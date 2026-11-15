from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .forms import validate_pin
from .models import Invite


class PinResetForm(AdminPasswordChangeForm):
    """Lets Victor reset a user's PIN. Staff keep Django's strong-password rules."""

    def validate_password_for_user(self, user, **kwargs):
        if user.is_staff or not self.cleaned_data.get("set_usable_password", True):
            return super().validate_password_for_user(user, **kwargs)
        password_field_name = kwargs.get("password_field_name", "password2")
        pin = self.cleaned_data.get(password_field_name)
        if pin:
            try:
                validate_pin(pin)
            except ValidationError as error:
                self.add_error(password_field_name, error)


admin.site.unregister(User)


@admin.register(User)
class PinUserAdmin(UserAdmin):
    change_password_form = PinResetForm


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ["note", "status", "created_by", "created_at", "expires_at", "used_by", "used_at"]
    search_fields = ["note", "used_by__username"]
    readonly_fields = ["token", "created_at", "used_at", "used_by"]
