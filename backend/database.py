"""Database configuration and session management."""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings

settings = get_settings()

# Convert sqlite URL to aiosqlite for async support
database_url = settings.database_url
if database_url.startswith("sqlite:///"):
    database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

async_engine = create_async_engine(
    database_url,
    echo=settings.debug,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


async def _patch_schema():
    """Add columns introduced after first deploy (SQLite / Postgres)."""
    from sqlalchemy import text

    dialect = async_engine.dialect.name
    async with async_engine.begin() as conn:
        if dialect == "sqlite":
            r = await conn.execute(text("PRAGMA table_info(payments)"))
            payment_cols = [row[1] for row in r.fetchall()]
            if payment_cols and "plan_slug" not in payment_cols:
                await conn.execute(text("ALTER TABLE payments ADD COLUMN plan_slug VARCHAR(50)"))

            r = await conn.execute(text("PRAGMA table_info(tenants)"))
            tenant_cols = [row[1] for row in r.fetchall()]
            if tenant_cols:
                new_cols = {
                    "salesdoctor_base_url": "VARCHAR(255)",
                    "salesdoctor_login": "VARCHAR(255)",
                    "salesdoctor_password": "TEXT",
                    "salesdoctor_user_id": "VARCHAR(100)",
                    "salesdoctor_token": "TEXT",
                    "salesdoctor_filial_id": "INTEGER DEFAULT 0",
                }
                for col, col_type in new_cols.items():
                    if col not in tenant_cols:
                        await conn.execute(text(f"ALTER TABLE tenants ADD COLUMN {col} {col_type}"))

        elif dialect == "postgresql":
            await conn.execute(
                text("ALTER TABLE payments ADD COLUMN IF NOT EXISTS plan_slug VARCHAR(50)")
            )
            pg_new = {
                "salesdoctor_base_url": "VARCHAR(255)",
                "salesdoctor_login": "VARCHAR(255)",
                "salesdoctor_password": "TEXT",
                "salesdoctor_user_id": "VARCHAR(100)",
                "salesdoctor_token": "TEXT",
                "salesdoctor_filial_id": "INTEGER DEFAULT 0",
            }
            for col, col_type in pg_new.items():
                await conn.execute(
                    text(f"ALTER TABLE tenants ADD COLUMN IF NOT EXISTS {col} {col_type}")
                )


async def init_db():
    """Initialize database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _patch_schema()


async def get_db():
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
