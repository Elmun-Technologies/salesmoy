"""Core synchronization logic between MoySklad and Sales Doctor (Tenant-aware)."""

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

logger = logging.getLogger(__name__)


class SyncService:
    """Main synchronization service with tenant isolation."""

    # Class-level: tracks last product sync time per tenant to avoid spamming SD
    _last_product_sync: Dict[int, datetime] = {}
    PRODUCT_SYNC_INTERVAL_SECONDS = 3600  # sync products to SD once per hour max

    def __init__(self, db: AsyncSession, tenant: Tenant):
        self.db = db
        self.tenant = tenant
        self.ms = None
        self.sd = None

    async def init_clients(self):
        """Initialize API clients with tenant credentials."""
        if self.tenant.moysklad_access_token:
            self.ms = MoySkladClient(token=self.tenant.moysklad_access_token)

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

            # Sync client to Sales Doctor (exact SD API field names)
            if self.sd:
                try:
                    sd_client = {
                        "CS_id": "",
                        "SD_id": "",
                        "code_1C": phone or ms_client.get("id", ""),
                        "shortName": name,
                        "firmName": name,
                        "address": client_data.get("address", ""),
                        "orentir": "",
                        "tel": phone,
                        "comment": "",
                        "lat": str(client_data.get("lat", "")),
                        "lon": str(client_data.get("lon", "")),
                        "active": "Y",
                    }
                    await self.sd.set_client([sd_client])
                except Exception as e:
                    logger.warning("SalesDoctor setClient failed: %s", e)

            return client

        except Exception as e:
            await self.log(LogType.ERROR, "Client Sync", f"Failed: {e}")
            return None

    async def sync_clients_from_moysklad(self):
        """Pull all clients from MoySklad to local DB, merging duplicates by phone."""
        if not self.ms:
            return

        try:
            counterparties = await self.ms.get_counterparties()
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
                    by_phone = r.scalar_one_or_none()

                r = await self.db.execute(
                    select(Client).where(
                        Client.tenant_id == self.tenant.id,
                        Client.name == name,
                        Client.is_duplicate == False,
                    )
                )
                by_name = r.scalar_one_or_none()

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
            msg = f"Synced {synced} clients"
            if merged:
                msg += f", merged {merged} duplicates"
            await self.log(LogType.SUCCESS, "Client Sync", msg)

        except Exception as e:
            await self.log(LogType.ERROR, "Client Sync", f"Failed: {e}")

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

        # Parse counterparty (client)
        agent_data = ms_order.get("agent", {})
        client_name = agent_data.get("name", "")
        client_phone = agent_data.get("phone", "") or agent_data.get("actualPhone", "")

        order_name = ms_order.get("name", ms_id[:8])
        total = ms_order.get("sum", 0) / 100
        description = ms_order.get("description", "")
        state_name = ms_order.get("state", {}).get("name", "Новый") if isinstance(ms_order.get("state"), dict) else "Новый"

        # Parse positions
        items: List[Dict] = []
        positions_block = ms_order.get("positions", {})
        if isinstance(positions_block, dict):
            for pos in positions_block.get("rows", []):
                assortment = pos.get("assortment", {})
                items.append({
                    "name": assortment.get("name", ""),
                    "sku": assortment.get("code", ""),
                    "qty": pos.get("quantity", 1),
                    "price": pos.get("price", 0) / 100,
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
            sync_status=SyncStatus.SYNCED,
            items=items,
            raw_data={"source": "moysklad", "state": state_name},
            synced_at=datetime.utcnow(),
        )
        self.db.add(order)

        # Push to Sales Doctor via setOrder (using exact SD API field names)
        if self.sd:
            try:
                order_products = [
                    {
                        "product": {"code_1C": item.get("sku", "")},
                        "quantity": item.get("qty", 1),
                        "price": item.get("price", 0),
                        "discountSumma": 0,
                    }
                    for item in items
                    if item.get("sku")
                ]
                sd_order = {
                    "CS_id": "",
                    "SD_id": "",
                    "code_1C": order_name,
                    "comment": description,
                    "status": MS_STATUS_TO_SD.get(state_name, 1),
                    "client": {"code_1C": client_phone or client_name},
                    "orderProducts": order_products,
                }
                resp = await self.sd.set_order([sd_order])
                # SD may return assigned IDs in the response; store code_1C as salesdoctor_id for now
                order.salesdoctor_id = order_name
            except Exception as e:
                logger.warning("Could not push order %s to Sales Doctor: %s", order_name, e)

        await self.db.commit()
        await self.log(LogType.SUCCESS, "Order Sync", f"MoySklad order {order_name} → Sales Doctor", order.id)
        return order

    async def sync_orders_from_moysklad(self):
        """Pull recent orders from MoySklad, save new ones to DB and push to Sales Doctor.

        Fetches the order list first (no expand), then fetches positions individually
        only for orders not yet in DB — avoids MoySklad list-expand limitations.
        """
        if not self.ms:
            return

        try:
            # Get basic order list (no expand — list endpoint doesn't reliably expand positions)
            ms_orders = await self.ms.get_customer_orders(limit=100, expand=False)
            synced = 0

            for ms_order_brief in ms_orders:
                ms_id = ms_order_brief.get("id", "")
                if not ms_id:
                    continue

                # Skip if already in DB
                result = await self.db.execute(
                    select(Order).where(
                        Order.tenant_id == self.tenant.id,
                        Order.moysklad_id == ms_id,
                    )
                )
                if result.scalar_one_or_none():
                    continue

                # Fetch full order with positions expanded (single-order endpoint supports this)
                try:
                    ms_order_full = await self.ms.get_customer_order_with_positions(ms_id)
                    order = await self.process_moysklad_order(ms_order_full)
                    if order:
                        synced += 1
                except Exception as e:
                    logger.warning("Could not fetch full order %s: %s", ms_id, e)
                    continue

            if synced > 0:
                await self.log(LogType.SUCCESS, "Order Sync", f"Synced {synced} new orders from MoySklad")

        except Exception as e:
            await self.log(LogType.ERROR, "Order Sync", f"sync_orders_from_moysklad failed: {e}")

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
            if self.tenant.max_orders_monthly > 0 and order_count.scalar() >= self.tenant.max_orders_monthly:
                await self.log(LogType.WARNING, "Order Sync", "Monthly order limit reached")
                return None

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
                    "price": item.get("price", 0) * 100,
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

            order.status = status_map.get(new_status, order.status)
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
            ms_products = await self.ms.get_products(limit=1000)
            if not ms_products:
                return

            sd_products = []
            for p in ms_products:
                code = p.get("code", "")
                name = p.get("name", "")
                if not code or not name:
                    continue
                sd_products.append({
                    "CS_id": "",
                    "SD_id": "",
                    "code_1C": code,
                    "name": name,
                    "active": 1,
                    "sort": 500,
                    "volume": p.get("volume", 0.0),
                    "packQuantity": p.get("buyPrice", {}).get("value", 1.0) if isinstance(p.get("buyPrice"), dict) else 1.0,
                    "barCode": "",
                    "weight": p.get("weight", 0.0),
                    "part_number": "",
                })

            # Send in batches of 100
            batch_size = 100
            for i in range(0, len(sd_products), batch_size):
                batch = sd_products[i:i + batch_size]
                try:
                    await self.sd.set_product(batch)
                except Exception as e:
                    logger.warning("setProduct batch %d failed: %s", i // batch_size, e)

            await self.log(LogType.INFO, "Product Sync", f"Synced {len(sd_products)} products to Sales Doctor")

        except Exception as e:
            logger.warning("sync_products_to_salesdoctor failed: %s", e)

    # ========== Stock Sync ==========

    async def sync_stock(self):
        """Sync stock from MoySklad to local DB and Sales Doctor.

        Groups products by MoySklad warehouse and sends each warehouse
        to SD via setStock with the correct {"warehouse": [...]} format.
        """
        if not self.ms:
            return

        try:
            stock_rows = await self.ms.get_stock()
            synced = 0
            low_stock_items = []
            # warehouse_code_1C → list of SD product dicts
            wh_products: Dict[str, List[Dict]] = {}

            for row in stock_rows:
                ms_id = row.get("id", "")
                sku = row.get("code", "") or ms_id  # fallback to MS id if no SKU
                if not sku:
                    continue
                name = row.get("name", "")
                qty = row.get("stock", 0)
                price = row.get("salePrice", 0) / 100
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
                    item.price = price
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
                        price=price,
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
                    })

                synced += 1

            await self.db.commit()

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
            if low_stock_items:
                msg += f". Low stock: {', '.join(low_stock_items[:3])}"
            await self.log(LogType.SUCCESS, "Stock Sync", msg)

        except Exception as e:
            await self.log(LogType.ERROR, "Stock Sync", f"Error: {e}", retry_count=3)

    # ========== Debt Sync ==========

    async def sync_debts(self):
        """Sync debt information from MoySklad."""
        if not self.ms:
            return

        try:
            counterparties = await self.ms.get_counterparties()
            synced = 0

            for cp in counterparties:
                cp_id = cp.get("id")
                name = cp.get("name", "")
                phone = cp.get("phone", "")

                try:
                    report = await self.ms.get_counterparty_report(cp_id)
                    debt_data = report.get("rows", [{}])[0] if report.get("rows") else {}

                    total_debt = debt_data.get("debt", 0)
                    paid = debt_data.get("paid", 0)
                    remaining = debt_data.get("balance", total_debt - paid)

                    result = await self.db.execute(
                        select(DebtRecord).where(
                            DebtRecord.tenant_id == self.tenant.id,
                            DebtRecord.client_phone == phone
                        )
                    )
                    record = result.scalar_one_or_none()

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
                            Client.phone == phone
                        )
                    )
                    client = client_result.scalar_one_or_none()
                    if client:
                        client.debt = remaining
                        client.total_paid = paid

                    if self.sd and phone:
                        try:
                            # Update current balance (shows debt in SD)
                            await self.sd.set_current_balance([{
                                "CS_id": "",
                                "SD_id": "",
                                "code_1C": phone,
                                "balance": remaining,
                                "paymentType": {
                                    "CS_id": "",
                                    "SD_id": "",
                                    "code_1C": "Наличные",
                                },
                            }])
                            # If payment received (paid > 0), record as income transaction
                            if paid > 0:
                                await self.sd.set_consumption([{
                                    "CS_id": "",
                                    "SD_id": "",
                                    "code_1C": f"pay-{phone}-{cp_id[:8]}",
                                    "name": f"Тўлов: {name}",
                                    "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
                                    "comment": f"MoySkladdan синхрон",
                                    "summa": paid,
                                    "type": "income",
                                    "paymentType": {
                                        "CS_id": "",
                                        "SD_id": "",
                                        "code_1C": "Наличные",
                                    },
                                    "cashbox": {
                                        "CS_id": "",
                                        "SD_id": "",
                                        "code_1C": "",
                                    },
                                }])
                        except Exception as e:
                            logger.warning("SalesDoctor Касса sync failed: %s", e)

                    synced += 1

                except Exception as e:
                    logger.warning(f"Report failed for {name}: {e}")
                    continue

            await self.db.commit()
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
