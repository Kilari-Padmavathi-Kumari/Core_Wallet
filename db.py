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


def init_db() -> None:
    logger.info("db_init_started")
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS wallets (
                    id BIGSERIAL PRIMARY KEY,
                    user_id TEXT UNIQUE NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    balance NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (balance >= 0),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_entries (
                    id BIGSERIAL PRIMARY KEY,
                    wallet_id BIGINT NOT NULL REFERENCES wallets(id) ON DELETE CASCADE,
                    entry_type TEXT NOT NULL CHECK (entry_type IN ('credit', 'debit')),
                    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
                    balance_after NUMERIC(18,2) NOT NULL CHECK (balance_after >= 0),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ledger_wallet_created_at
                ON ledger_entries(wallet_id, created_at DESC);
                """
            )
            # Normalize legacy schema to text-based user_id with timestamp.
            cur.execute("ALTER TABLE wallets DROP CONSTRAINT IF EXISTS wallets_user_id_fkey;")
            cur.execute(
                """
                ALTER TABLE users
                ALTER COLUMN user_id TYPE TEXT
                USING user_id::text;
                """
            )
            cur.execute("ALTER TABLE users ALTER COLUMN user_id SET NOT NULL;")
            cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();"
            )
            cur.execute("UPDATE users SET created_at = NOW() WHERE created_at IS NULL;")
            cur.execute("ALTER TABLE users ALTER COLUMN created_at SET NOT NULL;")
            cur.execute("ALTER TABLE users DROP COLUMN IF EXISTS id;")
            cur.execute(
                """
                ALTER TABLE wallets
                ALTER COLUMN user_id TYPE TEXT
                USING user_id::text;
                """
            )
            cur.execute("ALTER TABLE wallets DROP CONSTRAINT IF EXISTS wallets_user_id_key;")
            cur.execute("ALTER TABLE wallets ADD CONSTRAINT wallets_user_id_key UNIQUE (user_id);")
            cur.execute(
                """
                ALTER TABLE wallets
                ADD CONSTRAINT wallets_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;
                """
            )
        conn.commit()
    logger.info("db_init_completed")


def db_healthcheck() -> bool:
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return True
    except Exception:
        logger.exception("db_healthcheck_failed")
        return False
