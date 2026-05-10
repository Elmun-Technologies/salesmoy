"""Billing module — disabled. Each client is configured individually."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/billing", tags=["Billing"])
