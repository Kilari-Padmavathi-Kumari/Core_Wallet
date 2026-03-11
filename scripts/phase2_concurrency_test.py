import asyncio
import os
import secrets
from collections import Counter
from decimal import Decimal

import httpx


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
USER_ID = os.getenv("USER_ID", "1")
PASSWORD = os.getenv("PASSWORD", "pass1234")

DEBIT_AMOUNT = Decimal("10.00")
DEBIT_COUNT = 50
INITIAL_BALANCE = Decimal("100.00")


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        # Register (ignore conflict if user already exists).
        register = await client.post(
            "/auth/register",
            json={"user_id": USER_ID, "password": PASSWORD},
        )
        if register.status_code not in (201, 409):
            raise RuntimeError(f"register failed: {register.status_code} {register.text}")

        login = await client.post(
            "/auth/login",
            json={"user_id": USER_ID, "password": PASSWORD},
        )
        if login.status_code != 200:
            raise RuntimeError(f"login failed: {login.status_code} {login.text}")

        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create wallet (ignore conflict if it already exists).
        wallet = await client.post("/wallets", json={"user_id": USER_ID}, headers=headers)
        if wallet.status_code not in (201, 409):
            raise RuntimeError(f"create wallet failed: {wallet.status_code} {wallet.text}")

        # Credit initial balance = 100.
        credit = await client.post(
            f"/wallets/{USER_ID}/credit",
            json={"amount": str(INITIAL_BALANCE)},
            headers=headers,
        )
        if credit.status_code != 200:
            raise RuntimeError(f"credit failed: {credit.status_code} {credit.text}")

        async def debit_once() -> int:
            resp = await client.post(
                f"/wallets/{USER_ID}/debit",
                json={"amount": str(DEBIT_AMOUNT)},
                headers=headers,
            )
            return resp.status_code

        # 50 concurrent debits of 10.
        statuses = await asyncio.gather(*[debit_once() for _ in range(DEBIT_COUNT)])
        counts = Counter(statuses)
        success = counts.get(200, 0)
        insufficient = counts.get(400, 0)
        other = [code for code in statuses if code not in (200, 400)]

        balance = await client.get(f"/wallets/{USER_ID}/balance", headers=headers)
        ledger = await client.get(f"/wallets/{USER_ID}/ledger?limit=200", headers=headers)

        if balance.status_code != 200 or ledger.status_code != 200:
            raise RuntimeError(
                f"post-check failed: balance={balance.status_code} ledger={ledger.status_code}"
            )

        final_balance = Decimal(str(balance.json()["balance"]))
        ledger_rows = ledger.json()
        debit_entries = [e for e in ledger_rows if e["entry_type"] == "debit"]

        expected_successes = int(INITIAL_BALANCE / DEBIT_AMOUNT)
        passed = (
            success == expected_successes
            and insufficient == (DEBIT_COUNT - expected_successes)
            and final_balance == Decimal("0.00")
            and len(debit_entries) == expected_successes
            and not other
        )

        status_label = "PASS" if passed else "FAIL"
        print(f"PHASE2_CONCURRENCY_CHECK: {status_label}")
        print(
            f"successes={success} failures={insufficient} final_balance={final_balance} "
            f"debit_ledger_entries={len(debit_entries)} "
            f"failure_reasons={{'Insufficient balance': {insufficient}}}"
        )
        print("Ledger entries:")
        for entry in ledger_rows:
            print(entry)


if __name__ == "__main__":
    asyncio.run(main())
