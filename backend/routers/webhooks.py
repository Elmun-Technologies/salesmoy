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
            await service.log(LogType.INFO, "Webhook", f"Counterparty {action}: {entity_id}")

        elif "demand" in entity_type:
            await service.log(LogType.INFO, "Webhook", f"Demand {action}: {entity_id}")

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


# ========== Health Check ==========


@router.get("/health")
async def webhook_health():
    """Webhook endpoint health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
