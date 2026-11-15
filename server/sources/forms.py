from django import forms
from django.core.validators import URLValidator

from core.models import Source

from .feeds import FeedError, validate_feed


class AddSourceForm(forms.Form):
    url = forms.URLField(
        label="Feed address",
        max_length=1000,
        assume_scheme="https",
        validators=[URLValidator(schemes=["http", "https"])],
    )
    name = forms.CharField(label="Name", max_length=120, required=False, help_text="Leave blank to use the feed's title.")
    category = forms.CharField(label="Section", max_length=80)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.feed_title = ""

    def clean_url(self):
        url = self.cleaned_data["url"]
        if Source.objects.filter(user=self.user, url=url).exists():
            raise forms.ValidationError("You already follow this feed.", code="duplicate")
        try:
            self.feed_title = validate_feed(url)
        except FeedError as exc:
            raise forms.ValidationError(str(exc), code="not_a_feed") from exc
        return url

    def save(self) -> Source:
        data = self.cleaned_data
        name = data["name"].strip() or self.feed_title[:120] or data["url"][:120]
        return Source.objects.create(user=self.user, url=data["url"], name=name, category=data["category"].strip())
