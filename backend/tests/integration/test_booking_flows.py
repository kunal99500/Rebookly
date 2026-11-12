"""The most important flows, end to end, against a real Postgres database (with a fake PayPal).

Each test reads like a story: a client books and pays, and then something happens. The assertions check what
matters to people: the booking's state, where the money went, and that nothing happened twice.
"""
import asyncio
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import Booking, Decision, Document, Notification, Payment, Slot
from app.rules.engine import Event
from app.schemas.client import BookingCreate, ClassBookingCreate
from app.services import bookings, outcomes, refills, rescheduling

from .conftest import at

pytestmark = pytest.mark.asyncio


async def book_and_pay(session, paypal, client, service, starts_at, option="deposit_held"):
    booking = await bookings.create_booking(session, client, BookingCreate(
        service_ids=[service.id], starts_at=starts_at, payment_option=option))
    await bookings.hold_payment(session, paypal, booking)
    await bookings.authorize_hold(session, paypal, booking)
    await session.refresh(booking)
    return booking


async def hold_of(session, booking) -> Payment:
    return await session.scalar(select(Payment).where(Payment.booking_id == booking.id, Payment.kind == "hold"))


async def decisions_of(session, booking) -> list[Decision]:
    return list(await session.scalars(select(Decision).where(Decision.booking_id == booking.id)
                                      .order_by(Decision.created_at)))


# ---------- booking ----------

async def test_booking_is_confirmed_with_a_hold_a_receipt_and_messages(db, paypal, make_business, make_client):
    async with db.session_scope() as session:
        business, haircut, _, _ = await make_business(session)
        priya = await make_client(session)
        booking = await book_and_pay(session, paypal, priya, haircut, at(26))

        assert booking.status == "confirmed" and booking.confirmation_number
        hold = await hold_of(session, booking)
        assert (hold.status, hold.amount) == ("authorized", Decimal("80.00"))
        assert await session.scalar(select(func.count()).select_from(Document).where(
            Document.booking_id == booking.id)) >= 1
        owner_alerts = await session.scalar(select(func.count()).select_from(Notification).where(
            Notification.booking_id == booking.id, Notification.kind == "new_booking"))
        assert owner_alerts == 1


async def test_the_same_time_can_never_be_double_booked(db, paypal, make_business, make_client):
    async with db.session_scope() as session:
        business, haircut, _, _ = await make_business(session)
        clients = [await make_client(session, f"Client {i}") for i in range(2)]
    starts_at = at(26)

    async def attempt(client):
        async with db.session_scope() as session:
            try:
                await bookings.create_booking(session, client, BookingCreate(
                    service_ids=[haircut.id], starts_at=starts_at, payment_option="deposit_held"))
                return "booked"
            except HTTPException as err:
                return err.status_code

    results = sorted(map(str, await asyncio.gather(*(attempt(c) for c in clients))))
    assert results == ["409", "booked"]


# ---------- outcomes and money ----------

async def test_attending_collects_the_deposit_once(db, paypal, make_business, make_client):
    async with db.session_scope() as session:
        business, haircut, owner_id, _ = await make_business(session)
        booking = await book_and_pay(session, paypal, await make_client(session), haircut, at(26))
        _, decision = await outcomes.apply_event(session, paypal, booking.id, Event.ATTENDED, "owner", owner_id)

        assert decision.status == "executed"
        assert (await hold_of(session, booking)).status == "captured"
        assert [c[2] for c in paypal.captures()] == [Decimal("80.00")]


async def test_free_cancellation_releases_the_whole_hold(db, paypal, make_business, make_client):
    async with db.session_scope() as session:
        business, haircut, _, _ = await make_business(session)
        priya = await make_client(session)
        booking = await book_and_pay(session, paypal, priya, haircut, at(50))
        _, decision = await outcomes.apply_event(session, paypal, booking.id, Event.CLIENT_CANCELLED,
                                                 "client", priya.auth_user_id)

        assert (decision.action, decision.status) == ("void", "executed")
        assert (await hold_of(session, booking)).status == "voided"
        assert paypal.captures() == []


async def test_late_cancellation_fee_waits_for_the_owner_who_can_lower_it(db, paypal, make_business, make_client):
    async with db.session_scope() as session:
        business, haircut, owner_id, _ = await make_business(session)
        priya = await make_client(session)
        booking = await book_and_pay(session, paypal, priya, haircut, at(5))
        _, decision = await outcomes.apply_event(session, paypal, booking.id, Event.CLIENT_CANCELLED,
                                                 "client", priya.auth_user_id)
        assert (decision.status, decision.amount) == ("pending_approval", Decimal("40.00"))
        assert paypal.captures() == []                         # nothing taken without the owner

        with pytest.raises(HTTPException):                    # can't charge more than the policy allows
            await outcomes.approve(session, paypal, decision.id, owner_id, Decimal("50.00"), None)
        decision = await outcomes.approve(session, paypal, decision.id, owner_id, Decimal("20.00"), "First time")
        assert decision.status == "executed"
        assert [c[2] for c in paypal.captures()] == [Decimal("20.00")]


async def test_rebooked_time_drops_the_late_fee(db, paypal, make_business, make_client):
    async with db.session_scope() as session:
        business, haircut, _, _ = await make_business(session)
        priya, amit = await make_client(session, "Priya"), await make_client(session, "Amit")
        starts_at = at(5)
        first = await book_and_pay(session, paypal, priya, haircut, starts_at)
        _, fee = await outcomes.apply_event(session, paypal, first.id, Event.CLIENT_CANCELLED, "client", priya.auth_user_id)
        assert fee.status == "pending_approval"

        await book_and_pay(session, paypal, amit, haircut, starts_at)       # someone takes the freed time
        release_id = await refills.waive_if_refilled(session, fee.id)
        assert release_id is not None
        await outcomes.execute(session, paypal, release_id)

        statuses = [(d.action, d.status) for d in await decisions_of(session, first)]
        assert statuses == [("capture", "superseded"), ("void", "executed")]
        assert (await hold_of(session, first)).status == "voided" and paypal.captures() == []


async def test_after_an_owner_move_the_client_can_cancel_free(db, paypal, make_business, make_client):
    async with db.session_scope() as session:
        business, haircut, owner_id, _ = await make_business(session)
        priya = await make_client(session)
        booking = await book_and_pay(session, paypal, priya, haircut, at(5))
        await rescheduling.reschedule(session, booking.id, at(7), None, "owner", owner_id)
        _, decision = await outcomes.apply_event(session, paypal, booking.id, Event.CLIENT_CANCELLED,
                                                 "client", priya.auth_user_id)
        assert (decision.action, decision.status) == ("void", "executed")
        assert "moved your booking" in decision.reason


async def test_a_failed_capture_is_recovered_without_charging_twice(db, paypal, make_business, make_client):
    async with db.session_scope() as session:
        business, haircut, owner_id, _ = await make_business(session)
        booking = await book_and_pay(session, paypal, await make_client(session), haircut, at(26))
        paypal.fail_next = "capture"
        _, decision = await outcomes.apply_event(session, paypal, booking.id, Event.ATTENDED, "owner", owner_id)
        assert decision.status == "failed" and paypal.captures() == []

        decision = await outcomes.recover(session, paypal, decision.id)      # asks PayPal first, then retries
        assert decision.status == "executed"
        decision = await outcomes.recover(session, paypal, decision.id)      # running it again does nothing
        assert len(paypal.captures()) == 1


# ---------- classes ----------

async def test_three_clients_race_for_two_seats(db, paypal, make_business, make_client):
    from app.services import schedule

    async with db.session_scope() as session:
        business, _, owner_id, extra = await make_business(session, capacity_class=2)
        await schedule.generate_slots(session, business, owner_id, 3)
        slot = await session.scalar(select(Slot).where(Slot.service_id == extra["yoga"].id,
                                                       Slot.starts_at > at(2)).order_by(Slot.starts_at))
        clients = [await make_client(session, f"Yogi {i}") for i in range(3)]

    async def attempt(client):
        async with db.session_scope() as session:
            try:
                await bookings.create_class_booking(session, client, ClassBookingCreate(
                    slot_id=slot.id, payment_option="deposit_held"))
                return "seat"
            except HTTPException as err:
                return err.status_code

    results = sorted(map(str, await asyncio.gather(*(attempt(c) for c in clients))))
    assert results == ["409", "seat", "seat"]
    async with db.session_scope() as session:
        assert (await session.get(Slot, slot.id)).booked_count == 2


# ---------- reviews and privacy ----------

async def test_only_attended_visits_can_be_reviewed_and_ratings_follow(db, paypal, make_business, make_client):
    from app.schemas.review import ReviewIn
    from app.services import reviews

    async with db.session_scope() as session:
        business, haircut, owner_id, _ = await make_business(session)
        priya = await make_client(session)
        booking = await book_and_pay(session, paypal, priya, haircut, at(26))
        with pytest.raises(HTTPException):
            await reviews.write(session, priya, booking.id, ReviewIn(rating=5))
        await outcomes.apply_event(session, paypal, booking.id, Event.ATTENDED, "owner", owner_id)
        await reviews.write(session, priya, booking.id, ReviewIn(rating=4, comment="Neat and quick."))
        await session.refresh(business)
        assert (business.rating_average, business.rating_count) == (Decimal("4.00"), 1)


async def test_deleting_a_client_keeps_records_but_removes_personal_data(db, paypal, make_business, make_client):
    from app.services import account_deletion

    async with db.session_scope() as session:
        business, haircut, owner_id, _ = await make_business(session)
        priya = await make_client(session)
        booking = await book_and_pay(session, paypal, priya, haircut, at(26))
        with pytest.raises(HTTPException):                       # an upcoming booking blocks deletion
            await account_deletion.delete_client_data(session, priya)
        await outcomes.apply_event(session, paypal, booking.id, Event.ATTENDED, "owner", owner_id)

        await account_deletion.delete_client_data(session, priya)
        await session.refresh(priya)
        assert (priya.name, priya.phone_hash, priya.email, priya.auth_user_id) == ("Deleted client", None, None, None)
        kept = await session.get(Booking, booking.id)
        assert kept.status == "attended" and (await hold_of(session, kept)).status == "captured"