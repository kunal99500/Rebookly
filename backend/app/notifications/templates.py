"""What each message says. Pure functions: frozen payload in, subject + text + HTML out.

The payload is captured when the message is created, so it describes what happened at that moment.
Amounts and policy wording come from the same code as receipts; nothing here is written by AI.
"""
from html import escape

KINDS = (
    "booking_confirmed", "new_booking", "reminder_24h", "reminder_2h", "booking_cancelled",
    "booking_rescheduled", "fee_pending", "fee_charged", "hold_released", "payment_failed", "email_code",
    "hold_lost", "payment_dispute","waitlist_offer","new_review",
)


def _lines(kind: str, p: dict) -> tuple[str, list[str]]:
    biz, when, visit = p.get("business_name", ""), p.get("when", ""), p.get("visit", "your booking")
    if kind == "booking_confirmed":
        return f"Booked: {visit} at {biz}", [
            f"You're booked for {visit} at {biz} on {when}.",
            f"{p.get('held')} is held on your payment method. It isn't charged now.",
            p.get("policy_line", ""), f"Reference: {p.get('ref')}"]
    if kind == "new_booking":
        return f"New booking: {visit}, {when}", [
            f"{p.get('client_name')} booked {visit} on {when}.", f"{p.get('held')} is held.", f"Reference: {p.get('ref')}"]
    if kind in ("reminder_24h", "reminder_2h"):
        soon = "tomorrow" if kind == "reminder_24h" else "in about 2 hours"
        management = ("Need to change it? Open My bookings to reschedule or cancel."
                      if p.get("has_account") else "Need to change it? Contact the business directly.")
        return f"Reminder: {visit} {soon}", [
            f"See you {soon}: {visit} at {biz}, {when}.", p.get("policy_line", ""),
            management]
    if kind == "booking_cancelled":
        return f"Cancelled: {visit} on {when}", [
            f"The booking for {visit} at {biz} on {when} was cancelled ({p.get('by', 'cancelled')}).",
            p.get("outcome", "")]
    if kind == "booking_rescheduled":
        if p.get("by_owner"):
            next_step = ("If the new time doesn't work, contact the business."
                         if not p.get("has_account") else
                         "If the new time doesn't work for you, you can cancel this booking without a fee.")
            return f"{biz} moved your booking to {when}", [
                f"{biz} needed to move your booking for {visit}. It's now on {when}.",
                next_step,
                f"Reference: {p.get('ref')}"]
        return f"Moved: {visit} is now {when}", [f"Your booking for {visit} at {biz} is now on {when}.",
                                                 f"Reference: {p.get('ref')}"]
    if kind == "fee_pending":
        return f"Fee waiting for your approval: {p.get('amount')}", [
            f"{p.get('reason')}", f"Under your policy, up to {p.get('amount')} can be kept.",
            "Open Approvals to charge it, lower it, or waive it."]
    if kind == "fee_charged":
        return f"{biz}: a fee of {p.get('amount')} was charged", [
            p.get("reason", ""), f"{p.get('amount')} was charged and {p.get('released')} was released.",
            "Think this isn't right? Contact the business and ask them to review it."]
    if kind == "hold_released":
        return f"{biz}: your hold of {p.get('released')} was released", [
            f"Nothing was charged. {p.get('released')} was released to your payment method.",
            "Your bank may take a few days to remove the pending amount."]
    if kind == "payment_failed":
        return "A payment action needs your attention", [
            f"PayPal couldn't complete an action for booking {p.get('ref')}: {p.get('error')}",
            "Open Approvals to retry it."]

    if kind == "hold_lost":
           return f"Deposit no longer held: {visit}, {when}", [
               f"PayPal reports the hold for {p.get('client_name')}'s booking ({visit}, {when}) is now {p.get('paypal_status')}.",
               "The booking is still on, but there's no deposit to collect if it's cancelled late or missed.",
               f"Reference: {p.get('ref')}"]
    if kind == "payment_dispute":
           return f"A client opened a PayPal dispute: {p.get('ref')}", [
               f"{p.get('client_name')} disputed a payment for {visit} ({when}) with PayPal.",
               "Reply to the dispute in your PayPal account. Your booking records and receipts in Rebookly "
               "show what was agreed and when."]
    if kind == "waitlist_offer":
           return f"A time opened up: {visit} at {biz}", [
               f"Good news: {visit} at {biz} is free on {when}.",
               f"The first person to book it gets it. This offer ends at {p.get('expires')}.",
               "Open your waitlist in Rebookly to book it."]

    if kind == "new_review":
        stars = int(p.get("rating") or 0)
        comment = p.get("comment")
        return f"New review: {'★' * stars}{'☆' * (5 - stars)} from {p.get('reviewer')}", [
               f"{p.get('reviewer')} rated {biz} {stars} out of 5 after their visit.",
               f"“{comment}”" if comment else "",
               "You can reply publicly from Reviews in Rebookly."]
    if kind == "email_code":
        return "Your Rebookly verification code", [
            f"Your code is {p.get('code')}. It expires in 15 minutes.",
            "If you didn't ask for this, you can ignore this email."]
    raise ValueError(f"Unknown notification kind: {kind}")


def render(kind: str, payload: dict) -> tuple[str, str, str]:
    subject, lines = _lines(kind, payload)
    lines = [line for line in lines if line]
    link = payload.get("link")
    text = "\n\n".join(lines + ([link] if link else [])) + "\n\n— Rebookly"
    paragraphs = "".join(f'<p style="margin:0 0 12px">{escape(line)}</p>' for line in lines)
    button = (f'<p style="margin:16px 0"><a href="{escape(link, quote=True)}" style="background:#3B4FD8;color:#fff;'
              f'padding:10px 16px;border-radius:8px;text-decoration:none">Open in Rebookly</a></p>') if link else ""
    html = (f'<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:15px;line-height:1.5;'
            f'color:#161B2E;max-width:520px">{paragraphs}{button}'
            f'<p style="margin:16px 0 0;color:#5C6478;font-size:13px">Rebookly</p></div>')
    return subject, text, html