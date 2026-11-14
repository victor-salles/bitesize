from django.db import connection
from django.db.utils import DatabaseError
from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def healthz(request):
    """Liveness and database check for Dokku and uptime probes."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("database unavailable\n", status=503, content_type="text/plain")
    return HttpResponse("ok\n", content_type="text/plain")
