# MwanaCare

MwanaCare is a Django web app that helps caregivers track their children's immunizations, growth, and referrals, and helps them find and reach partner health facilities.

**Core idea:** caregivers never type in medical data. Partner hospitals/clinics enter parent, child, vaccination, and growth records ahead of time (via the Django admin); a caregiver's account is only *linked* to the records their facility already has, by matching phone number at signup. Reminders are generated automatically from the vaccination schedule — there's no "add reminder" form.

## Tech stack

- Python 3, Django 6.1
- SQLite (default dev database)
- Bootstrap 5 (via CDN) for styling
- Leaflet + OpenStreetMap (via CDN, no API key) for the facility map

## Project layout

```
mwanacare/
  manage.py
  requirements.txt
  db.sqlite3              # dev database (created by migrate)
  mwanacare/               # project settings, root urls
  core/                    # the app: models, views, forms, admin, templates
    models.py              # ParentProfile, Child, Facility, ImmunizationRecord,
                            # GrowthMeasurement, Referral, Reminder, Note
    admin.py                # where hospital staff enter caregiver/child/vaccine data
    views.py, urls.py, forms.py
    services.py             # WhatsApp dispatch stub, aftercare-question guidance,
                            # auto-reminder generation
    templates/
```

## Setup

```bash
cd mwanacare
python -m venv venv

# Windows (Git Bash)
source venv/Scripts/activate
# Windows (PowerShell)
# venv\Scripts\Activate.ps1
# macOS/Linux
# source venv/bin/activate

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser   # for /admin/ access — prompts for username/email/password
python manage.py runserver
```

Then open `http://127.0.0.1:8000/`.

## How data gets in: the admin comes first

Because caregivers only ever link to existing records, **every new caregiver needs a record created in `/admin/` before they can sign up**:

1. Log in to `http://127.0.0.1:8000/admin/` with the superuser account.
2. Under **Core → Parent profiles**, click **Add parent profile**.
3. Fill in `phone_number` (this is the key the caregiver will sign up with) and `location`. Leave `user` blank — it fills in automatically when the caregiver signs up.
4. Add their child(ren) right there in the inline **Children** section (name, date of birth, gender, blood type, allergies).
5. Open a saved **Child** to add **Immunization records** and **Growth measurements** inline — these populate that child's Health Record page and drive auto-generated reminders.
6. Under **Core → Facilities**, add partner hospitals/clinics: name, type, address, `location`, phone/email, `services` (comma-separated tags like `Paediatrics, Immunisation, Emergency`), an optional `rating`, and `latitude`/`longitude` if you want them to show as a pin on the facility map.

## Signing up as a caregiver

`/signup/` asks for a name, email, password, and the **exact phone number** the facility used in step 3 above:

- No matching phone number → signup is rejected with a message to contact the facility.
- Matching but already linked to another account → told to log in instead.
- Matching and unclaimed → a login is created and immediately linked to that `ParentProfile` (and all its children).

Logging in afterwards (`/accounts/login/`) is a normal username/password Django login — the phone number only matters once, at signup.

## Features

| Page | What it shows |
|---|---|
| Dashboard | Children, upcoming vaccinations, active reminders, recent completed referral visits |
| Children | Read-only list of the caregiver's children (facility-provided) |
| Health Records (`/records/`, then per child) | Blood type, allergies, latest growth measurement with percentiles, and a full vaccination timeline with status pills (Completed / Due soon / Overdue / Upcoming) |
| Reminders | Auto-generated from any vaccination due within 30 days or overdue; a "Notify via WhatsApp" button dispatches the message (console-logged in dev — see below). A persistent nag banner (see below) also follows the caregiver around the site until each reminder is resolved |
| Facilities | Search + tag filters (Vaccination/Paediatrics/Emergency) over partner facilities, with a live map (Leaflet/OpenStreetMap) and, if the browser grants location access via native GPS, distance sorting |
| Referrals | Caregiver-initiated: request a referral for a child to a facility, and mark it completed with visit notes afterward |
| MwanaAI (`/mwanaai/`) | Keyword-based guidance for common post-vaccination and child health questions, in English/Kiswahili/Luganda, typed or spoken via the browser's built-in voice input |
| Mwana Notes (`/notes/`) | The one place a caregiver enters their own data: health notes, bills paid, or outstanding debts, typed or spoken in any of the three languages, with a one-click "Send to WhatsApp" to keep a copy on their phone |

## Persistent reminder nudges

Any unresolved reminder (due within 30 days, or overdue) shows as a banner at the top
of every page — not just the Reminders page — via a `active_reminders` context
processor (`core/context_processors.py`). It turns red and pulses once a vaccination
is actually overdue. The banner keeps reappearing on each page load until the
caregiver resolves the underlying reminder (via the "Notify via WhatsApp" button on
`/reminders/`), the same way a Duolingo streak nag won't go away on its own.

## MwanaAI and voice input

MwanaAI (`core/services.py::post_immunization_answer`) is deliberately simple keyword
matching rather than a real language model — predictable answers matter more than
cleverness in a clinical context. The mic button on both MwanaAI and Mwana Notes uses
the browser's native `SpeechRecognition`/`webkitSpeechRecognition` API (no external
API key, Chrome/Edge only) to transcribe speech into the text field; the language
picker drives both the recognition locale and which translated answer comes back. The
Kiswahili/Luganda strings are best-effort prototype translations and should be
reviewed by a clinician or native speaker before this is used with real caregivers.

## WhatsApp integration

`core/services.py` has a `dispatch_whatsapp_message` stub. By default (`WHATSAPP_PROVIDER` unset, or `"console"`) it just prints the message to the server console instead of sending it — useful for development. To wire up a real provider (e.g. Twilio, Meta WhatsApp Cloud API), set `WHATSAPP_PROVIDER` in `mwanacare/settings.py` and extend that function. Reminders, referrals, and Mwana Notes ("Send to WhatsApp") all go through this same stub.

## Notes for development

- `DEBUG = True` and a hardcoded `SECRET_KEY` in `settings.py` are fine for local dev only — replace both before deploying anywhere real.
- The facility map only plots facilities that have `latitude`/`longitude` set in admin; others still appear as cards, just without a pin or distance badge.
- Password rules on the signup page are intentionally relaxed (minimum 6 characters) compared to the rest of the site (e.g. admin password changes still use Django's full validator set).
