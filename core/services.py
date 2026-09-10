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


# Keyword-matched, not a real language model -- MwanaAI's guidance is intentionally
# simple so it's predictable in a clinical context. Swahili/Luganda strings below are
# best-effort prototype translations; have a clinician/native speaker review them
# before this is used with real caregivers.
GUIDANCE_TOPICS = [
    {
        "keywords": {
            "en": ("fever", "temperature", "hot"),
            "sw": ("homa", "joto"),
            "lg": ("omusujja",),
        },
        "answer": {
            "en": "A mild fever after vaccination is common. Keep the child hydrated, dress them lightly, and seek clinical help if the fever is high, persistent, or the child is unusually sleepy.",
            "sw": "Homa kidogo baada ya chanjo ni jambo la kawaida. Mpe mtoto maji ya kutosha, mvalishe nguo nyepesi, na mtafute msaada wa kliniki ikiwa homa ni kali, inaendelea, au mtoto ana usingizi usio wa kawaida.",
            "lg": "Omusujja omutono oluvannyuma lw'okugema kya bulijjo. Wa omwana amazzi mangi, mwambaze engoye empewufu, era noonye obuyambi bw'abasawo singa omusujja gunywevu, gugenda mu maaso, oba omwana yeebase ennyo.",
        },
    },
    {
        "keywords": {
            "en": ("swelling", "pain", "red", "sore"),
            "sw": ("uvimbe", "maumivu", "kuwasha"),
            "lg": ("okuzimba", "obulumi"),
        },
        "answer": {
            "en": "A sore or slightly swollen injection site can happen. A clean cool cloth may help. Do not rub the injection site.",
            "sw": "Mahali palipochomwa sindano panaweza kuuma au kuvimba kidogo. Kitambaa safi na baridi kinaweza kusaidia. Usisugue mahali hapo.",
            "lg": "Ekifo we baamusinga ekiti kiyinza okuluma oba okuzimbako katono. Ekitambaala ekyewevu era ekinnyogovu kiyinza okuyamba. Toweewa kifo ekyo.",
        },
    },
    {
        "keywords": {
            "en": ("breastfeed", "feeding", "eat"),
            "sw": ("kunyonyesha", "kula", "lisha"),
            "lg": ("okuyonsa", "okulya"),
        },
        "answer": {
            "en": "Continue normal feeding or breastfeeding. Small frequent feeds are helpful if the child is fussy.",
            "sw": "Endelea kunyonyesha au kulisha mtoto kama kawaida. Milo midogo midogo mara kwa mara husaidia ikiwa mtoto anakereka.",
            "lg": "Weyongere okuyonsa oba okuliisa omwana nga bulijjo. Okumuliisa katono katono emirundi mingi kiyamba singa omwana tafaayo.",
        },
    },
    {
        "keywords": {
            "en": ("emergency", "danger", "rash", "breathing", "convulsion"),
            "sw": ("dharura", "hatari", "vipele", "kupumua", "degedege"),
            "lg": ("obulabe", "amawewo", "okussa"),
        },
        "answer": {
            "en": "Seek urgent care immediately for difficulty breathing, swelling of the face, convulsions, a widespread rash, or if the child becomes very weak.",
            "sw": "Tafuta msaada wa dharura mara moja ikiwa mtoto ana shida ya kupumua, uvimbe wa uso, degedege, vipele vinavyoenea, au akiwa dhaifu sana.",
            "lg": "Noonya obuyambi mangu ddala singa omwana afuna obuzibu okussa, amaaso okuzimba, okukwatibwa ekifafanyi, obulwadde bw'olususu obubunya, oba n'anafuwa nnyo.",
        },
    },
]

GUIDANCE_FALLBACK = {
    "en": "Most children have only mild symptoms after immunization. Watch for fever, swelling, feeding changes, or unusual sleepiness. For worrying symptoms, contact a health worker or visit the nearest facility.",
    "sw": "Watoto wengi hupata dalili ndogo tu baada ya chanjo. Angalia homa, uvimbe, mabadiliko ya kulisha, au usingizi usio wa kawaida. Kwa dalili za kutisha, wasiliana na mhudumu wa afya au tembelea kituo cha karibu.",
    "lg": "Abaana abasinga baba n'obubonero butono oluvannyuma lw'okugema. Weekuume ku musujja, okuzimba, enkyukakyuka mu kuliisa, oba okwebaka okutali kwa bulijjo. Bwe wabaawo obubonero obutiisa, tuukirira omusawo oba dduukiro erisembayo.",
}


def post_immunization_answer(question, language="en"):
    normalized = question.lower()
    if language not in ("en", "sw", "lg"):
        language = "en"

    for topic in GUIDANCE_TOPICS:
        # Match against keywords in every language, not just the selected one, so a
        # caregiver typing/speaking in Swahili or Luganda still gets a hit even if
        # the UI language picker is left on English.
        all_keywords = [kw for kws in topic["keywords"].values() for kw in kws]
        if any(keyword in normalized for keyword in all_keywords):
            return topic["answer"].get(language) or topic["answer"]["en"]

    return GUIDANCE_FALLBACK[language]


def forward_note_to_whatsapp(note):
    """Sends a Mwana Note to the caregiver's own WhatsApp for safekeeping, via the
    same dispatch stub reminders/referrals already use."""
    category_label = note.get_category_display()
    message = f"[MwanaCare - {category_label}] {note.content}"
    return dispatch_whatsapp_message(note.parent.phone_number, message)
