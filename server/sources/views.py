from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from core.models import Source

from . import catalogue
from .forms import AddSourceForm


def _render_list(request, form=None, status=200):
    sources = Source.objects.filter(user=request.user).order_by("category", "name")
    followed = {source.url for source in sources}
    grouped: dict[str, list[Source]] = {}
    for source in sources:
        grouped.setdefault(source.category, []).append(source)
    offered = [
        (category, [{"name": name, "url": url, "added": url in followed} for name, url in feeds.items()])
        for category, feeds in catalogue.load().items()
    ]
    context = {
        "grouped_sources": grouped,
        "catalogue": offered,
        "form": form or AddSourceForm(user=request.user),
        "categories": sorted(grouped),
    }
    return render(request, "sources/source_list.html", context, status=status)


@login_required
@require_safe
def source_list(request):
    return _render_list(request)


@login_required
@require_POST
def add_source(request):
    form = AddSourceForm(request.POST, user=request.user)
    if form.is_valid():
        try:
            source = form.save()
        except IntegrityError:
            form.add_error("url", "You already follow this feed.")
        else:
            messages.success(request, f"Added {source.name}.")
            return redirect("sources:list")
    return _render_list(request, form=form)


@login_required
@require_POST
def pick_source(request):
    category = request.POST.get("category", "")
    name = request.POST.get("name", "")
    url = catalogue.lookup(category, name)
    if url is None:
        raise Http404("Not in the catalogue")
    _source, created = Source.objects.get_or_create(
        user=request.user, url=url, defaults={"name": name, "category": category}
    )
    if created:
        messages.success(request, f"Added {name}.")
    else:
        messages.info(request, f"You already follow {name}.")
    return redirect("sources:list")


@login_required
@require_POST
def toggle_source(request, pk):
    source = get_object_or_404(Source, pk=pk, user=request.user)
    source.active = not source.active
    source.save(update_fields=["active"])
    messages.success(request, f"{source.name} is now {'on' if source.active else 'off'}.")
    return redirect("sources:list")


@login_required
@require_POST
def delete_source(request, pk):
    source = get_object_or_404(Source, pk=pk, user=request.user)
    source.delete()
    messages.success(request, f"Removed {source.name}.")
    return redirect("sources:list")
