import os
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Wallet Ledger Service")
APP_VERSION = os.getenv("APP_VERSION", "1.1.0")
APP_ENV = os.getenv("APP_ENV", "development")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:localhost@localhost:5432/walletdb"
)
MONEY_QUANT = Decimal("0.01")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
DB_POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "30"))
