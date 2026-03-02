import os
import sys
import secrets
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:localhost@localhost:5432/walletdb"
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function", autouse=True)
def clean_db():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE TABLE ledger_entries, wallets, users RESTART IDENTITY CASCADE;"
            )
        conn.commit()


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"healthy", "unhealthy"}
    assert "service" in data
    assert "environment" in data


def test_create_wallet_and_duplicate(client: TestClient):
    user_id = f"user-{secrets.token_hex(4)}"
    create_user = client.post("/users", json={"user_id": user_id})
    assert create_user.status_code == 201

    response = client.post("/wallets", json={"user_id": user_id})
    assert response.status_code == 201
    assert Decimal(response.json()["balance"]) == Decimal("0.00")
    assert "created_at" in response.json()

    duplicate = client.post("/wallets", json={"user_id": user_id})
    assert duplicate.status_code == 409


def test_create_get_list_user(client: TestClient):
    user_id = f"user-{secrets.token_hex(4)}"
    create = client.post("/users", json={"user_id": user_id})
    assert create.status_code == 201
    assert create.json()["user_id"] == user_id
    assert "created_at" in create.json()

    duplicate = client.post("/users", json={"user_id": user_id})
    assert duplicate.status_code == 409

    get_one = client.get(f"/users/{user_id}")
    assert get_one.status_code == 200
    assert get_one.json()["user_id"] == user_id
    assert "created_at" in get_one.json()

    list_users = client.get("/users")
    assert list_users.status_code == 200
    assert any(item["user_id"] == user_id for item in list_users.json())


def test_credit_debit_balance_and_ledger(client: TestClient):
    user_id = f"user-{secrets.token_hex(4)}"
    create_user = client.post("/users", json={"user_id": user_id})
    assert create_user.status_code == 201
    assert client.post("/wallets", json={"user_id": user_id}).status_code == 201

    c1 = client.post(
        f"/wallets/{user_id}/credit",
        json={"amount": "100.00"},
    )
    assert c1.status_code == 200
    assert Decimal(c1.json()["balance"]) == Decimal("100.00")

    d1 = client.post(f"/wallets/{user_id}/debit", json={"amount": "40.00"})
    assert d1.status_code == 200
    assert Decimal(d1.json()["balance"]) == Decimal("60.00")

    balance = client.get(f"/wallets/{user_id}/balance")
    assert balance.status_code == 200
    assert Decimal(balance.json()["balance"]) == Decimal("60.00")
    assert "created_at" in balance.json()

    ledger = client.get(f"/wallets/{user_id}/ledger")
    assert ledger.status_code == 200
    entries = ledger.json()
    assert len(entries) == 2
    assert {e["entry_type"] for e in entries} == {"credit", "debit"}


def test_debit_rejected_when_insufficient(client: TestClient):
    user_id = f"user-{secrets.token_hex(4)}"
    create_user = client.post("/users", json={"user_id": user_id})
    assert create_user.status_code == 201
    assert client.post("/wallets", json={"user_id": user_id}).status_code == 201
    assert (
        client.post(
            f"/wallets/{user_id}/credit",
            json={"amount": "10.00"},
        ).status_code
        == 200
    )

    fail = client.post(f"/wallets/{user_id}/debit", json={"amount": "15.00"})
    assert fail.status_code == 400
    assert fail.json()["detail"] == "insufficient funds"

    balance = client.get(f"/wallets/{user_id}/balance")
    assert Decimal(balance.json()["balance"]) == Decimal("10.00")
    assert "created_at" in balance.json()

    ledger = client.get(f"/wallets/{user_id}/ledger")
    assert len(ledger.json()) == 1
    assert ledger.json()[0]["entry_type"] == "credit"


def test_create_wallet_requires_existing_user(client: TestClient):
    user_id = f"user-{secrets.token_hex(4)}"
    response = client.post("/wallets", json={"user_id": user_id})
    assert response.status_code == 404
    assert response.json()["detail"] == "user not found"
