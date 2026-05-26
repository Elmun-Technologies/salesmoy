"""Webhook endpoints for MoySklad and Sales Doctor (Tenant-aware)."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import WebhookEvent, LogType, Tenant
from services.sync import SyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["Webhooks"])
# Authenticated management endpoints — separate router so they go through tenant auth.
mgmt_router = APIRouter(prefix="/api/integrations/moysklad", tags=["Integrations"])


# ========== MoySklad Webhooks ==========


@router.post("/moysklad")
async def moysklad_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive webhooks from MoySklad.

    MoySklad sends: {"accountId": "...", "events": [{"meta": {"type": "customerorder", "href": "..."}, "action": "CREATE", "updatedFields": [...]}]}
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw_body": (await request.body()).decode()}

    account_id = str(payload.get("accountId") or "").strip()
    if not account_id:
        logger.warning("MoySklad webhook missing accountId — ignored")
        return {"status": "ignored", "reason": "missing accountId"}

    result = await db.execute(
        select(Tenant).where(Tenant.moysklad_account_id == account_id)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        logger.warning("No tenant for MoySklad accountId=%s — event ignored", account_id)
        return {"status": "ignored", "reason": "unknown account"}

    events = payload.get("events", [])
    first_action = events[0].get("action", "unknown") if events else "unknown"

    event = WebhookEvent(
        tenant_id=tenant.id,
        source="moysklad",
        event_type=first_action,
        payload=payload,
    )
    db.add(event)
    await db.commit()

    service = SyncService(db, tenant)
    await service.init_clients()

    for evt in events:
        meta = evt.get("meta", {})
        entity_type = meta.get("type", "")
        action = evt.get("action", "")
        entity_href = meta.get("href", "")
        # Extract ID as the last path segment
        entity_id = entity_href.rstrip("/").split("/")[-1] if entity_href else ""

        if not entity_id:
            continue

        if "customerorder" in entity_type:
            if action == "CREATE":
                # New order in MoySklad → fetch full order → save & push to Sales Doctor
                try:
                    if service.ms:
                        ms_order = await service.ms.get_customer_order_with_positions(entity_id)
                        await service.process_moysklad_order(ms_order)
                except Exception as e:
                    logger.error("Failed to process new MoySklad order %s: %s", entity_id, e)
                    await service.log(LogType.ERROR, "Webhook", f"New order processing failed: {e}")

            elif action == "UPDATE":
                updated_fields = evt.get("updatedFields", [])
                if "state" in updated_fields:
                    try:
                        if service.ms:
                            # Use expanded fetch so state.name is available (not just meta href)
                            ms_order = await service.ms.get_customer_order_with_positions(entity_id)
                            state = ms_order.get("state", {})
                            state_name = state.get("name", "") if isinstance(state, dict) else ""
                            if state_name:
                                await service.update_order_status_from_moysklad(entity_id, state_name)
                    except Exception as e:
                        logger.error("Failed to update order status %s: %s", entity_id, e)

        elif "counterparty" in entity_type:
            # Mijoz MS'da yaratildi/yangilandi → SD'ga push (yangi GPS bilan ham)
            try:
                if service.ms and action in ("CREATE", "UPDATE"):
                    # Counterparty fetch without expand returns attributes for free —
                    # we need them for GPS extraction.
                    cp = await service.ms.get_counterparty(entity_id)
                    cp_name = (cp.get("name") or "").strip()
                    # Canonicalize so this counterparty maps to the same local
                    # row regardless of how the operator typed the phone in MS.
                    from utils.phone import normalize_phone as _np
                    cp_phone = _np(cp.get("phone") or "")
                    address = service._ms_address(cp)
                    gps = service._extract_gps_from_ms_counterparty(cp)
                    if cp_name:
                        # Local DB ga upsert
                        from sqlalchemy import select as sa_select
                        from models import Client, ClientType
                        from datetime import datetime
                        local = None
                        if cp_phone:
                            r = await service.db.execute(sa_select(Client).where(
                                Client.tenant_id == tenant.id,
                                Client.phone == cp_phone,
                                Client.is_duplicate == False))
                            local = r.scalars().first()
                        if not local:
                            local = Client(tenant_id=tenant.id, name=cp_name, phone=cp_phone)
                            service.db.add(local)
                        local.moysklad_id = entity_id
                        local.name = cp_name
                        local.address = address or local.address
                        # Persist GPS locally too so the dashboard / API
                        # reflects it without waiting for the next 5-min
                        # bulk client sync.
                        if gps:
                            local.location = gps
                        await service.db.commit()
                        # SD ga push — agent binding + GPS bilan
                        if service.sd:
                            category = await service._get_sd_category_id("retail")
                            agent_ref = await service._resolve_agent_for_ms_owner(cp.get("owner"))
                            sd_client = service._build_sd_client(
                                name=cp_name, phone=cp_phone,
                                address=address,
                                client_type="retail", category=category,
                                location=gps, agent=agent_ref,
                            )
                            try:
                                await service.sd.set_client([sd_client])
                            except Exception as e:
                                await service.log(LogType.WARNING, "Webhook", f"SD setClient failed: {e}")
                    msg = f"Counterparty {action} → SD: {cp_name}"
                    if gps:
                        msg += f" (GPS: {gps})"
                    await service.log(LogType.SUCCESS, "Webhook", msg)
            except Exception as e:
                await service.log(LogType.ERROR, "Webhook", f"Counterparty {action} failed: {e}")

        elif "demand" in entity_type:
            # Demand (отгрузка) yaratildi/yangilandi:
            # 1) Buyurtma statusini "Отгружен" ga o'tkazamiz
            # 2) Demand atributlaridan GPS o'qib SD klientini yangilaymiz
            try:
                if service.ms and action in ("CREATE", "UPDATE"):
                    demand = await service.ms._request(
                        "GET", f"/entity/demand/{entity_id}",
                        params={"expand": "customerOrder,agent"},
                    )

                    # --- 1) Order status update ---
                    co = demand.get("customerOrder") or {}
                    co_id = co.get("id") if isinstance(co, dict) else ""
                    if co_id and action == "CREATE":
                        await service.update_order_status_from_moysklad(co_id, "Отгружен")

                    # --- 2) GPS extraction from demand attributes → SD client ---
                    if service.sd:
                        attrs = demand.get("attributes") or []
                        gps_str = ""
                        for attr in attrs:
                            if not isinstance(attr, dict):
                                continue
                            name = (attr.get("name") or "").strip().lower()
                            if name == "gps" or "gps" in name or "координат" in name:
                                raw = str(attr.get("value") or "").strip()
                                gps_str = service._parse_gps_from_string(raw)
                                if gps_str:
                                    break

                        if gps_str:
                            # Get client info from demand's agent (counterparty)
                            agent = demand.get("agent") or {}
                            client_name = agent.get("name", "") if isinstance(agent, dict) else ""
                            client_phone = agent.get("phone", "") if isinstance(agent, dict) else ""
                            client_code = client_phone or client_name
                            address = service._ms_address(agent) if isinstance(agent, dict) else ""

                            if client_code:
                                try:
                                    category = await service._get_sd_category_id("retail")
                                    owner = agent.get("owner") if isinstance(agent, dict) else None
                                    agent_ref = await service._resolve_agent_for_ms_owner(owner)
                                    sd_client = service._build_sd_client(
                                        name=client_name or client_code,
                                        phone=client_phone,
                                        address=address,
                                        client_type="retail",
                                        category=category,
                                        location=gps_str,
                                        agent=agent_ref,
                                    )
                                    await service.sd.set_client([sd_client])
                                    await service.log(
                                        LogType.SUCCESS, "Webhook",
                                        f"Demand GPS → SD client {client_code}: {gps_str}",
                                    )
                                except Exception as e:
                                    await service.log(LogType.WARNING, "Webhook",
                                                      f"Demand GPS setClient failed: {e}")

                await service.log(LogType.SUCCESS, "Webhook", f"Demand {action}: {entity_id}")
            except Exception as e:
                await service.log(LogType.ERROR, "Webhook", f"Demand {action} failed: {e}")

    event.processed = True
    event.processed_at = datetime.utcnow()
    await db.commit()

    return {"status": "ok"}


# ========== Sales Doctor Webhooks ==========


@router.post("/salesdoctor")
async def salesdoctor_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive webhooks from Sales Doctor."""
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw_body": (await request.body()).decode()}

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        logger.warning("Sales Doctor webhook missing tenant_id")
        return {"status": "ignored", "reason": "tenant_id required"}

    result = await db.execute(select(Tenant).where(Tenant.id == int(tenant_id)))
    tenant = result.scalar_one_or_none()

    if not tenant:
        logger.warning("Sales Doctor webhook unknown tenant_id=%s", tenant_id)
        return {"status": "ignored", "reason": "unknown tenant"}

    # Log the event
    event = WebhookEvent(
        tenant_id=tenant.id,
        source="salesdoctor",
        event_type=payload.get("event", "unknown"),
        payload=payload,
    )
    db.add(event)
    await db.commit()

    # Process the event
    service = SyncService(db, tenant)
    await service.init_clients()

    event_type = payload.get("event", "")
    data = payload.get("data", {})

    if event_type == "order.created":
        await service.create_order_in_moysklad(data)
    elif event_type == "order.updated":
        order_id = data.get("order_id", "")
        status = data.get("status", "")
        if order_id and status:
            await service.update_order_status_from_moysklad(order_id, status)
    elif event_type == "delivery.status_changed":
        delivery_id = data.get("delivery_id")
        status = data.get("status", "")
        if delivery_id and status:
            await service.update_delivery_status(delivery_id, status)
    elif event_type == "client.updated":
        await service.sync_client_to_moysklad(data)

    event.processed = True
    event.processed_at = datetime.utcnow()
    await db.commit()

    return {"status": "ok"}


# ========== Tenant-facing webhook management ==========


@mgmt_router.get("/webhook/status")
async def moysklad_webhook_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Show whether MoySklad webhooks are registered for this tenant."""
    from config import get_settings
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        return {"connected": False, "reason": "not authenticated"}

    result = await db.execute(select(Tenant).where(Tenant.id == int(tenant_id)))
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.moysklad_access_token:
        return {"connected": False, "reason": "MoySklad not connected"}

    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    target = f"{base}/webhook/moysklad" if base else None

    from services.moysklad import MoySkladClient
    client = MoySkladClient(token=tenant.moysklad_access_token)
    try:
        existing = await client.list_webhooks()
    finally:
        await client.close()

    matching = [w for w in existing if target and w.get("url") == target]
    return {
        "connected": bool(matching),
        "public_base_url": base,
        "target_url": target,
        "registered_count": len(matching),
        "registered": [
            {"id": w.get("id"), "entityType": w.get("entityType"),
             "action": w.get("action"), "enabled": w.get("enabled")}
            for w in matching
        ],
        "all_webhooks_count": len(existing),
    }


@mgmt_router.post("/webhook/register")
async def moysklad_webhook_register(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register the standard set of MoySklad webhooks for this tenant.

    Idempotent — existing webhooks for the same URL are kept.
    Requires PUBLIC_BASE_URL to be set (HTTPS) in server config.
    """
    from config import get_settings
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        return {"success": False, "error": "Not authenticated"}

    result = await db.execute(select(Tenant).where(Tenant.id == int(tenant_id)))
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.moysklad_access_token:
        return {"success": False, "error": "MoySklad not connected for this tenant"}

    settings = get_settings()
    base = (settings.public_base_url or "").rstrip("/")
    if not base or not base.startswith("https://"):
        return {
            "success": False,
            "error": "PUBLIC_BASE_URL not configured or not HTTPS — set it in server .env",
            "current": base or None,
        }
    target_url = f"{base}/webhook/moysklad"

    from services.moysklad import MoySkladClient
    client = MoySkladClient(token=tenant.moysklad_access_token)
    try:
        # Persist accountId on first registration
        if not tenant.moysklad_account_id:
            account_id = await client.get_account_id()
            if account_id:
                tenant.moysklad_account_id = account_id
                await db.commit()

        result = await client.ensure_webhooks(target_url)
    finally:
        await client.close()

    return {
        "success": True,
        "target_url": target_url,
        "created": result["created"],
        "already_existed": result["existing"],
    }


@mgmt_router.delete("/webhook/unregister")
async def moysklad_webhook_unregister(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Remove all webhooks pointing at our public URL for this tenant."""
    from config import get_settings
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        return {"success": False, "error": "Not authenticated"}

    result = await db.execute(select(Tenant).where(Tenant.id == int(tenant_id)))
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.moysklad_access_token:
        return {"success": False, "error": "MoySklad not connected"}

    settings = get_settings()
    base = (settings.public_base_url or "").rstrip("/")
    target_url = f"{base}/webhook/moysklad" if base else None

    from services.moysklad import MoySkladClient
    client = MoySkladClient(token=tenant.moysklad_access_token)
    removed = []
    try:
        existing = await client.list_webhooks()
        for w in existing:
            if target_url and w.get("url") == target_url:
                try:
                    await client.delete_webhook(w["id"])
                    removed.append({"id": w["id"], "entityType": w.get("entityType"),
                                    "action": w.get("action")})
                except Exception as e:
                    logger.warning("MS webhook delete failed: %s", e)
    finally:
        await client.close()
    return {"success": True, "removed": removed}


# ========== Health Check ==========


@router.get("/health")
async def webhook_health():
    """Webhook endpoint health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
