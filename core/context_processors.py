from .models import ParentProfile
from .services import sync_due_reminders


def active_reminders(request):
    """Feeds the nag banner in base.html. Unlike the Reminders page (which the
    caregiver has to go visit), this makes an unresolved due/overdue reminder follow
    them around the site -- on every page load -- until they act on it, the same way
    Duolingo won't let a broken streak go unnoticed.
    """
    if not request.user.is_authenticated:
        return {}

    profile = ParentProfile.objects.filter(user=request.user).first()
    if profile is None:
        return {}

    reminders = sync_due_reminders(profile).filter(sent=False)
    if not reminders:
        return {}

    # Overdue reminders outrank due-soon ones for the headline slot; sync_due_reminders
    # already orders by due_date so the most overdue/soonest naturally sorts first.
    ordered = sorted(reminders, key=lambda r: (r.urgency != "overdue", r.due_date))
    return {
        "nag_reminder": ordered[0],
        "nag_reminder_extra_count": len(ordered) - 1,
    }
