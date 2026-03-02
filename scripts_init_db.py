import os
from urllib.parse import urlparse, urlunparse

import psycopg
from dotenv import load_dotenv
from psycopg import sql

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql://postgres:localhost@localhost:5432/walletdb"


def build_admin_url(database_url: str) -> str:
    """
    Build admin URL from DATABASE_URL.
    Example:
    postgresql://postgres:pass@localhost:5432/walletdb
    -> postgresql://postgres:pass@localhost:5432/postgres
    """
    parsed = urlparse(database_url)
    if not parsed.path or parsed.path == "/":
        raise RuntimeError("DATABASE_URL must contain a database name")
    return urlunparse(parsed._replace(path="/postgres"))


database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
db_name = urlparse(database_url).path.lstrip("/")
if not db_name:
    raise RuntimeError("DATABASE_URL must contain a database name")

admin_url = build_admin_url(database_url)

with psycopg.connect(admin_url, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            print(f"created database: {db_name}")
        else:
            print(f"database already exists: {db_name}")
