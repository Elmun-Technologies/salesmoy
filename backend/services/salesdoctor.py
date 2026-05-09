"""Sales Doctor API client — JSON-RPC style (all requests POST /api/v2/).

Auth flow:
  1. POST /api/v2/ with {"method": "login", "auth": {"login": ..., "password": ...}}
  2. Response returns {"userId": ..., "token": ...}
  3. Every subsequent request includes {"auth": {"userId": ..., "token": ...}}

Status codes (setOrder):
  1 = Новый, 2 = Отгружен, 3 = Доставлен, 4 = Возврат, 5 = Отменен
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# MoySklad status name → Sales Doctor status code
MS_STATUS_TO_SD: Dict[str, int] = {
    "Новый": 1,
    "В обработке": 1,
    "Отгружен": 2,
    "В пути": 2,
    "Доставлен": 3,
    "Возврат": 4,
    "Отменен": 5,
}


class SalesDoctorError(Exception):
    pass


class SalesDoctorClient:
    """HTTP client for Sales Doctor JSON-RPC API v2."""

    HEADERS = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; SalesMoy-Integration/1.0)",
    }

    def __init__(self, base_url: str, user_id: str, token: str, filial_id: int = 0):
        self.base_url = base_url.rstrip("/") + "/"
        self.user_id = user_id
        self.token = token
        self.filial_id = filial_id
        self._http = httpx.AsyncClient(timeout=30.0, headers=self.HEADERS)

    async def close(self):
        await self._http.aclose()

    # ========== Core RPC layer ==========

    def _auth(self) -> Dict:
        return {"userId": self.user_id, "token": self.token}

    def _filial(self) -> Dict:
        return {"filial_id": self.filial_id}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10), reraise=True)
    async def _rpc(self, method: str, data: Any, include_filial: bool = True) -> Dict:
        """Send a JSON-RPC style request to Sales Doctor."""
        payload: Dict = {
            "auth": self._auth(),
            "method": method,
            "data": data,
        }
        if include_filial:
            payload["filial"] = self._filial()

        try:
            resp = await self._http.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            result = resp.json() if resp.content else {}
            if isinstance(result, dict) and result.get("status") is False:
                err = result.get("error") or {}
                inner = result.get("result") or {}
                completed = inner.get("completed", 0) if isinstance(inner, dict) else 0
                # Build detailed error message from inner.failed[].error or err.data
                detail_msg = err.get("message") or "Unknown error"
                failed_items = inner.get("failed", []) if isinstance(inner, dict) else []
                if failed_items:
                    first_fail = failed_items[0]
                    if isinstance(first_fail, dict):
                        detail_msg = f"{first_fail.get('error', detail_msg)} (code_1C={first_fail.get('code_1C')})"
                if completed == 0:
                    raise SalesDoctorError(detail_msg)
                logger.warning("SD partial error in %s: %s", method, detail_msg)
            return result.get("result", result) if isinstance(result, dict) else result
        except httpx.HTTPStatusError as e:
            logger.error("SalesDoctor HTTP %s: %s", e.response.status_code, e.response.text)
            raise SalesDoctorError(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            logger.error("SalesDoctor request error: %s", e)
            raise SalesDoctorError(f"Request failed: {e}")

    # ========== Auth (class method — used before client instantiation) ==========

    @classmethod
    async def login(cls, base_url: str, login: str, password: str) -> Dict:
        """Login and return {"userId": ..., "token": ...}.

        Raises SalesDoctorError on failure.
        Token lifetime is infinite (until next login call).
        """
        url = base_url.rstrip("/") + "/"
        payload = {
            "method": "login",
            "auth": {"login": login, "password": password},
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; SalesMoy-Integration/1.0)",
        }
        async with httpx.AsyncClient(timeout=30.0) as http:
            try:
                resp = await http.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") is False:
                    err = data.get("error") or {}
                    raise SalesDoctorError(err.get("message") or "Login failed")
                result = data.get("result", data)
                if not result.get("userId") or not result.get("token"):
                    raise SalesDoctorError(f"Login response missing userId/token: {data}")
                return {"userId": str(result["userId"]), "token": str(result["token"])}
            except httpx.HTTPStatusError as e:
                raise SalesDoctorError(f"Login HTTP {e.response.status_code}: {e.response.text}")
            except httpx.RequestError as e:
                raise SalesDoctorError(f"Login request failed: {e}")

    # ========== Orders (Заявки) ==========

    async def set_order(self, orders: List[Dict]) -> Dict:
        """Import orders into Sales Doctor (setOrder).

        Each order dict structure (from SD API docs):
        {
            "CS_id": "",            # leave empty, SD assigns
            "SD_id": "",            # leave empty
            "code_1C": "MS-ORDER-NAME",  # MoySklad order name
            "comment": "",
            "status": 1,            # 1=Новый 2=Отгружен 3=Доставлен 4=Возврат 5=Отменен
            "client": {"code_1C": "CLIENT_PHONE_OR_CODE"},
            "agent":  {"code_1C": "AGENT_CODE"},        # optional
            "warehouse": {"code_1C": "WAREHOUSE_CODE"}, # optional
            "orderProducts": [
                {
                    "product": {"code_1C": "SKU"},
                    "quantity": 1,
                    "price": 10000,
                    "discountSumma": 0
                }
            ]
        }
        """
        return await self._rpc("setOrder", {"order": orders})

    async def get_order(self, order_cs_id: str) -> Dict:
        """Get order by CS_id."""
        return await self._rpc("getOrder", {"CS_id": order_cs_id}, include_filial=False)

    async def get_orders(self, date_from: Optional[str] = None) -> List[Dict]:
        """List all orders (optionally filtered by date)."""
        data = {"dateFrom": date_from} if date_from else {}
        result = await self._rpc("getOrder", data)
        if isinstance(result, dict):
            return result.get("order", [])
        return []

    async def get_clients(self) -> List[Dict]:
        """List all clients in SD."""
        result = await self._rpc("getClient", {})
        if isinstance(result, dict):
            return result.get("client", [])
        return []

    async def set_status(self, order_code_1c: str, status_code: int) -> Dict:
        """Update order status.

        status_code: 1=Новый, 2=Отгружен, 3=Доставлен, 4=Возврат, 5=Отменен
        Sends array format consistent with all other SD API methods.
        """
        return await self._rpc("setStatus", {
            "order": [
                {"CS_id": order_code_1c, "code_1C": order_code_1c, "status": status_code}
            ]
        })

    async def delete_order(self, order_cs_id: str) -> Dict:
        """Soft-delete order."""
        return await self._rpc("setDeletedOrder", {"CS_id": order_cs_id})

    # ========== Stock (Склад) ==========

    async def set_stock(self, warehouses: List[Dict]) -> Dict:
        """Set available stock for sales (setStock).

        warehouses — list of warehouse dicts (from SD API docs):
        [
            {
                "CS_id": "",            # leave empty or SD warehouse ID
                "SD_id": "",
                "code_1C": "WH_CODE",   # MoySklad warehouse/store code
                "dont_zero_others": True,  # keep products not in this list
                "products": [
                    {
                        "CS_id": "",
                        "SD_id": "",
                        "code_1C": "SKU_CODE",  # MoySklad product code
                        "quantity": 100
                    }
                ]
            }
        ]
        Note: data key is "warehouse" (not "stocks").
        """
        return await self._rpc("setStock", {"warehouse": warehouses})

    # ========== Clients / Directory (Справочник) ==========

    async def set_client(self, clients: List[Dict]) -> Dict:
        """Add or update clients/retail points (setClient).

        Each client dict structure (from SD API docs):
        {
            "CS_id": "",        # leave empty or existing
            "SD_id": "",
            "code_1C": "PHONE_OR_MS_ID",
            "shortName": "Short name",
            "firmName": "Full company name",
            "address": "Full address",
            "orentir": "",      # landmark/reference point
            "tel": "+998901234567",
            "comment": "",
            "inn": "",
            "pinfl": "",
            "lat": "",          # GPS latitude
            "lon": "",          # GPS longitude (note: "lon" not "lng")
            "active": "Y",      # "Y" or "N"
            "territory": {"code_1C": "TERRITORY_CODE"},  # optional
            "clientCategory": {"code_1C": "CAT_CODE"},   # optional
            "agent": {          # optional
                "code_1C": "AGENT_CODE",
                "visitDays": [1, 2, 3, 4, 5, 6, 7]
            }
        }
        Note: data key is "client" (not "clients").
        """
        return await self._rpc("setClient", {"client": clients})

    async def set_agent(self, agents: List[Dict]) -> Dict:
        """Add or update agents (setAgent)."""
        return await self._rpc("setAgent", {"agents": agents})

    async def set_product(self, products: List[Dict]) -> Dict:
        """Add or update products in SD catalog (setProduct).

        Each product dict (from SD API docs):
        {
            "CS_id": "",
            "SD_id": "",
            "code_1C": "SKU001",
            "name": "Product name",   # required
            "active": 1,              # 1 or 0 or "Y"/"N"
            "sort": 500,
            "volume": 0.0,
            "packQuantity": 1.0,
            "barCode": "",
            "weight": 0.0,
            "part_number": "",
            "category": {"code_1C": "CAT_CODE"},  # optional
            "unit": {"code_1C": "UNIT_CODE"}       # optional
        }
        Note: data key is "product", method is "setProduct".
        """
        return await self._rpc("setProduct", {"product": products})

    # ========== Debt / Cash (Касса) ==========

    async def set_current_balance(self, balances: List[Dict]) -> Dict:
        """Set current client balance via Касса (setCurrentBalance).

        Each balance dict:
        {
            "CS_id": "",
            "SD_id": "",
            "code_1C": "CLIENT_PHONE",   # client identifier
            "balance": 150000,            # remaining debt amount
            "paymentType": {
                "CS_id": "",
                "SD_id": "",
                "code_1C": "Наличные"
            }
        }
        """
        return await self._rpc("setCurrentBalance", {"currentBalance": balances})

    async def set_consumption(self, transactions: List[Dict]) -> Dict:
        """Record income/expense transaction in SD cash register (setConsumption).

        Each transaction dict:
        {
            "CS_id": "",
            "SD_id": "",
            "code_1C": "UNIQUE_CODE",   # e.g. payment ID or phone
            "name": "Payment description",
            "date": "2024-11-17T10:50:00",
            "comment": "",
            "summa": 150000,
            "type": "income",           # "income" for payment received
            "paymentType": {"CS_id": "", "SD_id": "", "code_1C": "Наличные"},
            "cashbox":     {"CS_id": "", "SD_id": "", "code_1C": ""}
        }
        """
        return await self._rpc("setConsumption", {"consumption": transactions})


# ========== Module-level helpers ==========

_sd_client: Optional["SalesDoctorClient"] = None


async def get_salesdoctor_client() -> Optional["SalesDoctorClient"]:
    return _sd_client


async def close_salesdoctor_client():
    global _sd_client
    if _sd_client:
        await _sd_client.close()
        _sd_client = None
