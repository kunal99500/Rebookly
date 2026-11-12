"""Writing, reading, replying to and reporting verified reviews; keeping each business's rating up to date."""
import uuid
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.config import get_settings
from app.models import Booking, Business, Client, Review
from app.notifications.outbox import enqueue, notify_safely
from app.rules.reviews import can_edit, comment_problem, display_name, review_problem
from app.schemas.review import MyReviewStatus, OwnerReviewOut, RatingSummary, ReviewIn, ReviewOut, ReviewPage
from app.services import audit, bookings

PAGE_SIZE = 20


async def _out(session: AsyncSession, review: Review, owner_view: bool = False) -> ReviewOut:
    client = await session.get(Client, review.client_id)
    business = await session.get(Business, review.business_id)
    services = (await bookings.visit_summaries(session, [review.booking_id])).get(review.booking_id, "")
    fields = dict(
        id=review.id, rating=review.rating, comment=review.comment, reviewer=display_name(client.name if client else None),
        services=services, visited_month=review.visited_at.astimezone(ZoneInfo(business.timezone)).strftime("%b %Y"),
        created_at=review.created_at, edited=review.edited_at is not None,
        owner_reply=review.owner_reply, owner_replied_at=review.owner_replied_at,
    )
    if owner_view:
        return OwnerReviewOut(**fields, booking_id=review.booking_id, reported=review.reported_at is not None)
    return ReviewOut(**fields)


async def _refresh_rating(session: AsyncSession, business_id: uuid.UUID) -> None:
    """Recalculate the business's average and count in the same transaction as the change."""
    average, count = (await session.execute(select(func.round(func.avg(Review.rating), 2), func.count(Review.id))
                                            .where(Review.business_id == business_id))).one()
    await session.execute(update(Business).where(Business.id == business_id)
                          .values(rating_average=average, rating_count=count))


def _check_comment(comment: str | None) -> None:
    problem = comment_problem(comment)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)


async def _my_booking(session: AsyncSession, client: Client, booking_id: uuid.UUID) -> Booking:
    booking = await session.scalar(select(Booking).where(Booking.id == booking_id, Booking.client_id == client.id))
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    return booking


async def my_status(session: AsyncSession, client: Client, booking_id: uuid.UUID) -> MyReviewStatus:
    booking = await _my_booking(session, client, booking_id)
    review = await session.scalar(select(Review).where(Review.booking_id == booking.id))
    now = get_clock().now()
    reason = review_problem(booking_status=booking.status, visit_ended_at=booking.ends_at, now=now,
                            already_reviewed=review is not None)
    return MyReviewStatus(review=await _out(session, review) if review else None, can_review=reason is None,
                          can_edit=bool(review and can_edit(review.created_at, now)),
                          reason=None if review else reason)


async def write(session: AsyncSession, client: Client, booking_id: uuid.UUID, data: ReviewIn) -> ReviewOut:
    booking = await _my_booking(session, client, booking_id)
    await session.execute(select(Booking.id).where(Booking.id == booking.id).with_for_update())
    existing = await session.scalar(select(Review.id).where(Review.booking_id == booking.id))
    problem = review_problem(booking_status=booking.status, visit_ended_at=booking.ends_at, now=get_clock().now(),
                             already_reviewed=existing is not None)
    if problem:
        raise HTTPException(status.HTTP_409_CONFLICT, problem)
    _check_comment(data.comment)
    review = Review(business_id=booking.business_id, booking_id=booking.id, client_id=client.id,
                    rating=data.rating, comment=data.comment or None, visited_at=booking.starts_at)
    session.add(review)
    await session.flush()
    await _refresh_rating(session, booking.business_id)
    audit.record(session, actor_type="client", actor_id=client.auth_user_id, action="review.written",
                 business_id=booking.business_id, booking_id=booking.id, details={"rating": data.rating})
    business = await session.get(Business, booking.business_id)
    if business.notification_email:
        await notify_safely(session, enqueue(
            session, kind="new_review", to_address=business.notification_email, recipient_type="owner",
            business_id=business.id, booking_id=booking.id, dedupe_key=f"new_review:{review.id}",
            payload={"business_name": business.name, "rating": data.rating, "reviewer": display_name(client.name),
                     "comment": (data.comment or "")[:300],
                     "link": f"{get_settings().frontend_url.rstrip('/')}/business/reviews"}))
    await session.commit()
    await session.refresh(review)
    return await _out(session, review)


async def _my_review(session: AsyncSession, client: Client, booking_id: uuid.UUID) -> Review:
    review = await session.scalar(select(Review).where(Review.booking_id == booking_id, Review.client_id == client.id)
                                  .with_for_update())
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You haven't reviewed this visit")
    return review


async def edit(session: AsyncSession, client: Client, booking_id: uuid.UUID, data: ReviewIn) -> ReviewOut:
    review = await _my_review(session, client, booking_id)
    if not can_edit(review.created_at, get_clock().now()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Reviews can be edited for 7 days after writing them.")
    _check_comment(data.comment)
    review.rating, review.comment, review.edited_at = data.rating, data.comment or None, get_clock().now()
    await session.flush()
    await _refresh_rating(session, review.business_id)
    await session.commit()
    await session.refresh(review)
    return await _out(session, review)


async def delete(session: AsyncSession, client: Client, booking_id: uuid.UUID) -> None:
    review = await _my_review(session, client, booking_id)
    business_id = review.business_id
    await session.delete(review)
    await session.flush()
    await _refresh_rating(session, business_id)
    audit.record(session, actor_type="client", actor_id=client.auth_user_id, action="review.deleted",
                 business_id=business_id, booking_id=booking_id, details={})
    await session.commit()


async def summary(session: AsyncSession, business: Business) -> RatingSummary:
    rows = dict((await session.execute(select(Review.rating, func.count()).where(Review.business_id == business.id)
                                       .group_by(Review.rating))).all())
    return RatingSummary(average=business.rating_average, count=business.rating_count,
                         distribution={stars: rows.get(stars, 0) for stars in (5, 4, 3, 2, 1)})


async def page(session: AsyncSession, business: Business, offset: int = 0, owner_view: bool = False) -> ReviewPage:
    rows = list(await session.scalars(select(Review).where(Review.business_id == business.id)
                                      .order_by(Review.created_at.desc()).offset(offset).limit(PAGE_SIZE + 1)))
    more = len(rows) > PAGE_SIZE
    return ReviewPage(summary=await summary(session, business),
                      reviews=[await _out(session, r, owner_view) for r in rows[:PAGE_SIZE]],
                      next_offset=offset + PAGE_SIZE if more else None)


async def _business_review(session: AsyncSession, business: Business, review_id: uuid.UUID) -> Review:
    review = await session.scalar(select(Review).where(Review.id == review_id, Review.business_id == business.id)
                                  .with_for_update())
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")
    return review


async def reply(session: AsyncSession, business: Business, owner_id: uuid.UUID, review_id: uuid.UUID,
                text: str | None) -> OwnerReviewOut:
    """Add, change or (with None) remove the owner's public reply. The review itself can't be changed."""
    review = await _business_review(session, business, review_id)
    if text:
        _check_comment(text)
    review.owner_reply = text or None
    review.owner_replied_at = get_clock().now() if text else None
    audit.record(session, actor_type="owner", actor_id=owner_id, action="review.replied" if text else "review.reply_removed",
                 business_id=business.id, booking_id=review.booking_id, details={})
    await session.commit()
    await session.refresh(review)
    return await _out(session, review, owner_view=True)


async def report(session: AsyncSession, business: Business, owner_id: uuid.UUID, review_id: uuid.UUID,
                 reason: str) -> OwnerReviewOut:
    """Ask Rebookly to look at a review (e.g. abusive, or about another business). It stays visible meanwhile."""
    review = await _business_review(session, business, review_id)
    review.reported_at, review.report_reason = get_clock().now(), reason
    audit.record(session, actor_type="owner", actor_id=owner_id, action="review.reported",
                 business_id=business.id, booking_id=review.booking_id, details={"reason": reason})
    await session.commit()
    await session.refresh(review)
    return await _out(session, review, owner_view=True)