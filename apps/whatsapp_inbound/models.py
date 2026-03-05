import uuid
import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField(null=True, blank=True)
    tenant_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    business_name = models.CharField(max_length=200, null=True, blank=True)
    domain = models.CharField(max_length=80, default="generic")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        key = self.tenant_key or "tenant"
        bn = self.business_name or self.name or ""
        return f"{key} - {bn}"


class Contact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    contact_key = models.TextField()  # "wa:549..."
    wa_id = models.TextField(null=True, blank=True)
    phone_e164 = models.TextField(null=True, blank=True)
    profile_name = models.TextField(null=True, blank=True)
    crm_contact_id = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "contact_key"], name="uniq_contact_key_per_tenant")
        ]
        indexes = [
            models.Index(fields=["tenant", "phone_e164"], name="contacts_phone_idx"),
        ]


class Conversation(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(STATUS_ACTIVE, "active"), (STATUS_CLOSED, "closed")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "contact", "status"], name="conv_active_idx"),
        ]


class Message(models.Model):
    DIR_IN = "in"
    DIR_OUT = "out"
    DIR_CHOICES = [(DIR_IN, "in"), (DIR_OUT, "out")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    direction = models.CharField(max_length=3, choices=DIR_CHOICES)
    channel = models.CharField(max_length=32, default="whatsapp")

    wamid = models.TextField()  # unique per tenant
    timestamp = models.DateTimeField()
    type = models.TextField()
    text_body = models.TextField(null=True, blank=True)

    payload_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "wamid"], name="uniq_wamid_per_tenant")
        ]
        indexes = [
            models.Index(fields=["tenant", "contact", "-timestamp"], name="messages_contact_time_idx"),
        ]


class Attribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    message_wamid = models.TextField(null=True, blank=True)

    source_type = models.TextField(default="unknown")
    ctwa_clid = models.TextField(null=True, blank=True)
    source_id = models.TextField(null=True, blank=True)
    headline = models.TextField(null=True, blank=True)
    body = models.TextField(null=True, blank=True)

    raw_json = models.JSONField(default=dict)
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "contact", "-captured_at"], name="attrib_contact_idx"),
        ]


class MemoryRecord(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)

    summary = models.TextField(default="")
    facts_json = models.JSONField(default=list)

    active_primary_event = models.TextField(null=True, blank=True)
    active_secondary_events = models.JSONField(default=list)
    recent_events = models.JSONField(default=list)
    scores_json = models.JSONField(default=dict)

    last_user_message_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        # Defense in depth: Ensure JSON fields are never None
        if self.active_secondary_events is None:
            logger.warning(f"IntegrityFix: active_secondary_events was None for memory {self.pk}. Defaulting to [].")
            self.active_secondary_events = []
        if self.facts_json is None:
            self.facts_json = []
        if self.recent_events is None:
            self.recent_events = []
        if self.scores_json is None:
            self.scores_json = {}
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "contact"], name="uniq_memory_per_contact")
        ]


class Template(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.TextField()
    category = models.TextField(null=True, blank=True)
    language = models.TextField(null=True, blank=True, default="es_AR")
    components_json = models.JSONField(default=list)
    meta_status = models.CharField(max_length=40, blank=True, default="")
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_template_name_per_tenant")
        ]


class TenantEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, related_name="events")
    name = models.CharField(max_length=80)  # ej: "PEDIDO"
    max_points = models.PositiveIntegerField(default=10)

    # lista JSON: [{ "type":"kw", "value":"precio", "points":5 }, ...]
    triggers = models.JSONField(default=list, blank=True)

    freeform_reply = models.TextField(blank=True, default="")
    template_key = models.CharField(max_length=120, blank=True, default="")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "name")]
        indexes = [
            models.Index(fields=["tenant", "name"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.tenant_key}:{self.name}"


class OutboxEvent(models.Model):
    TOPIC_INBOUND_SAVED = "INBOUND_SAVED"
    TOPIC_CHOICES = [(TOPIC_INBOUND_SAVED, TOPIC_INBOUND_SAVED)]

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_DEAD = "dead"
    STATUS_CHOICES = [
        (STATUS_PENDING, STATUS_PENDING),
        (STATUS_PROCESSING, STATUS_PROCESSING),
        (STATUS_SENT, STATUS_SENT),
        (STATUS_FAILED, STATUS_FAILED),
        (STATUS_DEAD, STATUS_DEAD),
    ]

    topic = models.CharField(max_length=64, choices=TOPIC_CHOICES)
    tenant_id = models.CharField(max_length=128, db_index=True)
    contact_key = models.CharField(max_length=128, db_index=True)
    turn_wamid = models.CharField(max_length=256, db_index=True)

    # idempotencia por etapa
    dedupe_key = models.CharField(max_length=512, unique=True)

    payload_json = models.JSONField(default=dict)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(default=timezone.now, db_index=True)

    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=128, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
