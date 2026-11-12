"""Shared setup for integration tests: a real Postgres test database, a fake PayPal, and a controllable clock.

These tests run only when you ask for them (pytest tests/integration) and TEST_DATABASE_URL is set
(in the environment or in backend/.env), so the normal quick `pytest -q` stays fast. They:
  * refuse to run against the app's own database (DATABASE_URL),
  * bring the test database up to date with Alembic (so migrations are tested too),
  * empty every table before each test.
"""
import os
import subprocess
import sys
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[2]
TZ = "Asia/Kolkata"


def _env_file() -> dict:
    values = {}
    env_path = BACKEND / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = {**_env_file(), **os.environ}
TEST_URL = ENV.get("TEST_DATABASE_URL", "")


def _same_database(a: str, b: str) -> bool:
    if not a or not b:
        return False
    ua, ub = make_url(a), make_url(b)
    return (ua.host, ua.port, ua.username, ua.database) == (ub.host, ub.port, ub.username, ub.database)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    if not any("integration" in arg for arg in sys.argv[1:]):
        pytest.skip("Integration tests run with: pytest tests/integration")
    if not TEST_URL:
        pytest.skip("Set TEST_DATABASE_URL to run integration tests")
    if _same_database(TEST_URL, ENV.get("DATABASE_URL", "")):
        pytest.exit("TEST_DATABASE_URL points at the app's own database. Refusing to wipe it.", returncode=2)
    # Bring the test database up to date (this also tests the migrations).
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND,
                            env={**os.environ, "DATABASE_URL": TEST_URL}, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.exit(f"Alembic upgrade failed on the test database:\n{result.stderr[-2000:]}", returncode=2)
    return TEST_URL


@pytest_asyncio.fixture
async def db(test_database_url):
    """A clean database for each test, and the app's clock set to a known moment."""
    from app import db as app_db
    from app.clock import get_clock, init_clock

    app_db.init_db(test_database_url)
    async with app_db.session_scope() as session:
        tables = (await session.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"))).scalars().all()
        if tables:
            await session.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
            await session.commit()
    init_clock(simulated=True)
    # Next Monday, 8:00 AM in the business's time zone (within the simulated clock's 30-day range).
    local = datetime.now(ZoneInfo(TZ))
    monday = (local + timedelta(days=7 - local.weekday())).date()
    get_clock().set_to(datetime.combine(monday, time(8), ZoneInfo(TZ)))
    yield app_db
    get_clock().reset()
    await app_db.close_db()


# ---------- a fake PayPal: remembers holds, honours request IDs, can be told to fail ----------

class FakePayPal:
    def __init__(self):
        self.authorizations: dict[str, dict] = {}     # authorization id -> {"status", "amount", "captured"}
        self.calls: list[tuple] = []
        self.done: dict[str, object] = {}             # request id -> result (PayPal never repeats an action)
        self.fail_next: str | None = None             # e.g. "capture" or "void"

    def _maybe_fail(self, action: str):
        from app.payments.paypal import PayPalError
        if self.fail_next == action:
            self.fail_next = None
            raise PayPalError(503, "SERVICE_UNAVAILABLE", "PayPal is temporarily unavailable", "debug-123")

    async def create_order(self, *, amount, currency, reference_id, description, payee_merchant_id, request_id):
        self.calls.append(("create_order", request_id))
        return self.done.setdefault(request_id, {"id": f"ORDER-{uuid.uuid4().hex[:10]}"})

    async def authorize_order(self, order_id, request_id=None):
        from types import SimpleNamespace
        self.calls.append(("authorize", order_id))
        if request_id in self.done:
            return self.done[request_id]
        auth_id = f"AUTH-{uuid.uuid4().hex[:10]}"
        self.authorizations[auth_id] = {"status": "CREATED", "captured": Decimal("0")}
        result = SimpleNamespace(authorization_id=auth_id, payment_method="paypal", card_brand=None,
                                 card_last_digits=None, expiration_time=None)
        self.done[request_id] = result
        return result

    async def capture_authorization(self, authorization_id, *, amount, currency, final_capture, request_id):
        if request_id in self.done:
            return self.done[request_id]
        self._maybe_fail("capture")
        self.calls.append(("capture", authorization_id, Decimal(str(amount))))
        auth = self.authorizations[authorization_id]
        auth["captured"] += Decimal(str(amount))
        auth["status"] = "CAPTURED"
        result = {"id": f"CAP-{uuid.uuid4().hex[:10]}", "status": "COMPLETED"}
        self.done[request_id] = result
        return result

    async def void_authorization(self, authorization_id, *, request_id):
        if request_id in self.done:
            return self.done[request_id]
        self._maybe_fail("void")
        self.calls.append(("void", authorization_id))
        self.authorizations[authorization_id]["status"] = "VOIDED"
        self.done[request_id] = {}
        return {}

    async def get_authorization(self, authorization_id):
        return {"id": authorization_id, "status": self.authorizations[authorization_id]["status"]}

    def captures(self) -> list:
        return [c for c in self.calls if c[0] == "capture"]


@pytest.fixture
def paypal():
    return FakePayPal()


# ---------- building a ready business and clients through the app's own services ----------

POLICY_RULES = {"free_cancel_hours": 24, "late_cancel_fee": {"kind": "percent_of_hold", "value": "50"},
                "no_show_fee": {"kind": "percent_of_hold", "value": "100"}, "waive_if_refilled": True,
                "grace_minutes": 10}


@pytest.fixture
def make_business(db):
    async def build(session, *, capacity_class: int | None = None):
        from app.schemas.business import BusinessCreate
        from app.schemas.policy import PolicyDraftIn
        from app.schemas.schedule import AvailabilityIn
        from app.schemas.service import ServiceCreate
        from app.services import businesses, offerings, policies, schedule

        owner_id = uuid.uuid4()
        business = await businesses.create_business(session, owner_id, BusinessCreate(
            name="Ravi's Barbershop", category="barber", timezone=TZ, currency="INR"), "owner@example.com")
        haircut = await offerings.create_service(session, business, owner_id, ServiceCreate(
            name="Haircut", kind="main", booking_mode="appointment", duration_minutes=30, cleanup_minutes=0,
            price=Decimal("300"), deposit=Decimal("80"), payment_options=["deposit_held", "full_held"]))
        extra = {}
        if capacity_class:
            yoga = await offerings.create_service(session, business, owner_id, ServiceCreate(
                name="Morning yoga", kind="main", booking_mode="class", duration_minutes=60, cleanup_minutes=0,
                price=Decimal("500"), deposit=Decimal("100"), payment_options=["deposit_held"]))
            yoga.capacity = capacity_class
            await session.commit()
            extra["yoga"] = yoga
        await schedule.replace_hours(session, business, owner_id, AvailabilityIn(hours=[
            {"weekday": d, "start": "09:00", "end": "18:00"} for d in range(7)]))
        draft = await policies.create_draft(session, business, owner_id, PolicyDraftIn(
            raw_text="Free cancellation up to 24 hours before.", rules=POLICY_RULES))
        await policies.confirm_policy(session, business, owner_id, draft.version)
        await session.refresh(business)
        business.min_notice_minutes = 0
        await session.commit()
        await businesses.go_live(session, business, owner_id, True)
        await session.refresh(business)
        return business, haircut, owner_id, extra

    return build


@pytest.fixture
def make_client(db):
    async def build(session, name="Priya Sharma"):
        from app.models import Client
        client = Client(name=name, auth_user_id=uuid.uuid4())
        session.add(client)
        await session.commit()
        await session.refresh(client)
        return client

    return build


def at(hours_from_now: float, round_to_minutes: int = 15) -> datetime:
    """A booking start time: N hours from the test clock, on the business's 15-minute grid."""
    from app.clock import get_clock
    moment = get_clock().now() + timedelta(hours=hours_from_now)
    moment = moment.replace(second=0, microsecond=0)
    return moment - timedelta(minutes=moment.minute % round_to_minutes)