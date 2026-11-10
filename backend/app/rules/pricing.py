"""Turns the services a client picked into one visit: total time, price and hold. Pure functions."""
from dataclasses import dataclass
from decimal import Decimal

MAX_VISIT_MINUTES = 720


class VisitError(ValueError):
    """The chosen combination isn't allowed. The message is safe to show to the client."""


@dataclass(frozen=True)
class ServiceLine:
    service_id: object
    name: str
    kind: str                 # "main" or "add_on"
    duration_minutes: int
    cleanup_minutes: int
    price: Decimal
    deposit: Decimal
    payment_options: tuple[str, ...]


@dataclass(frozen=True)
class VisitPlan:
    lines: tuple[ServiceLine, ...]
    duration_minutes: int     # what the client books
    occupied_minutes: int     # duration + cleanup: how long the staff member is busy
    price: Decimal
    deposit: Decimal
    payment_options: tuple[str, ...]

    def hold_for(self, option: str) -> Decimal:
        if option not in self.payment_options:
            raise VisitError("That payment option isn't available for this combination")
        return self.deposit if option == "deposit_held" else self.price


def plan_visit(lines: list[ServiceLine]) -> VisitPlan:
    if not lines:
        raise VisitError("Choose at least one service")
    if len({line.service_id for line in lines}) != len(lines):
        raise VisitError("Each service can only be chosen once")
    if not any(line.kind == "main" for line in lines):
        raise VisitError("Add-ons need a main service")

    # Main services first, then add-ons, keeping the client's order within each group.
    ordered = tuple(sorted(lines, key=lambda line: 0 if line.kind == "main" else 1))
    duration = sum(line.duration_minutes for line in ordered)
    cleanup = max(line.cleanup_minutes for line in ordered)  # one cleanup at the end of the visit
    if duration > MAX_VISIT_MINUTES:
        raise VisitError("That visit is too long to book in one go")

    options = set(ordered[0].payment_options)
    for line in ordered[1:]:
        options &= set(line.payment_options)
    price = sum((line.price for line in ordered), Decimal("0"))
    deposit = sum((line.deposit for line in ordered), Decimal("0"))
    if deposit <= 0:
        options.discard("deposit_held")
    if not options:
        raise VisitError("These services can't be paid for together. Please book them separately.")

    return VisitPlan(
        lines=ordered, duration_minutes=duration, occupied_minutes=duration + cleanup,
        price=price, deposit=deposit, payment_options=tuple(sorted(options)),
    )


def strictest_policy(business_policy: dict, overrides: list[dict | None]) -> dict:
    """If any chosen service has its own policy, use the strictest (longest free-cancellation notice)."""
    candidates = [business_policy] + [o for o in overrides if o]
    return max(candidates, key=lambda p: int(p.get("free_cancel_hours", 0)))