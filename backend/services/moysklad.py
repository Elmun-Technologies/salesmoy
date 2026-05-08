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

    def __init__(self):
        self.base_url = settings.moysklad_base_url
        self.token = settings.moysklad_token
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

    async def get_counterparties(self, phone: Optional[str] = None) -> List[Dict]:
        """Get all counterparties or filter by phone."""
        params = {"limit": 100}
        if phone:
            params["filter"] = f"phone={phone}"
        data = await self._request("GET", "/entity/counterparty", params=params)
        return data.get("rows", [])

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
        """Get all products."""
        params = {"limit": limit, "offset": offset}
        data = await self._request("GET", "/entity/product", params=params)
        return data.get("rows", [])

    async def get_product_by_code(self, code: str) -> Optional[Dict]:
        """Find product by code (SKU)."""
        params = {"filter": f"code={code}"}
        data = await self._request("GET", "/entity/product", params=params)
        rows = data.get("rows", [])
        return rows[0] if rows else None

    async def get_stock(self, warehouse_id: Optional[str] = None) -> List[Dict]:
        """Get stock report."""
        params = {"limit": 1000}
        if warehouse_id:
            params["filter"] = f"warehouse={warehouse_id}"
        data = await self._request("GET", "/report/stock/all", params=params)
        return data.get("rows", [])

    # ========== Customer Orders ==========

    async def get_customer_orders(
        self, status: Optional[str] = None, limit: int = 100, expand: bool = False
    ) -> List[Dict]:
        """Get customer orders."""
        params = {"limit": limit}
        if status:
            params["filter"] = f"state.name={status}"
        if expand:
            params["expand"] = "agent,state,positions"
        data = await self._request("GET", "/entity/customerorder", params=params)
        return data.get("rows", [])

    async def get_customer_order(self, order_id: str) -> Dict:
        """Get single customer order."""
        return await self._request("GET", f"/entity/customerorder/{order_id}")

    async def get_customer_order_with_positions(self, order_id: str) -> Dict:
        """Get customer order with agent and positions expanded."""
        params = {"expand": "agent,state,positions"}
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
