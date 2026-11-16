from math import ceil

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST, require_safe

from core.models import Edition

from .services import enqueue_edition, local_today, queue_status

RECENT_EDITIONS = 10


@login_required
@require_safe
def status(request):
    queue = queue_status(request.user)
    context = {
        "queue": queue,
        "wait_minutes": ceil(queue.estimated_wait.total_seconds() / 60) if queue.estimated_wait is not None else None,
        "can_request": queue.edition is None or queue.edition.status == Edition.Status.FAILED,
        "recent_editions": Edition.objects.filter(user=request.user)[:RECENT_EDITIONS],
    }
    return render(request, "editions/status.html", context)


@login_required
@require_POST
def request_today(request):
    edition = enqueue_edition(request.user, local_today(request.user))
    messages.success(request, f"Your edition for {edition.edition_date:%Y-%m-%d} is {edition.get_status_display().lower()}.")
    return redirect("editions:status")
