import logging

from psycopg_pool import ConnectionPool

from config import DATABASE_URL, DB_POOL_MAX_SIZE, DB_POOL_MIN_SIZE, DB_POOL_TIMEOUT

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    open=False,
    min_size=DB_POOL_MIN_SIZE,
    max_size=DB_POOL_MAX_SIZE,
    timeout=DB_POOL_TIMEOUT,
)
logger = logging.getLogger("wallet.db")

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS wallets (
        id BIGSERIAL PRIMARY KEY,
        user_id TEXT UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        balance NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (balance >= 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ledger_entries (
        id BIGSERIAL PRIMARY KEY,
        wallet_id BIGINT NOT NULL REFERENCES wallets(id) ON DELETE CASCADE,
        entry_type TEXT NOT NULL CHECK (entry_type IN ('credit', 'debit')),
        amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
        balance_after NUMERIC(18,2) NOT NULL CHECK (balance_after >= 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ledger_wallet_created_at
    ON ledger_entries(wallet_id, created_at DESC);
    """,
]


def init_db() -> None:
    """
    Create tables and index needed for wallet operations.
    Safe to run multiple times (idempotent).
    """
    logger.info("db_init_started")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            for index, statement in enumerate(SCHEMA_STATEMENTS, start=1):
                logger.debug("db_init_statement_%s", index)
                cur.execute(statement)
        conn.commit()
    logger.info("db_init_completed")


def db_healthcheck() -> bool:
    """Return True if DB can be queried, else False."""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return True
    except Exception:
        logger.exception("db_healthcheck_failed")
        return False
