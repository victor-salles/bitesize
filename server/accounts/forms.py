import re

from django import forms
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

from core.models import Profile, validate_kindle_email

PIN_PATTERN = re.compile(r"[0-9]{4,6}")
NAME_VALIDATOR = RegexValidator(
    r"^[A-Za-z0-9._-]+$",
    "Use letters, digits, dots, dashes or underscores, without spaces.",
)


def _is_trivial(pin: str) -> bool:
    """All one digit, or a straight run up or down (1234, 9876, 0123)."""
    steps = {int(b) - int(a) for a, b in zip(pin, pin[1:])}
    return steps in ({0}, {1}, {-1})


def validate_pin(pin: str) -> None:
    if not PIN_PATTERN.fullmatch(pin):
        raise forms.ValidationError("The PIN must be 4 to 6 digits.", code="pin_format")
    if _is_trivial(pin):
        raise forms.ValidationError("That PIN is too easy to guess.", code="pin_trivial")


def pin_input(autocomplete: str) -> forms.PasswordInput:
    return forms.PasswordInput(
        attrs={"inputmode": "numeric", "pattern": "[0-9]*", "maxlength": 6, "autocomplete": autocomplete}
    )


NAME_ATTRS = {"autocapitalize": "none", "autocorrect": "off", "spellcheck": "false", "autocomplete": "username"}


class SignupForm(forms.Form):
    name = forms.CharField(
        min_length=2,
        max_length=30,
        validators=[NAME_VALIDATOR],
        help_text="You type this to log in. Letters and digits, no spaces.",
        widget=forms.TextInput(attrs=NAME_ATTRS),
    )
    kindle_email = forms.EmailField(
        label="Send-to-Kindle address",
        validators=[validate_kindle_email],
        help_text="Ends in @kindle.com. Find it on Amazon under Manage Your Content and Devices.",
        widget=forms.EmailInput(attrs={"autocapitalize": "none", "autocorrect": "off", "spellcheck": "false"}),
    )
    pin = forms.CharField(
        label="PIN",
        strip=False,
        help_text="4 to 6 digits. Avoid 1234, 0000 and the like.",
        widget=pin_input("new-password"),
    )
    pin_confirm = forms.CharField(label="PIN again", strip=False, widget=pin_input("new-password"))

    def clean_name(self) -> str:
        name = self.cleaned_data["name"]
        if User.objects.filter(username__iexact=name).exists():
            raise forms.ValidationError("That name is taken.", code="name_taken")
        return name

    def clean_kindle_email(self) -> str:
        return self.cleaned_data["kindle_email"].lower()

    def clean_pin(self) -> str:
        pin = self.cleaned_data["pin"]
        validate_pin(pin)
        return pin

    def clean(self):
        cleaned = super().clean()
        pin, confirm = cleaned.get("pin"), cleaned.get("pin_confirm")
        if pin and confirm is not None and pin != confirm:
            self.add_error("pin_confirm", forms.ValidationError("The PINs do not match.", code="pin_mismatch"))
        return cleaned

    def save(self) -> User:
        data = self.cleaned_data
        user = User.objects.create_user(username=data["name"], password=data["pin"])
        profile = user.profile
        profile.kindle_email = data["kindle_email"]
        profile.save(update_fields=["kindle_email", "updated_at"])
        return user


class LoginForm(forms.Form):
    name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={**NAME_ATTRS, "autofocus": True}))
    pin = forms.CharField(label="PIN", max_length=32, strip=False, widget=pin_input("current-password"))
    next = forms.CharField(required=False, widget=forms.HiddenInput)


class InviteForm(forms.Form):
    note = forms.CharField(label="Who is it for?", max_length=120, required=False)


class DeliveryForm(forms.ModelForm):
    """Where and when a reader's edition arrives."""

    class Meta:
        model = Profile
        fields = ["kindle_email", "delivery_time", "timezone", "language"]
        labels = {
            "kindle_email": "Send-to-Kindle address",
            "delivery_time": "Delivery time",
            "timezone": "Time zone",
            "language": "Edition language",
        }
        help_texts = {
            "kindle_email": "Ends in @kindle.com. Find it on Amazon under Manage Your Content and Devices.",
            "delivery_time": "When the edition should arrive, as HH:MM in your time zone.",
            "timezone": "A name like America/Sao_Paulo or Europe/Lisbon.",
            "language": "Summaries and covers are written in this language.",
        }
        widgets = {
            "kindle_email": forms.EmailInput(attrs={"autocapitalize": "none", "autocorrect": "off", "spellcheck": "false"}),
            "delivery_time": forms.TimeInput(format="%H:%M", attrs={"inputmode": "numeric"}),
            "timezone": forms.TextInput(attrs={"autocapitalize": "none", "autocorrect": "off", "spellcheck": "false"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank in the model so a profile can exist before sign-up sets it; never blank once set here.
        self.fields["kindle_email"].required = True

    def clean_kindle_email(self) -> str:
        return self.cleaned_data["kindle_email"].lower()
