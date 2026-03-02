import os
from urllib.parse import urlparse

import psycopg
from dotenv import load_dotenv
from psycopg import sql

load_dotenv()
DEFAULT_ADMIN_URL = "postgresql://postgres:localhost@localhost:5432/postgres"
DEFAULT_DATABASE_URL = "postgresql://postgres:localhost@localhost:5432/walletdb"

admin_url = os.getenv("POSTGRES_ADMIN_URL", DEFAULT_ADMIN_URL)
database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

db_name = urlparse(database_url).path.lstrip("/")
if not db_name:
    raise RuntimeError("DATABASE_URL must contain a database name")

with psycopg.connect(admin_url, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            print(f"created database: {db_name}")
        else:
            print(f"database already exists: {db_name}")
