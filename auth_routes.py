import logging

from fastapi import APIRouter, HTTPException, status
from psycopg.rows import dict_row

from auth import create_access_token
from db import pool
from schemas import LoginRequest, TokenResponse

logger = logging.getLogger("wallet.auth")
router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    """
    Simple login:
    - user must already exist in users table
    - if yes, return JWT
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT user_id FROM users WHERE user_id = %s;", (payload.user_id,))
            user = cur.fetchone()

    if user is None:
        logger.warning("login_user_not_found user_id=%s", payload.user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    token = create_access_token(payload.user_id)
    logger.info("login_success user_id=%s", payload.user_id)
    return TokenResponse(access_token=token)
