"""MoySklad API client with retry logic and error handling."""

import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MoySkladError(Exception):
    """Custom exception for MoySklad API errors."""
    pass


class MoySkladClient:
    """HTTP client for MoySklad API."""

    def __init__(self, token: str = ""):
        self.base_url = settings.moysklad_base_url
        self.token = token or settings.moysklad_token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json;charset=utf-8",
        }
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0,
        )

    async def close(self):
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        try:
            response = await self.client.request(
                method=method,
                url=endpoint,
                json=json_data,
                params=params,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            logger.error(f"MoySklad HTTP error {e.response.status_code}: {e.response.text}")
            raise MoySkladError(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"MoySklad request error: {e}")
            raise MoySkladError(f"Request failed: {e}")

    # ========== Counterparty (Clients) ==========

    async def get_counterparties(
        self, phone: Optional[str] = None, days_back: Optional[int] = None,
        paginate_all: bool = False,
    ) -> List[Dict]:
        """Get counterparties (clients), optionally filtered by phone or recently updated.

        Expands `owner` (assigned MoySklad employee/agent) so callers can bind each
        Sales Doctor client to the correct agent, and route delivery/orders by agent.

        paginate_all=True walks every page (used for an initial full client sync).
        Without it, only the first 1000 rows are returned (incremental window).
        """
        from datetime import datetime, timedelta
        base_filters: List[str] = []
        if phone:
            base_filters.append(f"phone={phone}")
        if days_back is not None:
            since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
            base_filters.append(f"updated>{since}")

        all_rows: List[Dict] = []
        offset = 0
        page_size = 1000
        while True:
            params: Dict[str, Any] = {
                "limit": page_size,
                "offset": offset,
                "expand": "owner",
            }
            if base_filters:
                params["filter"] = ";".join(base_filters)
            data = await self._request("GET", "/entity/counterparty", params=params)
            rows = data.get("rows", [])
            all_rows.extend(rows)
            total = data.get("meta", {}).get("size", 0)
            offset += len(rows)
            if not paginate_all or not rows or offset >= total:
                break
        return all_rows

    async def get_counterparty(self, counterparty_id: str) -> Dict:
        """Get single counterparty by ID."""
        return await self._request("GET", f"/entity/counterparty/{counterparty_id}")

    async def create_counterparty(self, name: str, phone: str, **kwargs) -> Dict:
        """Create new counterparty in MoySklad."""
        payload = {
            "name": name,
            "phone": phone,
        }
        payload.update(kwargs)
        return await self._request("POST", "/entity/counterparty", json_data=payload)

    async def update_counterparty(self, counterparty_id: str, **kwargs) -> Dict:
        """Update counterparty."""
        return await self._request(
            "PUT", f"/entity/counterparty/{counterparty_id}", json_data=kwargs
        )

    # ========== Products (Stock) ==========

    async def get_products(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get all products with sale prices expanded.

        Including salePrices.currency lets the SD product sync attach a price
        to every product, so agents see the price when creating an order.
        """
        params = {
            "limit": limit,
            "offset": offset,
            "expand": "salePrices.currency",
        }
        data = await self._request("GET", "/entity/product", params=params)
        return data.get("rows", [])

    async def get_product_by_code(self, code: str) -> Optional[Dict]:
        """Find product by code (SKU)."""
        params = {"filter": f"code={code}"}
        data = await self._request("GET", "/entity/product", params=params)
        rows = data.get("rows", [])
        return rows[0] if rows else None

    async def get_stock(self, warehouse_id: Optional[str] = None) -> List[Dict]:
        """Get all stock rows with pagination.

        Includes salePriceCurrency block when available so callers can
        detect each item's pricing currency (USD, UZS, etc.).
        """
        all_rows: List[Dict] = []
        offset = 0
        limit = 1000
        while True:
            params: Dict[str, Any] = {"limit": limit, "offset": offset}
            if warehouse_id:
                params["filter"] = f"warehouse={warehouse_id}"
            data = await self._request("GET", "/report/stock/all", params=params)
            rows = data.get("rows", [])
            # Enrich each row with its currency ISO code via product expansion
            for row in rows:
                # MS stock report includes salePrice but not currency directly;
                # try to fetch from the product object if assortment is present.
                # For now, default to UZS unless explicitly set.
                if "salePriceCurrency" not in row:
                    row["salePriceCurrency"] = {"isoCode": "UZS"}
            all_rows.extend(rows)
            total = data.get("meta", {}).get("size", 0)
            offset += len(rows)
            if not rows or offset >= total:
                break
        return all_rows

    # ========== Customer Orders ==========

    async def get_customer_orders(
        self, status: Optional[str] = None, limit: int = 100, expand: bool = False,
        days_back: int = 90,
    ) -> List[Dict]:
        """Get customer orders from the last days_back days."""
        from datetime import datetime, timedelta
        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
        filters = [f"moment>{since}"]
        if status:
            filters.append(f"state.name={status}")
        params: Dict[str, Any] = {"limit": limit, "filter": ";".join(filters)}
        if expand:
            params["expand"] = "agent,state,positions"
        data = await self._request("GET", "/entity/customerorder", params=params)
        return data.get("rows", [])

    async def get_customer_order(self, order_id: str) -> Dict:
        """Get single customer order."""
        return await self._request("GET", f"/entity/customerorder/{order_id}")

    async def get_customer_order_with_positions(self, order_id: str) -> Dict:
        """Get customer order with agent, positions, product, and currency details expanded.

        Expanding rate.currency lets us read the order's ISO currency code
        (USD, UZS, EUR, etc.) to correctly convert prices to UZS sum.
        """
        params = {"expand": "agent,state,positions.assortment,rate.currency"}
        return await self._request("GET", f"/entity/customerorder/{order_id}", params=params)

    async def create_customer_order(self, order_data: Dict) -> Dict:
        """Create customer order in MoySklad."""
        return await self._request("POST", "/entity/customerorder", json_data=order_data)

    async def update_customer_order(self, order_id: str, **kwargs) -> Dict:
        """Update customer order status."""
        return await self._request(
            "PUT", f"/entity/customerorder/{order_id}", json_data=kwargs
        )

    # ========== Demands (Shipments) ==========

    async def create_demand(self, demand_data: Dict) -> Dict:
        """Create demand (shipment) in MoySklad."""
        return await self._request("POST", "/entity/demand", json_data=demand_data)

    async def get_demands(self, order_id: Optional[str] = None) -> List[Dict]:
        """Get demands."""
        params = {"limit": 100}
        if order_id:
            params["filter"] = f"customerOrder={order_id}"
        data = await self._request("GET", "/entity/demand", params=params)
        return data.get("rows", [])

    # ========== States (Statuses) ==========

    async def get_states(self, entity_type: str = "customerorder") -> List[Dict]:
        """Get available states for entity type."""
        data = await self._request("GET", f"/entity/{entity_type}/metadata")
        return data.get("states", [])

    # ========== Context (account info) ==========

    async def get_account_id(self) -> Optional[str]:
        """Fetch the MoySklad accountId for this token (used for webhook routing)."""
        try:
            data = await self._request("GET", "/context/employee")
            return data.get("accountId")
        except Exception:
            return None

    # ========== Webhooks ==========

    async def list_webhooks(self) -> List[Dict]:
        """List all webhooks for this account."""
        data = await self._request("GET", "/entity/webhook", params={"limit": 100})
        return data.get("rows", [])

    async def ensure_webhooks(self, target_url: str) -> Dict[str, Any]:
        """Idempotently register webhooks for the URL.

        Creates the standard set: customerorder CREATE/UPDATE, counterparty CREATE/UPDATE.
        Skips webhooks that already exist for the same URL+entityType+action.
        Returns {"created": [...], "existing": [...]}.
        """
        wanted = [
            ("customerorder", "CREATE"),
            ("customerorder", "UPDATE"),
            ("counterparty", "CREATE"),
            ("counterparty", "UPDATE"),
            ("demand", "CREATE"),  # Отгрузка → status "Отгружен" ga ko'chirish
        ]
        existing = await self.list_webhooks()
        # Index existing by (entityType, action, url)
        by_key = {(w.get("entityType"), w.get("action"), w.get("url")): w for w in existing}

        created = []
        already = []
        for entity_type, action in wanted:
            key = (entity_type, action, target_url)
            if key in by_key:
                already.append({"entityType": entity_type, "action": action})
                continue
            payload = {
                "url": target_url,
                "action": action,
                "entityType": entity_type,
                "enabled": True,
            }
            try:
                resp = await self._request("POST", "/entity/webhook", json_data=payload)
                created.append({"id": resp.get("id"), "entityType": entity_type, "action": action})
            except Exception as e:
                logger.warning("MS webhook create failed for %s/%s: %s", entity_type, action, e)
        return {"created": created, "existing": already}

    async def delete_webhook(self, webhook_id: str) -> None:
        await self._request("DELETE", f"/entity/webhook/{webhook_id}")

    # ========== Organization & Store ==========

    async def get_organization(self) -> Optional[Dict]:
        """Get first available organization."""
        data = await self._request("GET", "/entity/organization", params={"limit": 1})
        rows = data.get("rows", [])
        return rows[0] if rows else None

    async def get_store(self) -> Optional[Dict]:
        """Get first available store (warehouse)."""
        data = await self._request("GET", "/entity/store", params={"limit": 1})
        rows = data.get("rows", [])
        return rows[0] if rows else None

    # ========== Reports ==========

    async def get_counterparty_report(self, counterparty_id: str) -> Dict:
        """Get counterparty debt report."""
        params = {"counterparty.id": counterparty_id}
        return await self._request("GET", "/report/counterparty", params=params)


# Singleton instance
_moysklad_client: Optional[MoySkladClient] = None


async def get_moysklad_client() -> MoySkladClient:
    global _moysklad_client
    if _moysklad_client is None:
        _moysklad_client = MoySkladClient()
    return _moysklad_client


async def close_moysklad_client():
    global _moysklad_client
    if _moysklad_client:
        await _moysklad_client.close()
        _moysklad_client = None
