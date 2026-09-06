from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    FacilitySearchForm,
    ParentProfileForm,
    ReferralCompletionForm,
    ReferralForm,
    SignUpForm,
)
from .models import Child, Facility, ImmunizationRecord, ParentProfile, Referral, Reminder
from .services import dispatch_whatsapp_message, post_immunization_answer, sync_due_reminders


def get_parent_profile(user):
    profile = ParentProfile.objects.filter(user=user).first()
    if profile is not None:
        return profile
    # Safety net for accounts (e.g. staff/superusers) that were never linked to a
    # facility-provided record. Ordinary caregivers get linked at signup instead.
    profile, _ = ParentProfile.objects.get_or_create(user=user, phone_number=f"unset-{user.pk}")
    return profile


def welcome(request):
    return render(request, "welcome.html")


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data["phone_number"]
            profile = ParentProfile.objects.filter(phone_number=phone_number).first()
            if profile is None:
                form.add_error(
                    "phone_number",
                    "We couldn't find any records for this phone number. "
                    "Please confirm it with your health facility, or ask them to register you first.",
                )
            elif profile.user_id is not None:
                form.add_error(
                    "phone_number",
                    "An account is already linked to this phone number. Please log in instead.",
                )
            else:
                user = form.save()
                profile.user = user
                profile.save(update_fields=["user"])
                login(request, user)
                messages.success(
                    request,
                    "Your MwanaCare account is now linked to the records your health facility has on file.",
                )
                return redirect("dashboard")
    else:
        form = SignUpForm()
    return render(request, "signup.html", {"form": form})


@login_required
def dashboard(request):
    profile = get_parent_profile(request.user)
    today = timezone.localdate()
    children = Child.objects.filter(parent=profile)
    upcoming_records = ImmunizationRecord.objects.filter(
        child__parent=profile,
        next_due_date__gte=today,
    ).order_by("next_due_date")[:6]
    reminders = sync_due_reminders(profile).filter(sent=False)[:6]
    recent_visits = Referral.objects.filter(
        child__parent=profile,
        status="Completed",
    ).order_by("-completed_at", "-referral_date")[:6]

    return render(
        request,
        "dashboard.html",
        {
            "children": children,
            "upcoming_records": upcoming_records,
            "reminders": reminders,
            "recent_visits": recent_visits,
            "pending_referrals": Referral.objects.filter(child__parent=profile, status="Pending").count(),
        },
    )


@login_required
def profile(request):
    profile_obj = get_parent_profile(request.user)
    if request.method == "POST":
        form = ParentProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile")
    else:
        form = ParentProfileForm(instance=profile_obj)
    return render(request, "profile.html", {"form": form})


@login_required
def child_list(request):
    profile_obj = get_parent_profile(request.user)
    children = Child.objects.filter(parent=profile_obj)
    return render(request, "child-tracker.html", {"children": children})


@login_required
def records(request):
    """Overview: pick which child's health record to view. No data entry here --
    vaccination history comes entirely from the facility via the admin."""
    profile_obj = get_parent_profile(request.user)
    children = Child.objects.filter(parent=profile_obj)
    if children.count() == 1:
        return redirect("child_health_record", pk=children.first().pk)
    return render(request, "records.html", {"children": children})


@login_required
def child_health_record(request, pk):
    profile_obj = get_parent_profile(request.user)
    child = get_object_or_404(Child, pk=pk, parent=profile_obj)
    immunizations = ImmunizationRecord.objects.filter(child=child).order_by("next_due_date", "date_given")
    return render(
        request,
        "health-record.html",
        {
            "child": child,
            "immunizations": immunizations,
            "growth": child.latest_growth_measurement(),
        },
    )


@login_required
def reminders(request):
    """Reminders are derived automatically from each child's due/overdue
    vaccinations -- there is nothing for a caregiver to type in here."""
    profile_obj = get_parent_profile(request.user)
    if request.method == "POST":
        reminder = get_object_or_404(Reminder, pk=request.POST.get("reminder_id"), child__parent=profile_obj)
        result = dispatch_whatsapp_message(profile_obj.phone_number, reminder.message)
        reminder.sent = result.sent
        reminder.save(update_fields=["sent"])
        messages.success(request, result.detail)
        return redirect("reminders")

    reminder_list = sync_due_reminders(profile_obj)
    return render(request, "reminder.html", {"reminders": reminder_list})


@login_required
def facility_finder(request):
    form = FacilitySearchForm(request.GET or None)
    facilities = Facility.objects.all().order_by("name")
    query = ""
    if form.is_valid():
        query = form.cleaned_data.get("location") or ""
        if query:
            facilities = facilities.filter(
                Q(name__icontains=query) | Q(location__icontains=query) | Q(address__icontains=query)
            )

    active_tag = request.GET.get("tag", "")
    if active_tag:
        facilities = facilities.filter(services__icontains=active_tag)

    return render(
        request,
        "hospital-finder.html",
        {
            "form": form,
            "facilities": facilities,
            "query_location": query,
            "active_tag": active_tag,
            "filter_tags": ["Vaccination", "Paediatrics", "Emergency"],
        },
    )


@login_required
def referrals(request):
    profile_obj = get_parent_profile(request.user)
    if request.method == "POST":
        form = ReferralForm(request.POST, parent_profile=profile_obj)
        if form.is_valid():
            referral = form.save()
            message = f"Referral created for {referral.child.name} to {referral.facility.name}."
            result = dispatch_whatsapp_message(referral.child.parent.phone_number, message)
            messages.success(request, f"{message} {result.detail}")
            return redirect("referrals")
    else:
        form = ReferralForm(parent_profile=profile_obj)

    referral_list = Referral.objects.filter(child__parent=profile_obj).order_by("-referral_date")
    return render(request, "referral.html", {"form": form, "referrals": referral_list})


@login_required
def referral_update(request, pk):
    profile_obj = get_parent_profile(request.user)
    referral = get_object_or_404(Referral, pk=pk, child__parent=profile_obj)
    if request.method == "POST":
        form = ReferralCompletionForm(request.POST, instance=referral)
        if form.is_valid():
            updated = form.save(commit=False)
            if updated.status == "Completed" and not updated.completed_at:
                updated.completed_at = timezone.now()
            updated.save()
            messages.success(request, "Referral record updated.")
            return redirect("referrals")
    else:
        form = ReferralCompletionForm(instance=referral)
    return render(request, "referral-update.html", {"form": form, "referral": referral})


@login_required
def aftercare(request):
    answer = None
    question = ""
    if request.method == "POST":
        question = request.POST.get("question", "")
        answer = post_immunization_answer(question)
    return render(request, "aftercare.html", {"answer": answer, "question": question})
