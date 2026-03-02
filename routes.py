import logging

from fastapi import APIRouter, HTTPException, Query
from psycopg.rows import dict_row

from db import pool
from schemas import (
    CreateUserRequest,
    CreateWalletRequest,
    LedgerEntryResponse,
    MoneyRequest,
    UserResponse,
    WalletBalanceResponse,
    WalletMutationResponse,
)

logger = logging.getLogger("wallet.routes")
router = APIRouter()


@router.post("/users", response_model=UserResponse, status_code=201, tags=["users"])
def create_user(payload: CreateUserRequest) -> UserResponse:
    user_id_str = payload.user_id
    logger.info("create_user_requested user_id=%s", user_id_str)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO users (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                RETURNING user_id, created_at;
                """,
                (user_id_str,),
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        logger.warning("create_user_conflict user_id=%s", user_id_str)
        raise HTTPException(status_code=409, detail="user already exists")

    logger.info("create_user_success user_id=%s", user_id_str)
    return UserResponse(**row)


@router.get("/users", response_model=list[UserResponse], tags=["users"])
def list_users(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[UserResponse]:
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT user_id, created_at
                FROM users
                ORDER BY created_at DESC, user_id DESC
                LIMIT %s OFFSET %s;
                """,
                (limit, offset),
            )
            rows = cur.fetchall()

    return [UserResponse(**row) for row in rows]


@router.get("/users/{user_id}", response_model=UserResponse, tags=["users"])
def get_user(user_id: str) -> UserResponse:
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT user_id, created_at FROM users WHERE user_id = %s;",
                (user_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    return UserResponse(**row)


@router.post("/wallets", response_model=WalletBalanceResponse, status_code=201, tags=["wallet"])
def create_wallet(payload: CreateWalletRequest) -> WalletBalanceResponse:
    user_id_str = str(payload.user_id)
    logger.info("create_wallet_requested user_id=%s", user_id_str)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT 1 FROM users WHERE user_id = %s;
                """,
                (user_id_str,),
            )
            user_exists = cur.fetchone()
            if user_exists is None:
                conn.rollback()
                logger.warning("create_wallet_user_not_found user_id=%s", user_id_str)
                raise HTTPException(status_code=404, detail="user not found")

            cur.execute(
                """
                INSERT INTO wallets (user_id, balance)
                VALUES (%s, 0)
                ON CONFLICT (user_id) DO NOTHING
                RETURNING user_id, balance, created_at;
                """,
                (user_id_str,),
            )
            row = cur.fetchone()
            conn.commit()

    if row is None:
        logger.warning("create_wallet_conflict user_id=%s", user_id_str)
        raise HTTPException(status_code=409, detail="wallet already exists")

    logger.info("create_wallet_success user_id=%s", user_id_str)
    return WalletBalanceResponse(**row)


@router.post("/wallets/{user_id}/credit", response_model=WalletMutationResponse, tags=["wallet"])
def credit_wallet(user_id: str, payload: MoneyRequest) -> WalletMutationResponse:
    user_id_str = user_id
    logger.info("credit_requested user_id=%s amount=%s", user_id_str, payload.amount)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                WITH updated AS (
                    UPDATE wallets
                    SET balance = balance + %s
                    WHERE user_id = %s
                    RETURNING id, balance
                ),
                inserted AS (
                    INSERT INTO ledger_entries (wallet_id, entry_type, amount, balance_after)
                    SELECT id, 'credit', %s, balance
                    FROM updated
                    RETURNING id
                )
                SELECT
                    (SELECT balance FROM updated) AS balance,
                    (SELECT id FROM inserted) AS transaction_id;
                """,
                (payload.amount, user_id_str, payload.amount),
            )
            mutation = cur.fetchone()
            if mutation is None or mutation["transaction_id"] is None:
                conn.rollback()
                logger.warning("credit_wallet_not_found user_id=%s", user_id_str)
                raise HTTPException(status_code=404, detail="wallet not found")
            conn.commit()

    logger.info(
        "credit_success user_id=%s transaction_id=%s balance=%s",
        user_id_str,
        mutation["transaction_id"],
        mutation["balance"],
    )
    return WalletMutationResponse(
        user_id=user_id_str,
        balance=mutation["balance"],
        transaction_id=mutation["transaction_id"],
    )


@router.post("/wallets/{user_id}/debit", response_model=WalletMutationResponse, tags=["wallet"])
def debit_wallet(user_id: str, payload: MoneyRequest) -> WalletMutationResponse:
    user_id_str = user_id
    logger.info("debit_requested user_id=%s amount=%s", user_id_str, payload.amount)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                WITH updated AS (
                    UPDATE wallets
                    SET balance = balance - %s
                    WHERE user_id = %s
                      AND balance >= %s
                    RETURNING id, balance
                ),
                inserted AS (
                    INSERT INTO ledger_entries (wallet_id, entry_type, amount, balance_after)
                    SELECT id, 'debit', %s, balance
                    FROM updated
                    RETURNING id
                )
                SELECT
                    (SELECT balance FROM updated) AS balance,
                    (SELECT id FROM inserted) AS transaction_id;
                """,
                (payload.amount, user_id_str, payload.amount, payload.amount),
            )
            mutation = cur.fetchone()

            if mutation is None or mutation["transaction_id"] is None:
                cur.execute("SELECT 1 FROM wallets WHERE user_id = %s", (user_id_str,))
                exists = cur.fetchone()
                conn.rollback()
                if exists is None:
                    logger.warning("debit_wallet_not_found user_id=%s", user_id_str)
                    raise HTTPException(status_code=404, detail="wallet not found")
                logger.warning(
                    "debit_insufficient_funds user_id=%s amount=%s", user_id_str, payload.amount
                )
                raise HTTPException(status_code=400, detail="insufficient funds")
            conn.commit()

    logger.info(
        "debit_success user_id=%s transaction_id=%s balance=%s",
        user_id_str,
        mutation["transaction_id"],
        mutation["balance"],
    )
    return WalletMutationResponse(
        user_id=user_id_str,
        balance=mutation["balance"],
        transaction_id=mutation["transaction_id"],
    )


@router.get("/wallets/{user_id}/balance", response_model=WalletBalanceResponse, tags=["wallet"])
def get_wallet_balance(user_id: str) -> WalletBalanceResponse:
    user_id_str = user_id
    logger.info("balance_requested user_id=%s", user_id_str)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT user_id, balance, created_at FROM wallets WHERE user_id = %s;",
                (user_id_str,),
            )
            row = cur.fetchone()

    if row is None:
        logger.warning("balance_wallet_not_found user_id=%s", user_id_str)
        raise HTTPException(status_code=404, detail="wallet not found")

    return WalletBalanceResponse(**row)


@router.get("/wallets/{user_id}/ledger", response_model=list[LedgerEntryResponse], tags=["wallet"])
def get_wallet_ledger(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[LedgerEntryResponse]:
    user_id_str = user_id
    logger.info("ledger_requested user_id=%s limit=%s offset=%s", user_id_str, limit, offset)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id FROM wallets WHERE user_id = %s", (user_id_str,))
            wallet = cur.fetchone()
            if wallet is None:
                logger.warning("ledger_wallet_not_found user_id=%s", user_id_str)
                raise HTTPException(status_code=404, detail="wallet not found")

            cur.execute(
                """
                SELECT id, entry_type, amount, balance_after, created_at
                FROM ledger_entries
                WHERE wallet_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s OFFSET %s;
                """,
                (wallet["id"], limit, offset),
            )
            rows = cur.fetchall()

    return [LedgerEntryResponse(**row) for row in rows]
