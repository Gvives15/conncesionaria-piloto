from django.contrib import admin
from django.utils.html import format_html
import json
from .models import Tenant, Contact, Conversation, Message, Attribution, MemoryRecord, Template


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "id", "created_at")
    search_fields = ("name", "id")
    ordering = ("-created_at",)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("contact_key", "tenant", "wa_id", "phone_e164", "profile_name", "created_at", "updated_at")
    list_filter = ("tenant",)
    search_fields = ("contact_key", "wa_id", "phone_e164", "profile_name")
    ordering = ("-updated_at",)
    raw_id_fields = ("tenant",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "contact", "status", "opened_at", "closed_at", "created_at")
    list_filter = ("tenant", "status")
    search_fields = ("id", "contact__contact_key")
    ordering = ("-opened_at",)
    raw_id_fields = ("tenant", "contact")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "tenant", "contact", "direction", "type", "channel", "wamid", "short_text")
    list_filter = ("tenant", "direction", "type", "channel")
    search_fields = ("wamid", "contact__contact_key", "text_body")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    raw_id_fields = ("tenant", "conversation", "contact")
    readonly_fields = ("payload_pretty",)

    def short_text(self, obj):
        return (obj.text_body or "")[:80]

    def payload_pretty(self, obj):
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", json.dumps(obj.payload_json, indent=2, ensure_ascii=False))


@admin.register(Attribution)
class AttributionAdmin(admin.ModelAdmin):
    list_display = ("tenant", "contact", "message_wamid", "source_type", "headline", "captured_at")
    list_filter = ("tenant", "source_type")
    search_fields = ("message_wamid", "headline", "body", "source_id", "ctwa_clid", "contact__contact_key")
    ordering = ("-captured_at",)
    raw_id_fields = ("tenant", "contact")


@admin.register(MemoryRecord)
class MemoryRecordAdmin(admin.ModelAdmin):
    list_display = ("tenant", "contact", "last_user_message_at", "updated_at")
    list_filter = ("tenant",)
    search_fields = ("contact__contact_key",)
    ordering = ("-updated_at",)
    raw_id_fields = ("tenant", "contact")


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("tenant", "name", "category", "language", "active", "updated_at")
    list_filter = ("tenant", "category", "language", "active")
    search_fields = ("name",)
    ordering = ("-updated_at",)
    raw_id_fields = ("tenant",)
