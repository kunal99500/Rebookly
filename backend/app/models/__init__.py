"""Database tables.

Every model module must be imported here, so Alembic can see all tables
when it generates migrations.
"""
from app.models.audit_event import AuditEvent  # noqa: F401
from app.models.booking import Booking  # noqa: F401
from app.models.business import Business  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.decision import Decision  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.policy import BusinessPolicy  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.slot import Slot  # noqa: F401
from app.models.waitlist import WaitlistEntry  # noqa: F401
from app.models.availability import AvailabilityRule  # noqa: F401
from app.models.photo import BusinessPhoto  # noqa: F401
from app.models.booking_item import BookingItem  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.resource import Resource  # noqa: F401
from app.models.staff import Staff, StaffHours, StaffService  # noqa: F401
from app.models.time_off import TimeOff  # noqa: F401
from app.models.ai_usage import AIUsage  # noqa: F401
from app.models.tax_profile import BusinessTaxProfile  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.paypal_event import PayPalWebhookEvent  # noqa: F401
from app.models.review import Review  # noqa: F401
from app.models.briefing import DailyBriefing  # noqa: F401