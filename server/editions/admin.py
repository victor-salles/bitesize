"""Adds queue actions to core's Edition admin."""

from django.contrib import admin, messages

from core.admin import EditionAdmin
from core.models import Edition

from .services import retry_edition


class QueueEditionAdmin(EditionAdmin):
    actions = ["retry_failed"]

    @admin.action(description="Retry selected failed editions")
    def retry_failed(self, request, queryset):
        retried = sum(retry_edition(edition) for edition in queryset.filter(status=Edition.Status.FAILED))
        skipped = queryset.count() - retried
        self.message_user(request, f"Queued {retried} failed edition(s) again.", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped {skipped} edition(s) that had not failed.", messages.WARNING)


admin.site.unregister(Edition)
admin.site.register(Edition, QueueEditionAdmin)
