from django.contrib import admin

from .models import Article, Edition, Profile, Source


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "kindle_email", "language", "timezone", "delivery_time", "sender_approved"]
    list_filter = ["language", "sender_approved", "timezone"]
    search_fields = ["user__username", "kindle_email"]


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "user", "active", "url"]
    list_filter = ["active", "category"]
    search_fields = ["name", "url", "user__username"]


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "edition_date",
        "status",
        "delivery_status",
        "queued_at",
        "started_at",
        "finished_at",
        "article_count",
    ]
    list_filter = ["status", "delivery_status", "edition_date"]
    search_fields = ["user__username", "error"]
    date_hierarchy = "edition_date"


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ["title", "source", "language", "score", "text_length", "updated_at"]
    list_filter = ["language", "source"]
    search_fields = ["title", "url"]
