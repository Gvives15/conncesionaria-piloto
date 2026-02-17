import uuid
from django.db import models
from django.utils import timezone


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "contact"], name="uniq_memory_per_contact")
        ]


class Template(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.TextField()
    category = models.TextField(null=True, blank=True)
    language = models.TextField(null=True, blank=True)
    components_json = models.JSONField(default=dict)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_template_name_per_tenant")
        ]
