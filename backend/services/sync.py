"""Core synchronization logic between MoySklad and Sales Doctor (Tenant-aware)."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models import (
    Order, OrderStatus, SyncStatus, Client, ClientType,
    StockItem, DebtRecord, Delivery, SyncLog, LogType, Tenant,
)
from services.moysklad import MoySkladClient
from services.salesdoctor import SalesDoctorClient, MS_STATUS_TO_SD
from services.exchange_rate import get_usd_to_uzs_rate
from utils.currency import convert_usd_to_uzs_with_live_rate

logger = logging.getLogger(__name__)


class SyncService:
    """Main synchronization service with tenant isolation."""

    # Class-level: tracks last product sync time per tenant to avoid spamming SD
    _last_product_sync: Dict[int, datetime] = {}
    PRODUCT_SYNC_INTERVAL_SECONDS = 86400  # sync products to SD once per day max

    # Cached SD client categories per tenant {tenant_id: {"retail": SD_id, "wholesale": SD_id}}
    _sd_client_categories: Dict[int, Dict[str, str]] = {}

    # Cached SD default agent per tenant {tenant_id: {"code_1C": ..., "SD_id": ...}}
    _sd_default_agent: Dict[int, Dict[str, str]] = {}

    # Cached SD agents indexed by lowercase name {tenant_id: {agent_name_lc: {SD_id, code_1C}}}
    # Used to bind each MoySklad client to its real assigned agent.
    _sd_agents_by_name: Dict[int, Dict[str, Dict[str, str]]] = {}

    # Cached SD order defaults (priceType, warehouse) per tenant
    _sd_order_defaults: Dict[int, Dict[str, Dict[str, str]]] = {}

    # Cached SD "retail" priceType reference per tenant (SD_id + code_1C)
    # Resolved from the actual SD instance so setPrice attaches to the same
    # priceType the agent sees in the order ("Розничная").
    _sd_retail_price_type: Dict[int, Dict[str, str]] = {}

    # Map of MoySklad product code → currency ISO ("USD", "UZS", ...)
    # Built during product sync. Used by stock sync (whose API doesn't
    # expand currency) to apply the correct conversion.
    _product_currencies: Dict[int, Dict[str, str]] = {}

    # Default currency to assume when MoySklad data doesn't expose it.
    # Set this to "USD" for tenants whose MoySklad catalog is priced in $.
    _default_price_currency: Dict[int, str] = {}

    def __init__(self, db: AsyncSession, tenant: Tenant):
        self.db = db
        self.tenant = tenant
        self.ms = None
        self.sd = None

    async def init_clients(self):
        """Initialize API clients with tenant credentials."""
        if self.tenant.moysklad_access_token:
            self.ms = MoySkladClient(token=self.tenant.moysklad_access_token)
            # Auto-discover and persist accountId for webhook routing
            if not self.tenant.moysklad_account_id:
                try:
                    account_id = await self.ms.get_account_id()
                    if account_id:
                        self.tenant.moysklad_account_id = account_id
                        await self.db.commit()
                except Exception as e:
                    logger.warning("Could not fetch MS accountId for tenant %s: %s", self.tenant.id, e)

        if self.tenant.salesdoctor_token and self.tenant.salesdoctor_user_id:
            self.sd = SalesDoctorClient(
                base_url=self.tenant.salesdoctor_base_url or "",
                user_id=self.tenant.salesdoctor_user_id,
                token=self.tenant.salesdoctor_token,
                filial_id=self.tenant.salesdoctor_filial_id or 0,
            )

    # ========== Logging ==========

    async def log(
        self,
        log_type: LogType,
        module: str,
        message: str,
        order_id: Optional[int] = None,
        retry_count: int = 0,
    ):
        """Create sync log entry for tenant."""
        log = SyncLog(
            tenant_id=self.tenant.id,
            log_type=log_type,
            module=module,
            message=message,
            order_id=order_id,
            retry_count=retry_count,
        )
        self.db.add(log)
        await self.db.commit()
        logger.info(f"[Tenant {self.tenant.id}] [{module}] {message}")

    # ========== Client Sync ==========

    async def sync_client_to_moysklad(self, client_data: Dict) -> Optional[Client]:
        """Sync client from Sales Doctor to MoySklad."""
        if not self.ms:
            await self.log(LogType.ERROR, "Client Sync", "MoySklad not connected")
            return None

        try:
            phone = client_data.get("phone", "")
            name = client_data.get("name", "")

            existing = await self.ms.get_counterparties(phone=phone)

            if existing:
                ms_client = existing[0]
                await self.log(LogType.INFO, "Client Sync", f"Counterparty exists: {name}")
            else:
                ms_client = await self.ms.create_counterparty(
                    name=name, phone=phone,
                    actualAddress=client_data.get("address", ""),
                )
                await self.log(LogType.SUCCESS, "Client Sync", f"Created counterparty: {name}")

            # Save/update in local DB with tenant isolation
            result = await self.db.execute(
                select(Client).where(Client.tenant_id == self.tenant.id, Client.phone == phone)
            )
            client = result.scalar_one_or_none()

            if not client:
                client = Client(
                    tenant_id=self.tenant.id,
                    moysklad_id=ms_client.get("id"),
                    name=name,
                    phone=phone,
                    address=client_data.get("address", ""),
                    location=client_data.get("location", ""),
                    client_type=ClientType.WHOLESALE if client_data.get("type") == "Опт" else ClientType.RETAIL,
                    debt_limit=client_data.get("debt_limit", 0),
                )
                self.db.add(client)
            else:
                client.moysklad_id = ms_client.get("id")
                client.name = name
                client.address = client_data.get("address", client.address)

            await self.db.commit()

            # Sync client to Sales Doctor
            if self.sd:
                try:
                    ct = "wholesale" if client_data.get("type") == "Опт" else "retail"
                    category = await self._get_sd_category_id(ct)
                    sd_client = self._build_sd_client(
                        name=name, phone=phone,
                        address=client_data.get("address", ""),
                        client_type=ct, category=category,
                        location=client_data.get("location", ""),
                    )
                    await self.sd.set_client([sd_client])
                except Exception as e:
                    logger.warning("SalesDoctor setClient failed: %s", e)

            return client

        except Exception as e:
            await self.log(LogType.ERROR, "Client Sync", f"Failed: {e}")
            return None

    async def sync_clients_from_moysklad(self):
        """Pull recently updated clients from MoySklad to local DB.

        Only fetches clients updated in the last 24 hours. Initial full import
        is not done automatically — only new/changed clients are synced.
        """
        if not self.ms:
            return

        try:
            counterparties = await self.ms.get_counterparties(days_back=1)
            synced = 0
            merged = 0

            for cp in counterparties:
                phone = cp.get("phone", "").strip()
                name = cp.get("name", "").strip()
                ms_id = cp.get("id", "")

                if not name:
                    continue

                # Find ALL existing records matching phone OR name (potential duplicates)
                by_phone = None
                by_name = None

                if phone:
                    r = await self.db.execute(
                        select(Client).where(
                            Client.tenant_id == self.tenant.id,
                            Client.phone == phone,
                            Client.is_duplicate == False,
                        )
                    )
                    by_phone = r.scalars().first()

                r = await self.db.execute(
                    select(Client).where(
                        Client.tenant_id == self.tenant.id,
                        Client.name == name,
                        Client.is_duplicate == False,
                    )
                )
                by_name = r.scalars().first()

                # Both found and they differ → merge name-match into phone-match
                if by_phone and by_name and by_phone.id != by_name.id:
                    by_name.is_duplicate = True
                    by_name.merged_into_id = by_phone.id
                    by_phone.moysklad_id = ms_id
                    by_phone.name = name
                    merged += 1

                elif by_phone:
                    by_phone.moysklad_id = ms_id
                    by_phone.name = name

                elif by_name:
                    by_name.moysklad_id = ms_id
                    if phone:
                        by_name.phone = phone

                else:
                    # New client
                    client = Client(
                        tenant_id=self.tenant.id,
                        moysklad_id=ms_id,
                        name=name,
                        phone=phone,
                        address=cp.get("actualAddress", ""),
                        client_type=ClientType.RETAIL,
                        is_duplicate=False,
                    )
                    self.db.add(client)

                synced += 1

            await self.db.commit()

            # Push all synced clients to Sales Doctor in batches
            if self.sd and counterparties:
                try:
                    category = await self._get_sd_category_id("retail")
                    sd_clients_batch = []
                    for cp in counterparties:
                        cp_name = cp.get("name", "").strip()
                        cp_phone = cp.get("phone", "").strip()
                        if not cp_name:
                            continue
                        # Bind each client to its MoySklad owner (assigned agent)
                        owner = cp.get("owner")
                        agent_ref = await self._resolve_agent_for_ms_owner(owner)
                        sd_clients_batch.append(self._build_sd_client(
                            name=cp_name,
                            phone=cp_phone,
                            address=cp.get("actualAddress", ""),
                            client_type="retail",
                            category=category,
                            agent=agent_ref,
                        ))
                    batch_size = 100
                    failed = 0
                    for i in range(0, len(sd_clients_batch), batch_size):
                        try:
                            await self.sd.set_client(sd_clients_batch[i:i + batch_size])
                        except Exception as e:
                            failed += 1
                            logger.warning("SalesDoctor setClient batch %d failed: %s", i // batch_size, e)
                    if failed:
                        await self.log(LogType.ERROR, "Client Sync",
                                       f"{failed} setClient batch(es) failed of {(len(sd_clients_batch)+batch_size-1)//batch_size}")
                except Exception as e:
                    await self.log(LogType.ERROR, "Client Sync", f"SalesDoctor push failed: {e}")

            msg = f"Synced {synced} clients"
            if merged:
                msg += f", merged {merged} duplicates"
            await self.log(LogType.SUCCESS, "Client Sync", msg)

        except Exception as e:
            await self.log(LogType.ERROR, "Client Sync", f"Failed: {e}")

    async def sync_clients_from_salesdoctor(self):
        """Pull SD clients that don't have code_1C and push them to MoySklad.

        SD-originated clients have code_1C=null; MS-originated clients have code_1C set.
        For each SD-only client we create a MoySklad counterparty and update SD with code_1C.
        """
        if not self.sd or not self.ms:
            return

        try:
            sd_clients = await self.sd.get_clients()
            new_in_ms = 0
            sd_updates: List[Dict] = []

            for c in sd_clients:
                if c.get("code_1C"):
                    continue  # already linked to MS

                phone = (c.get("tel") or "").strip()
                name = (c.get("shortName") or c.get("firmName") or "").strip()
                if not name and not phone:
                    continue

                # Idempotency: skip if local Client already has this SD_id
                sd_id = c.get("SD_id", "")
                r = await self.db.execute(
                    select(Client).where(
                        Client.tenant_id == self.tenant.id,
                        Client.salesdoctor_id == sd_id,
                    )
                )
                if r.scalars().first():
                    continue

                # Find or create MS counterparty by phone
                ms_client = None
                if phone:
                    existing = await self.ms.get_counterparties(phone=phone)
                    if existing:
                        ms_client = existing[0]
                if not ms_client:
                    try:
                        ms_client = await self.ms.create_counterparty(
                            name=name or phone,
                            phone=phone,
                            actualAddress=c.get("address", ""),
                        )
                    except Exception as e:
                        logger.warning("MS create_counterparty failed for %s: %s", name, e)
                        continue

                ms_id = ms_client.get("id", "")
                code_1c = phone or ms_id

                # Save in local DB
                local = Client(
                    tenant_id=self.tenant.id,
                    moysklad_id=ms_id,
                    salesdoctor_id=sd_id,
                    name=name or phone,
                    phone=phone,
                    address=c.get("address", ""),
                    client_type=ClientType.RETAIL,
                )
                self.db.add(local)

                # Push code_1C back to SD so future syncs skip it
                category = await self._get_sd_category_id("retail")
                sd_updates.append({
                    "CS_id": c.get("CS_id", ""),
                    "SD_id": sd_id,
                    "code_1C": code_1c,
                    "shortName": name or phone,
                    "firmName": name or phone,
                    "tel": phone,
                    "address": c.get("address", ""),
                    "active": "Y",
                    "clientCategory": category if category else None,
                })
                new_in_ms += 1

            await self.db.commit()

            # Push SD updates in batches of 100
            batch_size = 100
            for i in range(0, len(sd_updates), batch_size):
                try:
                    await self.sd.set_client(sd_updates[i:i + batch_size])
                except Exception as e:
                    logger.warning("SD set_client (write-back) batch %d failed: %s", i // batch_size, e)

            if new_in_ms:
                await self.log(LogType.SUCCESS, "Client Sync",
                               f"Synced {new_in_ms} new clients SD → MoySklad")
        except Exception as e:
            await self.log(LogType.ERROR, "Client Sync", f"sync_clients_from_salesdoctor failed: {e}")

    # ========== Order Sync ==========

    async def process_moysklad_order(self, ms_order: Dict) -> Optional[Order]:
        """Save a MoySklad customerorder to DB and push to Sales Doctor.

        Accepts an order dict already expanded with agent, state, positions.
        Skips if order already exists by moysklad_id.
        """
        ms_id = ms_order.get("id", "")
        if not ms_id:
            return None

        # Skip if already in DB
        result = await self.db.execute(
            select(Order).where(
                Order.tenant_id == self.tenant.id,
                Order.moysklad_id == ms_id,
            )
        )
        if result.scalar_one_or_none():
            return None

        # Get live exchange rate once for all conversions in this order
        from utils.currency import convert_moysklad_price_to_uzs, get_order_currency_iso
        import os
        current_rate = await get_usd_to_uzs_rate()
        # Force-currency policy: tenant catalog is priced in $, so even orders
        # whose MoySklad rate.currency says UZS should be converted as USD.
        force_currency = (
            SyncService._default_price_currency.get(self.tenant.id)
            or os.getenv("FORCE_PRICE_CURRENCY", "USD")
        ).upper()
        order_currency = force_currency  # was: get_order_currency_iso(ms_order)

        # Parse counterparty (client) — note: MoySklad calls this "agent" (контрагент)
        agent_data = ms_order.get("agent", {})
        client_name = agent_data.get("name", "")
        client_phone = agent_data.get("phone", "") or agent_data.get("actualPhone", "")
        # Owner = the MoySklad employee (sales agent) assigned to this client.
        # Used to bind both client and order to the correct SD agent.
        client_owner = agent_data.get("owner") if isinstance(agent_data, dict) else None
        # Delivery address: prefer order's shipmentAddress, fall back to client's actual address
        delivery_address = (
            ms_order.get("shipmentAddress")
            or ms_order.get("shipmentAddressFull", {}).get("comment", "") if isinstance(ms_order.get("shipmentAddressFull"), dict) else ""
        ) or agent_data.get("actualAddress", "") or ""

        order_name = ms_order.get("name", ms_id[:8])
        # MoySklad returns sum in kopecks; normalize to UZS using order currency
        total_raw = ms_order.get("sum", 0)
        total = convert_moysklad_price_to_uzs(total_raw, order_currency, current_rate)
        description = ms_order.get("description", "")
        state_name = ms_order.get("state", {}).get("name", "Новый") if isinstance(ms_order.get("state"), dict) else "Новый"

        # Parse positions — keep raw MS prices; convert when pushing to SD
        items: List[Dict] = []
        positions_block = ms_order.get("positions", {})
        if isinstance(positions_block, dict):
            for pos in positions_block.get("rows", []):
                assortment = pos.get("assortment", {})
                price_raw = pos.get("price", 0)  # in kopecks/cents
                items.append({
                    "name": assortment.get("name", ""),
                    "sku": assortment.get("code", ""),
                    "qty": pos.get("quantity", 1),
                    # Store normalized UZS price for local DB / display
                    "price": convert_moysklad_price_to_uzs(price_raw, order_currency, current_rate),
                    "price_raw": price_raw,
                    "currency": order_currency,
                })

        status_map = {
            "Новый": OrderStatus.NEW,
            "В обработке": OrderStatus.PROCESSING,
            "Отгружен": OrderStatus.SHIPPED,
            "В пути": OrderStatus.IN_TRANSIT,
            "Доставлен": OrderStatus.DELIVERED,
            "Отменен": OrderStatus.CANCELLED,
        }

        order = Order(
            tenant_id=self.tenant.id,
            order_id=order_name,
            moysklad_id=ms_id,
            client_name=client_name,
            client_phone=client_phone,
            agent_name="MoySklad",
            comment=description,
            total_amount=total,
            status=status_map.get(state_name, OrderStatus.NEW),
            sync_status=SyncStatus.PENDING,
            items=items,
            raw_data={"source": "moysklad", "state": state_name},
        )
        self.db.add(order)

        # Push to Sales Doctor via setOrder (using exact SD API field names)
        if self.sd:
            try:
                # Resolve which SD agent owns this client (based on MS owner field)
                agent_ref = await self._resolve_agent_for_ms_owner(client_owner)
                # Pull GPS from MoySklad client's custom attributes if available
                client_lat_lon = self._extract_gps_from_ms_counterparty(agent_data)

                # Ensure client exists in SD before pushing order, with address + GPS + agent
                client_code = client_phone or client_name
                if client_code:
                    try:
                        category = await self._get_sd_category_id("retail")
                        sd_client = self._build_sd_client(
                            name=client_name or client_code,
                            phone=client_phone,
                            address=delivery_address,
                            client_type="retail",
                            category=category,
                            location=client_lat_lon,
                            agent=agent_ref,
                        )
                        await self.sd.set_client([sd_client])
                    except Exception as e:
                        logger.warning("Pre-order setClient failed for %s: %s", client_code, e)

                order_products = [
                    {
                        "product": {"code_1C": item.get("sku", "")},
                        "quantity": item.get("qty", 1),
                        # item["price"] is already normalized UZS (see parsing above)
                        "price": item.get("price", 0),
                        "discountSumma": 0,
                    }
                    for item in items
                    if item.get("sku")
                ]
                # Pre-pend delivery address to comment so courier sees it in SD
                comment_parts = []
                if delivery_address:
                    comment_parts.append(f"Манзил: {delivery_address}")
                if description:
                    comment_parts.append(description)
                full_comment = " | ".join(comment_parts)

                sd_order = {
                    "CS_id": "",
                    "SD_id": "",
                    "code_1C": order_name,
                    "comment": full_comment,
                    "status": MS_STATUS_TO_SD.get(state_name, 1),
                    "client": {"code_1C": client_code},
                    "orderProducts": order_products,
                }
                if delivery_address:
                    sd_order["address"] = delivery_address
                if agent_ref:
                    sd_order["agent"] = agent_ref
                order_defaults = await self._get_sd_order_defaults()
                if order_defaults.get("priceType"):
                    sd_order["priceType"] = order_defaults["priceType"]
                if order_defaults.get("warehouse"):
                    sd_order["warehouse"] = order_defaults["warehouse"]
                await self.sd.set_order([sd_order])
                order.salesdoctor_id = order_name
                order.sync_status = SyncStatus.SYNCED
                order.synced_at = datetime.utcnow()
            except Exception as e:
                order.sync_status = SyncStatus.ERROR
                await self.log(LogType.ERROR, "Order Sync",
                               f"setOrder failed for {order_name}: {e}")

        await self.db.commit()
        # Only log SUCCESS if order actually reached Sales Doctor
        if order.sync_status == SyncStatus.SYNCED:
            await self.log(LogType.SUCCESS, "Order Sync", f"MoySklad order {order_name} → Sales Doctor ✓", order.id)
        return order

    async def sync_orders_from_moysklad(self):
        """Pull today's new orders from MoySklad → Sales Doctor.

        Only fetches orders from the last 24 hours. Historical orders are not
        imported automatically — they can be synced on demand if the client requests.
        Also retries SD push for any DB orders that are still PENDING (no salesdoctor_id).
        """
        if not self.ms:
            return

        try:
            # Only last 24 hours — no historical import
            ms_orders = await self.ms.get_customer_orders(limit=100, expand=False, days_back=1)
            synced = 0

            for ms_order_brief in ms_orders:
                ms_id = ms_order_brief.get("id", "")
                if not ms_id:
                    continue

                # Check if already in DB
                result = await self.db.execute(
                    select(Order).where(
                        Order.tenant_id == self.tenant.id,
                        Order.moysklad_id == ms_id,
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    continue

                # New order: full processing
                try:
                    ms_order_full = await self.ms.get_customer_order_with_positions(ms_id)
                    order = await self.process_moysklad_order(ms_order_full)
                    if order:
                        synced += 1
                except Exception as e:
                    logger.warning("Could not fetch full order %s: %s", ms_id, e)
                    continue

            if synced > 0:
                await self.log(LogType.SUCCESS, "Order Sync",
                               f"Synced {synced} new orders from MoySklad")

            # ── Retry PENDING orders (pushed to DB but never pushed to SD) ──
            # This handles orders that were imported when SD was not configured,
            # or when the first setOrder call failed silently.
            if self.sd:
                try:
                    pending_result = await self.db.execute(
                        select(Order).where(
                            Order.tenant_id == self.tenant.id,
                            Order.sync_status == SyncStatus.PENDING,
                            Order.moysklad_id.isnot(None),
                        ).limit(20)  # process at most 20 retries per cycle
                    )
                    pending_orders = pending_result.scalars().all()
                except Exception as e:
                    logger.warning("Could not load PENDING orders for retry: %s", e)
                    pending_orders = []

                retried = 0
                failed_retries = 0
                for pending in pending_orders:
                    order_id_str = pending.order_id or str(pending.id)
                    try:
                        ms_order_full = await self.ms.get_customer_order_with_positions(pending.moysklad_id)
                        await self._push_order_to_sd(pending, ms_order_full)
                        pending.sync_status = SyncStatus.SYNCED
                        pending.synced_at = datetime.utcnow()
                        await self.db.commit()
                        retried += 1
                    except Exception as e:
                        logger.warning("Retry failed for order %s: %s", order_id_str, e)
                        failed_retries += 1
                        # Reset session state, then mark order as ERROR
                        try:
                            await self.db.rollback()
                        except Exception as rb_err:
                            logger.warning("Rollback failed after retry error: %s", rb_err)
                        try:
                            # Re-load pending order after rollback to avoid DetachedInstanceError
                            fresh = await self.db.get(Order, pending.id)
                            if fresh:
                                fresh.sync_status = SyncStatus.ERROR
                                await self.db.commit()
                        except Exception as mark_err:
                            logger.warning("Could not mark order %s as ERROR: %s", order_id_str, mark_err)
                            try:
                                await self.db.rollback()
                            except Exception:
                                pass

                if retried > 0:
                    await self.log(LogType.SUCCESS, "Order Sync",
                                   f"Retried {retried} pending orders → SD")
                if failed_retries > 0:
                    await self.log(LogType.WARNING, "Order Sync",
                                   f"{failed_retries} pending orders failed retry (marked as ERROR)")

        except Exception as e:
            import traceback as _tb
            logger.error("sync_orders_from_moysklad tenant=%s: %s\n%s",
                         self.tenant.id, e, _tb.format_exc())
            await self.log(LogType.ERROR, "Order Sync",
                           f"sync_orders_from_moysklad failed: {type(e).__name__}: {e}")

    async def sync_orders_from_salesdoctor(self):
        """Pull SD orders that originated in SD (no code_1C) and create them in MoySklad.

        Orders pushed from MS have code_1C set; SD-only orders have code_1C=null.
        For each SD-only order, create a MoySklad customerorder and write code_1C back.
        """
        if not self.sd or not self.ms:
            return

        try:
            sd_orders = await self.sd.get_orders()
            new_in_ms = 0
            sd_updates: List[Dict] = []

            org = await self.ms.get_organization()
            store = await self.ms.get_store()
            if not org or not store:
                return

            for o in sd_orders:
                if o.get("code_1C"):
                    continue  # already linked to MS

                sd_id = o.get("SD_id", "")
                if not sd_id:
                    continue

                # Skip if already imported
                r = await self.db.execute(
                    select(Order).where(
                        Order.tenant_id == self.tenant.id,
                        Order.salesdoctor_id == sd_id,
                    )
                )
                if r.scalars().first():
                    continue

                client_block = o.get("client") or {}
                client_phone = (client_block.get("tel") or "").strip()
                client_name = (client_block.get("shortName") or client_block.get("firmName") or "").strip()
                client_code_1c = client_block.get("code_1C") or client_phone

                # Find or create MS counterparty
                counterparty = None
                if client_phone:
                    existing = await self.ms.get_counterparties(phone=client_phone)
                    if existing:
                        counterparty = existing[0]
                if not counterparty and (client_name or client_phone):
                    try:
                        counterparty = await self.ms.create_counterparty(
                            name=client_name or client_phone,
                            phone=client_phone,
                        )
                    except Exception as e:
                        logger.warning("MS create_counterparty failed: %s", e)
                        continue
                if not counterparty:
                    continue

                # Build positions from SD orderProducts
                positions = []
                products_invalid = False
                for p in o.get("orderProducts", []) or []:
                    sku = (p.get("product") or {}).get("code_1C") or p.get("code_1C")
                    qty = p.get("quantity", 1)
                    price = p.get("price", 0)
                    if not sku:
                        continue
                    ms_product = await self.ms.get_product_by_code(sku)
                    if not ms_product:
                        products_invalid = True
                        logger.warning("MS product not found for SKU %s — skip order %s", sku, sd_id)
                        break
                    positions.append({
                        "quantity": qty,
                        "price": price,
                        "assortment": {"meta": ms_product.get("meta")},
                    })
                if products_invalid or not positions:
                    continue

                order_name = f"SD-{sd_id}"
                ms_order_data = {
                    "name": order_name,
                    "organization": {"meta": org["meta"]},
                    "agent": {"meta": counterparty["meta"]},
                    "store": {"meta": store["meta"]},
                    "positions": positions,
                    "description": o.get("comment", ""),
                }

                try:
                    ms_order = await self.ms.create_customer_order(ms_order_data)
                except Exception as e:
                    logger.warning("MS create_customer_order failed for SD %s: %s", sd_id, e)
                    continue

                ms_id = ms_order.get("id", "")

                local = Order(
                    tenant_id=self.tenant.id,
                    order_id=order_name,
                    moysklad_id=ms_id,
                    salesdoctor_id=sd_id,
                    client_name=client_name,
                    client_phone=client_phone,
                    agent_name="SalesDoctor",
                    comment=o.get("comment", ""),
                    total_amount=o.get("totalSumma", 0) or 0,
                    status=OrderStatus.NEW,
                    sync_status=SyncStatus.SYNCED,
                    items=[
                        {"sku": (p.get("product") or {}).get("code_1C", ""),
                         "qty": p.get("quantity", 1),
                         "price": p.get("price", 0)}
                        for p in (o.get("orderProducts") or [])
                    ],
                    raw_data={"source": "salesdoctor", "ms_order_name": order_name},
                    synced_at=datetime.utcnow(),
                )
                self.db.add(local)
                new_in_ms += 1

                # Write code_1C back to SD so we don't reprocess
                sd_updates.append({
                    "CS_id": o.get("CS_id", ""),
                    "SD_id": sd_id,
                    "code_1C": order_name,
                })

            await self.db.commit()

            # Update SD orders with code_1C in batches
            for i in range(0, len(sd_updates), 100):
                try:
                    await self.sd._rpc("setOrder", {"order": sd_updates[i:i + 100]})
                except Exception as e:
                    logger.warning("SD setOrder write-back batch %d failed: %s", i // 100, e)

            if new_in_ms:
                await self.log(LogType.SUCCESS, "Order Sync",
                               f"Synced {new_in_ms} new orders SD → MoySklad")
        except Exception as e:
            await self.log(LogType.ERROR, "Order Sync", f"sync_orders_from_salesdoctor failed: {e}")

    async def _push_order_to_sd(self, order: Order, ms_order: Dict):
        """Push an existing DB order to Sales Doctor (used for retries)."""
        if not self.sd:
            return

        from utils.currency import convert_moysklad_price_to_uzs, get_order_currency_iso
        import os
        current_rate = await get_usd_to_uzs_rate()
        force_currency = (
            SyncService._default_price_currency.get(self.tenant.id)
            or os.getenv("FORCE_PRICE_CURRENCY", "USD")
        ).upper()
        order_currency = force_currency  # tenant catalog is $ — force USD

        agent_data = ms_order.get("agent", {})
        client_name = agent_data.get("name", order.client_name or "")
        client_phone = (agent_data.get("phone") or agent_data.get("actualPhone") or order.client_phone or "")
        client_owner = agent_data.get("owner") if isinstance(agent_data, dict) else None
        state_name = ms_order.get("state", {}).get("name", "Новый") if isinstance(ms_order.get("state"), dict) else "Новый"
        description = ms_order.get("description", order.comment or "")
        delivery_address = (
            ms_order.get("shipmentAddress")
            or agent_data.get("actualAddress", "")
            or ""
        )
        client_lat_lon = self._extract_gps_from_ms_counterparty(agent_data)
        agent_ref = await self._resolve_agent_for_ms_owner(client_owner)

        items: List[Dict] = []
        positions_block = ms_order.get("positions", {})
        if isinstance(positions_block, dict):
            for pos in positions_block.get("rows", []):
                assortment = pos.get("assortment", {})
                price_raw = pos.get("price", 0)  # MoySklad kopecks/cents
                items.append({
                    "sku": assortment.get("code", ""),
                    "qty": pos.get("quantity", 1),
                    # Convert to UZS sum based on order's currency
                    "price": convert_moysklad_price_to_uzs(price_raw, order_currency, current_rate),
                })

        client_code = client_phone or client_name
        if client_code:
            try:
                category = await self._get_sd_category_id("retail")
                sd_client = self._build_sd_client(
                    name=client_name or client_code,
                    phone=client_phone,
                    address=delivery_address,
                    client_type="retail",
                    category=category,
                    location=client_lat_lon,
                    agent=agent_ref,
                )
                await self.sd.set_client([sd_client])
            except Exception as e:
                logger.warning("Pre-order setClient failed for %s: %s", client_code, e)

        order_products = [
            {
                "product": {"code_1C": item.get("sku", "")},
                "quantity": item.get("qty", 1),
                # Already normalized to UZS in items parsing above
                "price": item.get("price", 0),
                "discountSumma": 0,
            }
            for item in items if item.get("sku")
        ]
        comment_parts = []
        if delivery_address:
            comment_parts.append(f"Манзил: {delivery_address}")
        if description:
            comment_parts.append(description)
        full_comment = " | ".join(comment_parts)

        sd_order = {
            "CS_id": "", "SD_id": "",
            "code_1C": order.order_id,
            "comment": full_comment,
            "status": MS_STATUS_TO_SD.get(state_name, 1),
            "client": {"code_1C": client_code},
            "orderProducts": order_products,
        }
        if delivery_address:
            sd_order["address"] = delivery_address
        if agent_ref:
            sd_order["agent"] = agent_ref
        order_defaults = await self._get_sd_order_defaults()
        if order_defaults.get("priceType"):
            sd_order["priceType"] = order_defaults["priceType"]
        if order_defaults.get("warehouse"):
            sd_order["warehouse"] = order_defaults["warehouse"]
        await self.sd.set_order([sd_order])
        order.salesdoctor_id = order.order_id
        await self.db.commit()

    async def create_order_in_moysklad(self, order_data: Dict) -> Optional[Dict]:
        """Create order in MoySklad from Sales Doctor data."""
        if not self.ms:
            await self.log(LogType.ERROR, "Order Sync", "MoySklad not connected")
            return None

        try:
            client_name = order_data.get("client_name", "")
            client_phone = order_data.get("phone", "")
            items = order_data.get("items", [])

            # Check monthly order limit
            current_month = datetime.utcnow().replace(day=1)
            from sqlalchemy import func
            order_count = await self.db.execute(
                select(func.count()).select_from(Order).where(
                    Order.tenant_id == self.tenant.id,
                    Order.created_at >= current_month
                )
            )
            # Find or create counterparty
            counterparties = await self.ms.get_counterparties(phone=client_phone)
            if counterparties:
                counterparty = counterparties[0]
            else:
                counterparty = await self.ms.create_counterparty(
                    name=client_name, phone=client_phone
                )

            org = await self.ms.get_organization()
            store = await self.ms.get_store()

            if not org or not store:
                await self.log(LogType.ERROR, "Order Sync", "Organization or Store not found")
                return None

            # ❗ Check client debt limit — BLOCK order if exceeded
            client_result = await self.db.execute(
                select(Client).where(
                    Client.tenant_id == self.tenant.id,
                    Client.phone == client_phone
                )
            )
            client = client_result.scalar_one_or_none()
            if client and client.debt_limit > 0 and client.debt >= client.debt_limit:
                await self.log(
                    LogType.ERROR, "Order Sync",
                    f"BLOCKED: debt limit exceeded for {client_name} (debt={client.debt}, limit={client.debt_limit})"
                )
                return None

            positions = []
            for item in items:
                sku = item.get("sku", "")
                qty = item.get("qty", 1)

                # ❗ Check stock — BLOCK order if qty=0
                stock_result = await self.db.execute(
                    select(StockItem).where(
                        StockItem.tenant_id == self.tenant.id,
                        StockItem.sku == sku,
                    )
                )
                stock_item = stock_result.scalar_one_or_none()
                if stock_item is not None and stock_item.qty <= 0:
                    await self.log(
                        LogType.ERROR, "Order Sync",
                        f"BLOCKED: '{stock_item.name}' out of stock (sku={sku})"
                    )
                    return None

                product = await self.ms.get_product_by_code(sku)
                if not product:
                    await self.log(LogType.ERROR, "Order Sync", f"Product not found: {sku}")
                    return None
                positions.append({
                    "quantity": qty,
                    "price": item.get("price", 0),
                    "assortment": {"meta": product.get("meta")},
                })

            ms_order_data = {
                "name": order_data.get("order_id", f"SD-{self.tenant.id}"),
                "organization": {"meta": org["meta"]},
                "agent": {"meta": counterparty["meta"]},
                "store": {"meta": store["meta"]},
                "positions": positions,
                "description": order_data.get("comment", ""),
            }

            ms_order = await self.ms.create_customer_order(ms_order_data)

            order = Order(
                tenant_id=self.tenant.id,
                order_id=order_data.get("order_id", ""),
                moysklad_id=ms_order.get("id"),
                client_name=client_name,
                client_phone=client_phone,
                agent_name=order_data.get("agent_name", ""),
                comment=order_data.get("comment", ""),
                total_amount=sum(i.get("qty", 0) * i.get("price", 0) for i in items),
                status=OrderStatus.NEW,
                sync_status=SyncStatus.SYNCED,
                items=items,
                raw_data=order_data,
                synced_at=datetime.utcnow(),
            )
            self.db.add(order)
            await self.db.commit()

            await self.log(LogType.SUCCESS, "Order Sync", f"Order {order.order_id} created", order.id)
            return ms_order

        except Exception as e:
            await self.log(LogType.ERROR, "Order Sync", f"Error: {e}", retry_count=3)
            return None

    async def update_order_status_from_moysklad(self, moysklad_order_id: str, new_status: str):
        """Update local order status when MoySklad sends webhook."""
        try:
            result = await self.db.execute(
                select(Order).where(
                    Order.tenant_id == self.tenant.id,
                    Order.moysklad_id == moysklad_order_id
                )
            )
            order = result.scalar_one_or_none()

            if not order:
                await self.log(LogType.WARNING, "Order Sync", f"Order {moysklad_order_id} not found")
                return

            status_map = {
                "Новый": OrderStatus.NEW,
                "В обработке": OrderStatus.PROCESSING,
                "Отгружен": OrderStatus.SHIPPED,
                "В пути": OrderStatus.IN_TRANSIT,
                "Доставлен": OrderStatus.DELIVERED,
                "Отменен": OrderStatus.CANCELLED,
            }

            new_local_status = status_map.get(new_status, order.status)

            # Short-circuit: if local status already matches, the change came from us — skip SD push to break echo loops
            if order.status == new_local_status:
                await self.log(LogType.INFO, "Order Sync", f"Status {new_status} already current — no-op", order.id)
                return

            order.status = new_local_status
            order.sync_status = SyncStatus.SYNCED
            order.updated_at = datetime.utcnow()
            await self.db.commit()

            if self.sd and order.order_id:
                try:
                    sd_code = MS_STATUS_TO_SD.get(new_status)
                    if sd_code:
                        # order_id is the code_1C we registered in setOrder; SD uses it as CS_id
                        await self.sd.set_status(order.order_id, sd_code)
                except Exception as e:
                    await self.log(LogType.WARNING, "Order Sync", f"SalesDoctor status update failed: {e}", order.id)

            await self.log(LogType.SUCCESS, "Order Sync", f"Status updated to {new_status}", order.id)

        except Exception as e:
            await self.log(LogType.ERROR, "Order Sync", f"Status update failed: {e}")

    # ========== Product Sync ==========

    async def sync_products_to_salesdoctor(self):
        """Register MoySklad products in Sales Doctor so stock sync works.

        SD requires products to exist (matching code_1C) before setStock can reference them.
        Fetches MoySklad product list and sends them via setProduct.
        """
        if not self.ms or not self.sd:
            return

        # Throttle: max once per hour per tenant
        last = SyncService._last_product_sync.get(self.tenant.id)
        if last and (datetime.utcnow() - last).total_seconds() < SyncService.PRODUCT_SYNC_INTERVAL_SECONDS:
            return
        SyncService._last_product_sync[self.tenant.id] = datetime.utcnow()

        try:
            # Fetch all products with pagination
            ms_products: List[Dict] = []
            offset = 0
            while True:
                page = await self.ms.get_products(limit=1000, offset=offset)
                if not page:
                    break
                ms_products.extend(page)
                offset += len(page)
                if len(page) < 1000:
                    break

            if not ms_products:
                return

            # Get SD unit for "Штук" (pieces) to attach to each product
            sd_unit: Dict = {}
            try:
                unit_result = await self.sd._rpc("getUnit", {})
                units = unit_result.get("unit", []) if isinstance(unit_result, dict) else []
                shtuk = next((u for u in units if "штук" in u.get("name", "").lower()), None)
                if shtuk:
                    sd_unit = {"SD_id": shtuk["SD_id"]}
            except Exception:
                pass

            # Live exchange rate for any USD-priced products
            from utils.currency import convert_moysklad_price_to_uzs, detect_currency_iso
            current_rate = await get_usd_to_uzs_rate()

            # Currency policy:
            #   FORCE_PRICE_CURRENCY="USD" → every product price treated as USD
            #   (MoySklad isoCode is IGNORED). This matches tenants whose
            #   catalogs use $ semantics regardless of the MoySklad currency
            #   field. Default is "USD" because this is the current customer's
            #   setup — override per tenant via _default_price_currency or env.
            import os
            force_currency = (
                SyncService._default_price_currency.get(self.tenant.id)
                or os.getenv("FORCE_PRICE_CURRENCY", "USD")
            ).upper()
            currency_cache: Dict[str, str] = {}

            sd_products = []
            sd_product_prices = []  # (code_1C, price_uzs) for setPrice
            for p in ms_products:
                code = p.get("code", "")
                name = p.get("name", "")
                if not code or not name:
                    continue
                # Extract sale price from MoySklad product. Currency is forced
                # per tenant policy above — do NOT trust MoySklad's isoCode.
                price_uzs = 0
                product_currency = force_currency
                sale_prices = p.get("salePrices") or []
                if isinstance(sale_prices, list) and sale_prices:
                    sp = sale_prices[0]
                    if isinstance(sp, dict):
                        raw_value = sp.get("value", 0)
                        price_uzs = convert_moysklad_price_to_uzs(
                            raw_value, product_currency, current_rate
                        )
                # Remember this product's currency so stock sync can reuse it
                if code:
                    currency_cache[code] = product_currency

                # setProduct payload (no price field — per SD API spec)
                prod: Dict = {
                    "CS_id": "",
                    "SD_id": "",
                    "code_1C": code,
                    "name": name,
                    "active": 1,
                    "sort": 500,
                    "volume": p.get("volume", 0.0),
                    "packQuantity": 1.0,
                    "barCode": "",
                    "weight": p.get("weight", 0.0),
                    "part_number": "",
                }
                if sd_unit:
                    prod["unit"] = sd_unit
                sd_products.append(prod)
                if price_uzs > 0:
                    sd_product_prices.append((code, price_uzs))

            # Publish currency cache so sync_stock can convert correctly
            if currency_cache:
                SyncService._product_currencies[self.tenant.id] = currency_cache

            # 1) Push products (without price) — matches SD setProduct schema
            batch_size = 100
            for i in range(0, len(sd_products), batch_size):
                batch = sd_products[i:i + batch_size]
                try:
                    await self.sd.set_product(batch)
                except Exception as e:
                    logger.warning("setProduct batch %d failed: %s", i // batch_size, e)

            # 2) Push prices via SD's dedicated setPrice endpoint (Касса → Цены).
            #    Crucial: attach to the EXACT priceType the agent uses in the
            #    order UI (usually "Розничная"). Resolve its SD_id/code_1C
            #    once per tenant, then embed that ref in every setPrice row.
            priced = 0
            if sd_product_prices:
                price_type_ref = await self._get_sd_retail_price_type()
                if not price_type_ref:
                    logger.warning(
                        "No SD priceType resolved — skipping setPrice (would attach prices to nothing)"
                    )
                else:
                    doc_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    payload_all = []
                    for code, price in sd_product_prices:
                        # Build per-row priceType: copy ref and add the price field
                        pt_block: Dict = {
                            "CS_id": price_type_ref.get("CS_id", ""),
                            "SD_id": price_type_ref.get("SD_id", ""),
                            "code_1C": price_type_ref.get("code_1C", ""),
                            "price": f"{price:.2f}",
                        }
                        payload_all.append({
                            "CS_id": "",
                            "SD_id": "",
                            "code_1C": code,
                            "document_1C": doc_id,
                            "priceType": pt_block,
                        })
                    for i in range(0, len(payload_all), batch_size):
                        chunk = payload_all[i:i + batch_size]
                        try:
                            await self.sd._rpc("setPrice", {"product": chunk})
                            priced += len(chunk)
                        except Exception as e:
                            logger.warning("setPrice batch %d failed: %s", i // batch_size, e)

            await self.log(LogType.INFO, "Product Sync",
                           f"Synced {len(sd_products)} products to Sales Doctor "
                           f"({priced}/{len(sd_product_prices)} prices via setPrice)")

        except Exception as e:
            logger.warning("sync_products_to_salesdoctor failed: %s", e)

    async def _get_sd_category_id(self, client_type: str = "retail") -> Dict:
        """Return SD clientCategory reference for retail or wholesale.

        Fetches categories once per session and caches. Falls back to first available.
        """
        if not self.sd:
            return {}
        cached = SyncService._sd_client_categories.get(self.tenant.id)
        if not cached:
            try:
                result = await self.sd._rpc("getClientCategory", {})
                cats = result.get("clientCategory", []) if isinstance(result, dict) else []
                cached = {}
                for c in cats:
                    name_lower = (c.get("name") or "").lower()
                    if "розница" in name_lower or "retail" in name_lower:
                        cached["retail"] = {"SD_id": c["SD_id"]}
                    elif "опт" in name_lower or "wholesale" in name_lower:
                        cached["wholesale"] = {"SD_id": c["SD_id"]}
                # fallback: use first category for both if mapping not found
                if cats and "retail" not in cached:
                    cached["retail"] = {"SD_id": cats[0]["SD_id"]}
                if cats and "wholesale" not in cached:
                    cached["wholesale"] = cached.get("retail", {"SD_id": cats[0]["SD_id"]})
                SyncService._sd_client_categories[self.tenant.id] = cached
            except Exception as e:
                logger.warning("SD getClientCategory failed: %s", e)
                return {}
        return cached.get(client_type, cached.get("retail", {}))

    async def _get_sd_order_defaults(self) -> Dict[str, Dict[str, str]]:
        """Ensure SD has priceType, paymentType, valyutaType, warehouse set up
        and return references {"priceType": {...}, "warehouse": {...}} for setOrder.

        Lazy: runs once per tenant. SD requires every order to reference these.
        """
        if not self.sd:
            return {}
        cached = SyncService._sd_order_defaults.get(self.tenant.id)
        if cached:
            return cached

        defaults: Dict[str, Dict[str, str]] = {}
        try:
            # 1) Ensure paymentType has code_1C "cash"
            pt_result = await self.sd._rpc("getPaymentType", {})
            payment_types = pt_result.get("currency", []) if isinstance(pt_result, dict) else []
            cash_pt = next((p for p in payment_types if p.get("code_1C") == "cash"), None)
            if not cash_pt and payment_types:
                # Pick first UZS payment type and assign code_1C "cash"
                first_uzs = next((p for p in payment_types if p.get("short") == "UZS"), payment_types[0])
                await self.sd._rpc("setPaymentType", {"paymentType": [{
                    "CS_id": first_uzs.get("CS_id", ""),
                    "SD_id": first_uzs.get("SD_id", ""),
                    "code_1C": "cash",
                    "name": first_uzs.get("name", "Наличные"),
                    "short": first_uzs.get("short", "UZS"),
                    "active": "Y",
                }]})
                cash_pt = first_uzs

            # 2) Get valyutaType (currency)
            vt_result = await self.sd._rpc("getValyutaType", {})
            valyuta_types = vt_result.get("valyutaType", []) if isinstance(vt_result, dict) else []
            uzs_vt = next((v for v in valyuta_types if v.get("short") == "UZS"), valyuta_types[0] if valyuta_types else None)

            # 3) Ensure priceType has code_1C "retail"
            ptype_result = await self.sd._rpc("getPriceType", {})
            price_types = ptype_result.get("priceType", []) if isinstance(ptype_result, dict) else []
            retail_pt = next((p for p in price_types if p.get("code_1C") == "retail"), None)
            if not retail_pt and uzs_vt and cash_pt:
                await self.sd._rpc("setPriceType", {"priceType": [{
                    "CS_id": "", "SD_id": "",
                    "code_1C": "retail",
                    "name": "Розничная",
                    "paymentType": {"SD_id": cash_pt.get("SD_id", "")},
                    "valyutaType": {"SD_id": uzs_vt.get("SD_id", "")},
                    "active": "Y",
                }]})
            defaults["priceType"] = {"code_1C": "retail"}

            # 4) Ensure warehouse has code_1C set
            wh_result = await self.sd._rpc("getWarehouse", {})
            warehouses = wh_result.get("warehouse", []) if isinstance(wh_result, dict) else []
            wh_with_code = next((w for w in warehouses if w.get("code_1C")), None)
            if wh_with_code:
                defaults["warehouse"] = {"code_1C": wh_with_code["code_1C"]}
            elif warehouses:
                # Assign code_1C "main" to first warehouse
                first_wh = warehouses[0]
                await self.sd._rpc("setWarehouse", {"warehouse": [{
                    "CS_id": first_wh.get("CS_id", ""),
                    "SD_id": first_wh.get("SD_id", ""),
                    "code_1C": "main",
                    "name": first_wh.get("name", "Основной склад"),
                    "active": "Y",
                }]})
                defaults["warehouse"] = {"code_1C": "main"}

            SyncService._sd_order_defaults[self.tenant.id] = defaults
        except Exception as e:
            logger.warning("SD order defaults setup failed: %s", e)
        return defaults

    async def _get_sd_default_agent(self) -> Optional[Dict]:
        """Return SD default agent reference {"code_1C": ...} for setOrder.

        SD requires every order to have an agent. Caches first available agent per tenant.
        """
        if not self.sd:
            return None
        cached = SyncService._sd_default_agent.get(self.tenant.id)
        if cached:
            return cached
        try:
            result = await self.sd._rpc("getAgent", {})
            agents = result.get("agent", []) if isinstance(result, dict) else []
            if not agents:
                return None
            # Prefer an agent with code_1C set; fall back to SD_id-based reference
            chosen = next((a for a in agents if a.get("code_1C")), agents[0])
            ref: Dict = {}
            if chosen.get("code_1C"):
                ref["code_1C"] = chosen["code_1C"]
            elif chosen.get("SD_id"):
                ref["SD_id"] = chosen["SD_id"]
            SyncService._sd_default_agent[self.tenant.id] = ref
            return ref
        except Exception as e:
            logger.warning("SD getAgent failed: %s", e)
            return None

    async def _get_sd_retail_price_type(self) -> Dict[str, str]:
        """Return a reference {SD_id, code_1C} to SD's active retail priceType.

        Strategy:
          1. Fetch all priceTypes from SD.
          2. Prefer one whose name contains "роз" or "retail".
          3. Otherwise pick the first one.
          4. Return BOTH SD_id and code_1C so callers can include whichever
             SD's setPrice accepts.

        Result is cached per tenant — only fetched once per worker lifetime.
        """
        cached = SyncService._sd_retail_price_type.get(self.tenant.id)
        if cached is not None:
            return cached
        ref: Dict[str, str] = {}
        if not self.sd:
            return ref
        try:
            result = await self.sd._rpc("getPriceType", {})
            price_types = result.get("priceType", []) if isinstance(result, dict) else []
            chosen = None
            for pt in price_types:
                if not isinstance(pt, dict):
                    continue
                name = (pt.get("name") or "").lower()
                if "роз" in name or "retail" in name:
                    chosen = pt
                    break
            if not chosen and price_types:
                chosen = price_types[0]
            if chosen:
                if chosen.get("SD_id"):
                    ref["SD_id"] = str(chosen["SD_id"])
                if chosen.get("code_1C"):
                    ref["code_1C"] = chosen["code_1C"]
                if chosen.get("CS_id"):
                    ref["CS_id"] = str(chosen["CS_id"])
        except Exception as e:
            logger.warning("SD getPriceType lookup failed: %s", e)
        SyncService._sd_retail_price_type[self.tenant.id] = ref
        return ref

    async def _load_sd_agents_index(self) -> Dict[str, Dict[str, str]]:
        """Build and cache an index of SD agents by lowercased name.

        Returns: {agent_name_lc: {"SD_id": ..., "code_1C": ...}}
        Used to match a MoySklad client's owner (agent) to its SD counterpart
        so each client is bound to the right agent.
        """
        if not self.sd:
            return {}
        cached = SyncService._sd_agents_by_name.get(self.tenant.id)
        if cached is not None:
            return cached
        index: Dict[str, Dict[str, str]] = {}
        try:
            result = await self.sd._rpc("getAgent", {})
            agents = result.get("agent", []) if isinstance(result, dict) else []
            for a in agents:
                name = (a.get("name") or a.get("fio") or "").strip().lower()
                if not name:
                    continue
                ref: Dict[str, str] = {}
                if a.get("SD_id"):
                    ref["SD_id"] = a["SD_id"]
                if a.get("code_1C"):
                    ref["code_1C"] = a["code_1C"]
                if ref:
                    index[name] = ref
        except Exception as e:
            logger.warning("SD agents index load failed: %s", e)
        SyncService._sd_agents_by_name[self.tenant.id] = index
        return index

    async def _resolve_agent_for_ms_owner(self, owner_block: Optional[Dict]) -> Optional[Dict]:
        """Map a MoySklad client.owner (employee) to a SD agent reference.

        Tries to match by name (case-insensitive). Falls back to the default
        agent so existing logic still produces a valid SD order.
        """
        if not owner_block or not isinstance(owner_block, dict):
            return await self._get_sd_default_agent()

        owner_name = (owner_block.get("name") or "").strip().lower()
        if owner_name:
            index = await self._load_sd_agents_index()
            ref = index.get(owner_name)
            if ref:
                return ref
            # Try a softer match: first-name only
            first = owner_name.split()[0] if owner_name else ""
            for key, ref in index.items():
                if key.startswith(first):
                    return ref

        return await self._get_sd_default_agent()

    def _extract_gps_from_ms_counterparty(self, cp: Dict) -> str:
        """Extract a 'lat,lon' string from a MoySklad counterparty if available.

        MoySklad stores GPS via custom attributes (атрибуты): each attribute has
        a name and value. We look for an attribute whose name contains 'gps',
        'координат', or 'lat/lon'. Returns empty string if not found.
        """
        if not isinstance(cp, dict):
            return ""
        attrs = cp.get("attributes") or []
        if not isinstance(attrs, list):
            return ""
        lat = lon = None
        for a in attrs:
            if not isinstance(a, dict):
                continue
            name = (a.get("name") or "").lower()
            value = a.get("value")
            if value is None:
                continue
            s = str(value)
            if "gps" in name or "координат" in name or "geo" in name:
                # Expect "lat,lon" or "lat;lon"
                for sep in (",", ";"):
                    if sep in s:
                        parts = [p.strip() for p in s.split(sep, 1)]
                        if len(parts) == 2:
                            return f"{parts[0]},{parts[1]}"
            if "lat" in name and lat is None:
                lat = s.strip()
            if ("lon" in name or "lng" in name) and lon is None:
                lon = s.strip()
        if lat and lon:
            return f"{lat},{lon}"
        return ""

    def _build_sd_client(self, name: str, phone: str, address: str = "",
                         client_type: str = "retail", category: Dict = None,
                         location: str = "", agent: Optional[Dict] = None) -> Dict:
        """Build a Sales Doctor client dict with required fields.

        location: optional "lat,lon" comma-separated GPS string. If parseable,
        populates lat/lon for SD client (used for territory navigation).
        agent: optional {"SD_id": ...} or {"code_1C": ...} reference. Binds
        the client to its assigned SD agent so the courier app shows only
        relevant clients to that agent.
        """
        code = phone or name
        lat = ""
        lon = ""
        if location and "," in location:
            try:
                parts = [p.strip() for p in location.split(",", 1)]
                lat = parts[0]
                lon = parts[1] if len(parts) > 1 else ""
            except Exception:
                pass
        d: Dict = {
            "CS_id": "", "SD_id": "",
            "code_1C": code,
            "shortName": name,
            "firmName": name,
            "tel": phone,
            "address": address,
            "orentir": "", "comment": "",
            "lat": lat, "lon": lon,
            "active": "Y",
        }
        if category:
            d["clientCategory"] = category
        if agent:
            d["agent"] = agent
        return d

    async def _ensure_sd_warehouses(self, ms_wh_codes: List[str]):
        """Register MoySklad warehouse codes in Sales Doctor.

        SD warehouses start with code_1C=null. This sets the code_1C so that
        setStock calls can find the warehouse by code.
        """
        if not self.sd:
            return
        try:
            result = await self.sd._rpc("getWarehouse", {})
            sd_warehouses = result.get("warehouse", []) if isinstance(result, dict) else []
            if not sd_warehouses:
                return

            # Map existing SD warehouses: code_1C → warehouse dict
            by_code = {w.get("code_1C"): w for w in sd_warehouses if w.get("code_1C")}

            to_update = []
            for wh_code in ms_wh_codes:
                if wh_code not in by_code:
                    # Assign this code to the first unassigned SD warehouse
                    for w in sd_warehouses:
                        if not w.get("code_1C"):
                            to_update.append({
                                "CS_id": w.get("CS_id", ""),
                                "SD_id": w.get("SD_id", ""),
                                "code_1C": wh_code,
                                "name": w.get("name", "Основной склад"),
                                "active": "Y",
                            })
                            by_code[wh_code] = w
                            break

            if to_update:
                await self.sd._rpc("setWarehouse", {"warehouse": to_update})
        except Exception as e:
            logger.warning("SD warehouse setup failed: %s", e)

    # ========== Stock Sync ==========

    async def sync_stock(self):
        """Sync stock from MoySklad to local DB and Sales Doctor.

        Groups products by MoySklad warehouse and sends each warehouse
        to SD via setStock with the correct {"warehouse": [...]} format.
        """
        if not self.ms:
            return

        try:
            from utils.currency import convert_moysklad_price_to_uzs, detect_currency_iso
            current_rate = await get_usd_to_uzs_rate()

            # Ensure product → currency map is populated. The stock report doesn't
            # carry currency info, so we lean on the product sync's cache.
            product_currencies = SyncService._product_currencies.get(self.tenant.id) or {}
            if not product_currencies:
                # Trigger an early product sync so we know currencies before
                # converting stock prices. Throttle still applies inside.
                try:
                    await self.sync_products_to_salesdoctor()
                except Exception as e:
                    logger.warning("Early product sync for currency map failed: %s", e)
                product_currencies = SyncService._product_currencies.get(self.tenant.id) or {}

            import os
            force_currency = (
                SyncService._default_price_currency.get(self.tenant.id)
                or os.getenv("FORCE_PRICE_CURRENCY", "USD")
            ).upper()

            stock_rows = await self.ms.get_stock()
            synced = 0
            low_stock_items = []
            # warehouse_code_1C → list of SD product dicts
            wh_products: Dict[str, List[Dict]] = {}

            skipped_no_sku = 0
            for row in stock_rows:
                ms_id = row.get("id", "")
                sku = (row.get("code") or "").strip()
                if not sku:
                    # Don't fall back to MS UUID — it pollutes SD with opaque code_1C
                    skipped_no_sku += 1
                    continue
                name = row.get("name", "")
                qty = row.get("stock", 0)
                # MoySklad stock report returns salePrice in minor units.
                # We FORCE the configured currency (default USD) — MoySklad's
                # isoCode is ignored because this tenant's catalog is priced
                # in $ regardless of how MoySklad stores it.
                price_raw = row.get("salePrice", 0)
                price_uzs = convert_moysklad_price_to_uzs(price_raw, force_currency, current_rate)

                store = row.get("store", {})
                warehouse = store.get("name", "Основной склад")
                warehouse_id = store.get("id", "")
                wh_code = store.get("externalCode") or warehouse_id or "main"

                if qty > 0 and qty <= 5:
                    low_stock_items.append(f"{name} ({qty} шт.)")

                result = await self.db.execute(
                    select(StockItem).where(
                        StockItem.tenant_id == self.tenant.id,
                        StockItem.sku == sku,
                    )
                )
                item = result.scalar_one_or_none()

                if item:
                    item.qty = qty
                    item.price = price_uzs
                    item.name = name
                    item.warehouse = warehouse
                    item.moysklad_id = ms_id
                    item.last_sync = datetime.utcnow()
                else:
                    item = StockItem(
                        tenant_id=self.tenant.id,
                        moysklad_id=ms_id,
                        sku=sku,
                        name=name,
                        qty=qty,
                        price=price_uzs,
                        warehouse=warehouse,
                        warehouse_id=warehouse_id,
                    )
                    self.db.add(item)

                if sku:
                    wh_products.setdefault(wh_code, []).append({
                        "CS_id": "",
                        "SD_id": "",
                        "code_1C": sku,
                        "quantity": qty,
                        "price": price_uzs,
                    })

                synced += 1

            await self.db.commit()

            # Ensure SD warehouses are registered with proper code_1C
            if self.sd and wh_products:
                await self._ensure_sd_warehouses(list(wh_products.keys()))

            # Ensure products exist in SD before pushing stock
            if self.sd and wh_products:
                await self.sync_products_to_salesdoctor()

            # Push all stock to Sales Doctor grouped by warehouse
            if self.sd and wh_products:
                try:
                    sd_warehouses = [
                        {
                            "CS_id": "",
                            "SD_id": "",
                            "code_1C": wh_code,
                            "dont_zero_others": True,
                            "products": products,
                        }
                        for wh_code, products in wh_products.items()
                    ]
                    await self.sd.set_stock(sd_warehouses)
                except Exception as e:
                    logger.warning("SalesDoctor setStock failed: %s", e)

            msg = f"Synced {synced} stock items"
            if skipped_no_sku:
                msg += f" (skipped {skipped_no_sku} without SKU)"
            if low_stock_items:
                msg += f". Low stock: {', '.join(low_stock_items[:3])}"
            await self.log(LogType.SUCCESS, "Stock Sync", msg)

        except Exception as e:
            await self.log(LogType.ERROR, "Stock Sync", f"Error: {e}", retry_count=3)

    # ========== Debt Sync ==========

    async def sync_debts(self):
        """Sync debt information from MoySklad bulk report.

        Uses /report/counterparty (bulk) instead of per-counterparty calls
        to avoid rate-limiting. Batches all SD balance updates into one call.
        """
        if not self.ms:
            return

        try:
            # Bulk report — one call instead of N per counterparty
            all_rows: List[Dict] = []
            offset = 0
            while True:
                data = await self.ms._request(
                    "GET", "/report/counterparty",
                    params={"limit": 1000, "offset": offset}
                )
                rows = data.get("rows", [])
                all_rows.extend(rows)
                total = data.get("meta", {}).get("size", 0)
                offset += len(rows)
                if not rows or offset >= total:
                    break

            synced = 0
            sd_balances: List[Dict] = []

            for row in all_rows:
                cp = row.get("counterparty", {})
                cp_id = cp.get("id", "")
                name = cp.get("name", "")
                phone = (cp.get("phone") or "").strip()

                remaining = row.get("balance", 0) or 0
                total_debt = row.get("debt") or 0
                paid = row.get("paid") or 0

                result = await self.db.execute(
                    select(DebtRecord).where(
                        DebtRecord.tenant_id == self.tenant.id,
                        DebtRecord.client_phone == phone,
                    )
                )
                record = result.scalars().first()

                if record:
                    record.total_debt = total_debt
                    record.paid = paid
                    record.remaining = remaining
                    record.updated_at = datetime.utcnow()
                else:
                    record = DebtRecord(
                        tenant_id=self.tenant.id,
                        client_name=name,
                        client_phone=phone,
                        total_debt=total_debt,
                        paid=paid,
                        remaining=remaining,
                    )
                    self.db.add(record)

                client_result = await self.db.execute(
                    select(Client).where(
                        Client.tenant_id == self.tenant.id,
                        Client.phone == phone,
                    )
                )
                client = client_result.scalars().first()
                if client:
                    client.debt = remaining
                    client.total_paid = paid

                # Push every balance, including zero, so SD reflects paid-off debts
                if phone:
                    sd_balances.append({
                        "CS_id": "",
                        "SD_id": "",
                        "code_1C": phone,
                        "balance": remaining,
                        "paymentType": {"CS_id": "", "SD_id": "", "code_1C": "cash"},
                    })

                synced += 1

            await self.db.commit()

            # Batched calls to SD with delay to avoid 429 rate limit.
            # 1333 balances at batch=100 + 2s pause was still hitting SD's limits;
            # use smaller batches + longer cooldown, with adaptive backoff on 429.
            if self.sd and sd_balances:
                batch_size = 50
                base_pause = 4  # seconds between successful batches
                backoff = base_pause
                i = 0
                total = len(sd_balances)
                while i < total:
                    chunk = sd_balances[i:i + batch_size]
                    try:
                        await self.sd.set_current_balance(chunk)
                        i += batch_size
                        backoff = base_pause  # reset on success
                        if i < total:
                            await asyncio.sleep(base_pause)
                    except Exception as e:
                        msg = str(e)
                        is_rate_limited = "429" in msg or "Too Many" in msg
                        if is_rate_limited:
                            # Exponential backoff capped at 60s, then retry SAME chunk
                            backoff = min(backoff * 2, 60)
                            logger.warning(
                                "SD 429 on balance batch starting at %d — sleeping %ds before retry",
                                i, backoff,
                            )
                            await asyncio.sleep(backoff)
                            # do NOT advance i — retry the same chunk
                        else:
                            logger.warning(
                                "SalesDoctor balance sync failed (batch starting %d): %s", i, e
                            )
                            # Non-429 error: skip this batch to avoid infinite loop
                            i += batch_size
                            await asyncio.sleep(base_pause)

            await self.log(LogType.SUCCESS, "Debt Sync", f"Synced debts for {synced} clients")

        except Exception as e:
            await self.log(LogType.ERROR, "Debt Sync", f"Sync failed: {e}", retry_count=3)

    # ========== Delivery ==========

    async def create_delivery(self, order_id: str, courier_name: str) -> Optional[Delivery]:
        """Create delivery record when order is shipped."""
        try:
            result = await self.db.execute(
                select(Order).where(
                    Order.tenant_id == self.tenant.id,
                    Order.order_id == order_id
                )
            )
            order = result.scalar_one_or_none()

            if not order:
                await self.log(LogType.ERROR, "Delivery", f"Order {order_id} not found")
                return None

            delivery = Delivery(
                tenant_id=self.tenant.id,
                order_id=order.id,
                order_number=order.order_id,
                client_name=order.client_name,
                address=order.client.address if order.client else "",
                courier_name=courier_name,
                status="В пути",
            )
            self.db.add(delivery)
            await self.db.commit()

            await self.log(LogType.SUCCESS, "Delivery", f"Delivery created for {order_id}")
            return delivery

        except Exception as e:
            await self.log(LogType.ERROR, "Delivery", f"Failed: {e}")
            return None

    async def update_delivery_status(self, delivery_id: int, status: str):
        """Update delivery status and sync back to MoySklad."""
        try:
            result = await self.db.execute(
                select(Delivery).where(
                    Delivery.tenant_id == self.tenant.id,
                    Delivery.id == delivery_id
                )
            )
            delivery = result.scalar_one_or_none()

            if not delivery:
                await self.log(LogType.ERROR, "Delivery", f"Delivery {delivery_id} not found")
                return

            delivery.status = status
            if status == "Доставлен":
                delivery.delivered_at = datetime.utcnow()

            await self.db.commit()

            order_result = await self.db.execute(
                select(Order).where(Order.id == delivery.order_id)
            )
            order = order_result.scalar_one_or_none()

            if order and order.moysklad_id and self.ms:
                try:
                    # Map delivery status → MoySklad state name
                    delivery_to_ms_state = {
                        "В пути": "Отгружен",
                        "Доставлен": "Доставлен",
                        "Отказ": "Отменен",
                    }
                    ms_state_name = delivery_to_ms_state.get(status)
                    if ms_state_name:
                        # Find matching state from MoySklad metadata
                        states = await self.ms.get_states("customerorder")
                        matched = next((s for s in states if s.get("name") == ms_state_name), None)
                        if matched:
                            await self.ms.update_customer_order(
                                order.moysklad_id,
                                state={"meta": matched["meta"]},
                            )
                            # Sync status back to Sales Doctor too
                            from services.salesdoctor import MS_STATUS_TO_SD
                            sd_code = MS_STATUS_TO_SD.get(ms_state_name)
                            if self.sd and sd_code and order.order_id:
                                await self.sd.set_status(order.order_id, sd_code)
                except Exception as e:
                    await self.log(LogType.WARNING, "Delivery", f"MoySklad state update failed: {e}")

            await self.log(LogType.SUCCESS, "Delivery", f"Status: {status}")

        except Exception as e:
            await self.log(LogType.ERROR, "Delivery", f"Status update failed: {e}")
