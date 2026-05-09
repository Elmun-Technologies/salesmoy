"""Seed database with demo data for testing."""

import asyncio
from datetime import datetime, timedelta

from database import AsyncSessionLocal, init_db
from models import Tenant, User, SubscriptionPlan
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_demo_data():
    """Create demo tenant and user."""
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # Check if demo tenant exists
        from sqlalchemy import select
        result = await db.execute(select(Tenant).where(Tenant.slug == "demo"))
        existing = result.scalar_one_or_none()
        
        if existing:
            print("✅ Demo data already exists")
            print(f"   Company: {existing.name}")
            print(f"   Slug: {existing.slug}")
            print(f"   Login: demo@example.com")
            print(f"   Password: demo123")
            return
        
        # Create demo tenant
        tenant = Tenant(
            name="Demo Kompaniya",
            slug="demo",
            email="demo@example.com",
            phone="+998 90 123 45 67",
            plan=SubscriptionPlan.PRO,
            is_active=True,
            is_trial=True,
            trial_ends_at=datetime.utcnow() + timedelta(days=30),
            max_orders_monthly=5000,
            max_users=15,
            sync_interval_seconds=15,
            moysklad_access_token=None,
            salesdoctor_base_url=None,
            salesdoctor_user_id=None,
            salesdoctor_token=None,
            salesdoctor_filial_id=0,
        )
        db.add(tenant)
        await db.flush()
        
        # Create demo admin user
        admin = User(
            tenant_id=tenant.id,
            email="demo@example.com",
            hashed_password=pwd_context.hash("demo123"),
            full_name="Demo Admin",
            role="admin",
            is_active=True,
        )
        db.add(admin)
        
        # Create demo agent user
        agent = User(
            tenant_id=tenant.id,
            email="agent@example.com",
            hashed_password=pwd_context.hash("demo123"),
            full_name="Demo Agent",
            role="agent",
            is_active=True,
        )
        db.add(agent)
        
        await db.commit()
        
        print("✅ Demo data created successfully!")
        print("")
        print("🔑 DEMO LOGIN CREDENTIALS:")
        print("   Company Slug: demo")
        print("   Email:        demo@example.com")
        print("   Password:     demo123")
        print("")
        print("   Agent Login:")
        print("   Email:        agent@example.com")
        print("   Password:     demo123")
        print("")
        print("   Trial: 30 days (Pro plan)")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
