from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Child, Referral, ParentProfile


def _widget_attrs(**extra):
    attrs = {"class": "form-control"}
    attrs.update(extra)
    return attrs


class SignUpForm(UserCreationForm):
    # Plain, short username instead of Django's default 150-char field with its
    # "letters, digits and @/./+/-/_ only" help text.
    username = forms.CharField(
        max_length=30,
        label="Name",
        widget=forms.TextInput(attrs=_widget_attrs(maxlength="30", autocomplete="username")),
    )
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs=_widget_attrs()))
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        label="Phone number on file with your health facility",
        help_text="Enter the exact phone number your health facility used when registering you and your child.",
        widget=forms.TextInput(attrs=_widget_attrs()),
    )

    class Meta:
        model = User
        fields = ["username", "email", "phone_number", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("password1", "password2"):
            self.fields[field_name].widget.attrs.update(_widget_attrs())
            # Drop Django's default password-rules bullet list; this page only
            # enforces a simple minimum length (see validate_password_for_user).
            self.fields[field_name].help_text = ""

    def validate_password_for_user(self, user, password_field_name="password2"):
        # Skip the project-wide complexity/common-password/similarity checks for
        # signup specifically; just require a reasonable minimum length.
        password = self.cleaned_data.get(password_field_name)
        if password and len(password) < 6:
            self.add_error(password_field_name, "Password must be at least 6 characters long.")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ParentProfileForm(forms.ModelForm):
    class Meta:
        model = ParentProfile
        fields = ["phone_number", "location"]
        widgets = {
            "phone_number": forms.TextInput(attrs=_widget_attrs()),
            "location": forms.TextInput(attrs=_widget_attrs()),
        }


class FacilitySearchForm(forms.Form):
    location = forms.CharField(
        max_length=200,
        required=False,
        label="Search",
        widget=forms.TextInput(attrs=_widget_attrs(placeholder="Search hospitals, clinics...")),
    )


class ReferralForm(forms.ModelForm):
    class Meta:
        model = Referral
        fields = ["child", "facility"]

    def __init__(self, *args, parent_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        if parent_profile is not None:
            self.fields["child"].queryset = Child.objects.filter(parent=parent_profile)
        self.fields["child"].widget.attrs["class"] = "form-select"
        self.fields["facility"].widget.attrs["class"] = "form-select"


class ReferralCompletionForm(forms.ModelForm):
    class Meta:
        model = Referral
        fields = ["status", "visit_notes"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "visit_notes": forms.Textarea(attrs=_widget_attrs(rows=4)),
        }
