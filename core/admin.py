from django.contrib import admin

from .models import Child, Facility, GrowthMeasurement, ImmunizationRecord, Note, ParentProfile, Referral, Reminder


class ChildInline(admin.TabularInline):
    model = Child
    extra = 1


class ImmunizationRecordInline(admin.TabularInline):
    model = ImmunizationRecord
    extra = 1


class GrowthMeasurementInline(admin.TabularInline):
    model = GrowthMeasurement
    extra = 1


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    """Partner facility staff create the caregiver + child records here, ahead of
    the caregiver ever signing up. The caregiver's login is linked automatically
    (by phone_number) the first time they sign up on the site."""

    list_display = ("phone_number", "user", "location", "is_claimed")
    search_fields = ("phone_number", "location", "user__username", "user__email")
    list_filter = ("location",)
    inlines = [ChildInline]

    @admin.display(boolean=True, description="Account linked")
    def is_claimed(self, obj):
        return obj.user_id is not None


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "date_of_birth", "gender", "blood_type")
    search_fields = ("name", "parent__phone_number", "parent__user__username")
    list_filter = ("gender", "blood_type")
    inlines = [ImmunizationRecordInline, GrowthMeasurementInline]


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "facility_type", "location", "rating", "phone")
    list_filter = ("facility_type",)
    search_fields = ("name", "location", "address", "services")
    fields = (
        "name", "facility_type", "rating", "services",
        "address", "location", "latitude", "longitude",
        "phone", "email",
    )


@admin.register(ImmunizationRecord)
class ImmunizationRecordAdmin(admin.ModelAdmin):
    list_display = ("child", "vaccine_name", "dose_label", "date_given", "next_due_date", "facility")
    list_filter = ("vaccine_name", "facility")
    search_fields = ("child__name", "vaccine_name")


@admin.register(GrowthMeasurement)
class GrowthMeasurementAdmin(admin.ModelAdmin):
    list_display = ("child", "measured_on", "height_cm", "weight_kg", "height_percentile", "weight_percentile")
    search_fields = ("child__name",)


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("child", "facility", "status", "referral_date", "completed_at")
    list_filter = ("status", "facility")
    search_fields = ("child__name", "facility__name")


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("child", "due_date", "sent")
    list_filter = ("sent",)
    search_fields = ("child__name", "message")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """Read-only visibility for facility staff -- Mwana Notes are written by the
    caregiver themselves, not entered here."""

    list_display = ("parent", "category", "language", "created_at", "forwarded_to_whatsapp")
    list_filter = ("category", "language", "forwarded_to_whatsapp")
    search_fields = ("parent__phone_number", "parent__user__username", "content")
