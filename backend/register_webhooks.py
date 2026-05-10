"""One-time script: register MoySklad webhooks for all tenants with MS token."""

import asyncio
from database import AsyncSessionLocal, init_db
from models import Tenant
from sqlalchemy import select
from services.moysklad import MoySkladClient
from config import get_settings

settings = get_settings()


async def register_all():
    await init_db()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(
                Tenant.is_active == True,
                Tenant.moysklad_access_token != None,
            )
        )
        tenants = result.scalars().all()

        if not tenants:
            print("❌ No tenants with MoySklad token found")
            return

        base = (settings.public_base_url or "").rstrip("/")
        if not base or not base.startswith("https://"):
            print(f"❌ PUBLIC_BASE_URL not HTTPS: {base}")
            return

        target_url = f"{base}/api/webhook/moysklad"
        print(f"📡 Target URL: {target_url}")

        for tenant in tenants:
            print(f"\n🏢 Tenant: {tenant.name} (id={tenant.id})")
            client = MoySkladClient(token=tenant.moysklad_access_token)
            try:
                # Auto-discover accountId if missing
                if not tenant.moysklad_account_id:
                    account_id = await client.get_account_id()
                    if account_id:
                        tenant.moysklad_account_id = account_id
                        await db.commit()
                        print(f"   ✅ accountId discovered: {account_id}")

                result = await client.ensure_webhooks(target_url)
                print(f"   ✅ Created: {result['created']}")
                print(f"   ✅ Already existed: {result['existing']}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
            finally:
                await client.close()

    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(register_all())
