"""Adds queue actions to core's Edition admin."""

from django.contrib import admin, messages

from core.admin import EditionAdmin
from core.models import Edition

from .delivery import resend_delivery
from .services import retry_edition


class QueueEditionAdmin(EditionAdmin):
    actions = ["retry_failed", "resend_delivery"]

    @admin.action(description="Retry selected failed editions")
    def retry_failed(self, request, queryset):
        retried = sum(retry_edition(edition) for edition in queryset.filter(status=Edition.Status.FAILED))
        skipped = queryset.count() - retried
        self.message_user(request, f"Queued {retried} failed edition(s) again.", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped {skipped} edition(s) that had not failed.", messages.WARNING)


    @admin.action(description="Resend delivery of selected editions")
    def resend_delivery(self, request, queryset):
        failed = queryset.filter(delivery_status=Edition.Delivery.FAILED)
        resent = sum(resend_delivery(edition) for edition in failed)
        skipped = queryset.count() - resent
        self.message_user(request, f"Queued {resent} failed delivery again.", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped {skipped} edition(s) whose delivery had not failed.", messages.WARNING)


admin.site.unregister(Edition)
admin.site.register(Edition, QueueEditionAdmin)
