"""Business logic for a business's services (what it sells).

Named "offerings" so it isn't confused with the app.services package itself.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Service
from app.schemas.service import ServiceCreate, ServiceUpdate, check_service_money
from app.services import audit , team


async def create_service(session: AsyncSession, business: Business, owner_id: uuid.UUID, data: ServiceCreate) -> Service:
    service = Service(id=uuid.uuid4(), business_id=business.id, **data.model_dump())
    session.add(service)
    await session.flush()
    await team.link_service_to_all_staff(session, business, service.id)
    audit.record(session, actor_type="owner", actor_id=owner_id, action="service.created",
                 business_id=business.id, details={"service_id": str(service.id), "name": service.name})
    await session.commit()
    await session.refresh(service)
    return service


async def list_services(session: AsyncSession, business: Business, include_inactive: bool = True) -> list[Service]:
    query = select(Service).where(Service.business_id == business.id)
    if not include_inactive:
        query = query.where(Service.is_active.is_(True))
    result = await session.scalars(query.order_by(Service.sort_order, Service.created_at))
    return list(result)


async def update_service(
    session: AsyncSession, service: Service, owner_id: uuid.UUID, data: ServiceUpdate
) -> Service:
    changes = data.model_dump(exclude_unset=True)
    price = changes.get("price", service.price)
    deposit = changes.get("deposit", service.deposit)
    options = changes.get("payment_options", service.payment_options)
    kind = changes.get("kind", service.kind)
    try:
           check_service_money(price, deposit, options, kind)
    except ValueError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err))

    for field, value in changes.items():
        setattr(service, field, value)
    if changes:
        audit.record(session, actor_type="owner", actor_id=owner_id, action="service.updated",
                     business_id=service.business_id,
                     details={"service_id": str(service.id), "fields": sorted(changes)})
        await session.commit()
        await session.refresh(service)
    return service