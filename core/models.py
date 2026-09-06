from datetime import date

from django.db import models
from django.contrib.auth.models import User


BLOOD_TYPE_CHOICES = [
    ("O+", "O Positive (O+)"),
    ("O-", "O Negative (O-)"),
    ("A+", "A Positive (A+)"),
    ("A-", "A Negative (A-)"),
    ("B+", "B Positive (B+)"),
    ("B-", "B Negative (B-)"),
    ("AB+", "AB Positive (AB+)"),
    ("AB-", "AB Negative (AB-)"),
]


class ParentProfile(models.Model):
    # Created by partner facility staff (via the admin) before the caregiver ever
    # signs up, so `user` starts out unset. It is filled in once the caregiver
    # creates a login and is matched to this record by phone_number.
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        help_text="Used to match a caregiver's login to the records their health facility already entered.",
    )
    location = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.user.username if self.user else f"Unclaimed profile ({self.phone_number})"

class Child(models.Model):
    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=[('M','Male'),('F','Female')])
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPE_CHOICES, blank=True)
    allergies = models.CharField(
        max_length=300,
        blank=True,
        help_text="Comma-separated, e.g. Penicillin, Peanuts. Leave blank if none known.",
    )

    def __str__(self):
        caregiver = self.parent.user.username if self.parent.user else self.parent.phone_number
        return f"{self.name} ({caregiver})"

    @property
    def age_display(self):
        today = date.today()
        months = (today.year - self.date_of_birth.year) * 12 + (today.month - self.date_of_birth.month)
        if today.day < self.date_of_birth.day:
            months -= 1
        months = max(months, 0)
        if months < 24:
            return f"{months} month{'s' if months != 1 else ''}"
        years = months // 12
        return f"{years} year{'s' if years != 1 else ''}"

    @property
    def allergy_list(self):
        return [a.strip() for a in self.allergies.split(",") if a.strip()]

    def latest_growth_measurement(self):
        return self.growthmeasurement_set.order_by("-measured_on").first()

class Facility(models.Model):
    FACILITY_TYPE_CHOICES = [
        ("public", "Public Hospital"),
        ("private", "Private Hospital"),
        ("clinic", "Clinic"),
        ("health_centre", "Health Centre"),
    ]

    name = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=200)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    facility_type = models.CharField(max_length=20, choices=FACILITY_TYPE_CHOICES, default="public")
    rating = models.DecimalField(
        max_digits=2, decimal_places=1, null=True, blank=True,
        help_text="Out of 5, e.g. 4.8. Leave blank if not yet rated.",
    )
    services = models.CharField(
        max_length=300,
        blank=True,
        help_text="Comma-separated tags shown as filters, e.g. Paediatrics, Immunisation, Emergency.",
    )

    def __str__(self):
        return self.name

    @property
    def service_list(self):
        return [s.strip() for s in self.services.split(",") if s.strip()]

class ImmunizationRecord(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    vaccine_name = models.CharField(max_length=100)
    dose_label = models.CharField(
        max_length=50, blank=True, help_text="e.g. Dose 3, Booster. Shown alongside the vaccine name.",
    )
    date_given = models.DateField(null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True)
    facility = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.child.name} - {self.vaccine_name}"

    @property
    def status(self):
        today = date.today()
        if self.date_given:
            return "Completed"
        if self.next_due_date:
            if self.next_due_date < today:
                return "Overdue"
            if (self.next_due_date - today).days <= 30:
                return "Due soon"
        return "Upcoming"

class GrowthMeasurement(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    measured_on = models.DateField(default=date.today)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    height_percentile = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="e.g. 65 for 65th percentile.",
    )
    weight_percentile = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-measured_on"]

    def __str__(self):
        return f"{self.child.name} growth on {self.measured_on}"

class Referral(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    referral_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('Pending','Pending'),
        ('Completed','Completed'),
        ('Cancelled','Cancelled')
    ], default='Pending')
    visit_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Referral for {self.child.name} to {self.facility.name}"

class Reminder(models.Model):
    # Auto-generated from a child's upcoming/overdue ImmunizationRecord entries
    # (see services.sync_due_reminders) rather than typed in by a caregiver.
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    record = models.ForeignKey(ImmunizationRecord, on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    due_date = models.DateField()
    sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"Reminder for {self.child.name} on {self.due_date}"
