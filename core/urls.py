from django.urls import path

from . import views


urlpatterns = [
    path("", views.welcome, name="welcome"),
    path("signup/", views.signup, name="signup"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("children/", views.child_list, name="children"),
    path("records/", views.records, name="records"),
    path("children/<int:pk>/records/", views.child_health_record, name="child_health_record"),
    path("reminders/", views.reminders, name="reminders"),
    path("facilities/", views.facility_finder, name="facility_finder"),
    path("referrals/", views.referrals, name="referrals"),
    path("referrals/<int:pk>/update/", views.referral_update, name="referral_update"),
    path("mwanaai/", views.mwanaai, name="mwanaai"),
    path("notes/", views.notes, name="notes"),
    path("notes/<int:pk>/forward/", views.note_forward, name="note_forward"),
]
