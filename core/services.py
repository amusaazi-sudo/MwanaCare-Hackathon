from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings

from .models import ImmunizationRecord, Reminder

DUE_SOON_WINDOW_DAYS = 30


@dataclass
class WhatsAppDispatchResult:
    sent: bool
    detail: str


def sync_due_reminders(parent_profile):
    """Create/refresh Reminder rows from each child's upcoming or overdue
    ImmunizationRecord entries. Reminders are never typed in by a caregiver --
    they are derived entirely from the vaccination schedule the facility entered.
    Returns the current queryset of reminders for this caregiver's children.
    """
    horizon = date.today() + timedelta(days=DUE_SOON_WINDOW_DAYS)
    due_records = ImmunizationRecord.objects.filter(
        child__parent=parent_profile,
        date_given__isnull=True,
        next_due_date__isnull=False,
        next_due_date__lte=horizon,
    )
    for record in due_records:
        label = f"{record.vaccine_name} ({record.dose_label})" if record.dose_label else record.vaccine_name
        verb = "was due" if record.next_due_date < date.today() else "is due"
        Reminder.objects.update_or_create(
            record=record,
            defaults={
                "child": record.child,
                "message": f"{record.child.name} {verb} for {label} on {record.next_due_date}.",
                "due_date": record.next_due_date,
            },
        )
    # Drop reminders for doses that have since been given or rescheduled outside the window.
    Reminder.objects.filter(child__parent=parent_profile, record__isnull=False).exclude(
        record__in=due_records
    ).delete()
    return Reminder.objects.filter(child__parent=parent_profile).order_by("due_date")


def dispatch_whatsapp_message(phone_number, message):
    """Placeholder integration point for Twilio or Meta WhatsApp Cloud API."""
    if not phone_number:
        return WhatsAppDispatchResult(False, "No phone number on caregiver profile.")

    provider = getattr(settings, "WHATSAPP_PROVIDER", "console")
    if provider == "console":
        print(f"[MwanaCare WhatsApp] To {phone_number}: {message}")
        return WhatsAppDispatchResult(True, "WhatsApp reminder queued in console mode.")

    return WhatsAppDispatchResult(False, "WhatsApp provider is not configured yet.")


def post_immunization_answer(question):
    normalized = question.lower()
    guidance = [
        (
            ("fever", "temperature", "hot"),
            "A mild fever after vaccination is common. Keep the child hydrated, dress them lightly, and seek clinical help if the fever is high, persistent, or the child is unusually sleepy.",
        ),
        (
            ("swelling", "pain", "red", "sore"),
            "A sore or slightly swollen injection site can happen. A clean cool cloth may help. Do not rub the injection site.",
        ),
        (
            ("breastfeed", "feeding", "eat"),
            "Continue normal feeding or breastfeeding. Small frequent feeds are helpful if the child is fussy.",
        ),
        (
            ("emergency", "danger", "rash", "breathing", "convulsion"),
            "Seek urgent care immediately for difficulty breathing, swelling of the face, convulsions, a widespread rash, or if the child becomes very weak.",
        ),
    ]

    for keywords, answer in guidance:
        if any(keyword in normalized for keyword in keywords):
            return answer

    return (
        "Most children have only mild symptoms after immunization. Watch for fever, swelling, feeding changes, or unusual sleepiness. "
        "For worrying symptoms, contact a health worker or visit the nearest facility."
    )
