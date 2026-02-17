from ninja import NinjaAPI
from django.db import transaction, IntegrityError, connection
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from .schemas import WANormalizedInbound, MessageLogResponse, MessageLogItem
from .models import Tenant, Contact, Conversation, Message, Attribution, MemoryRecord

api = NinjaAPI()


def _get_or_create_tenant(tenant_id: str) -> Tenant:
    # MVP: si tenant_id viene “concesionaria_001”, lo mapeás a un registro real.
    # Si querés que tenant_id sea UUID real, cambiás el schema.
    tenant, _ = Tenant.objects.get_or_create(name=tenant_id)
    return tenant


@api.post("/v1/whatsapp/inbound")
def whatsapp_inbound(request, payload: WANormalizedInbound):
    tenant = _get_or_create_tenant(payload.tenant_id)

    contact_key = payload.contact.contact_key
    wamid = payload.message.wamid

    # timestamp ISO -> datetime
    ts = parse_datetime(payload.message.timestamp)
    if ts is None:
        return 400, {"ok": False, "error": "invalid message.timestamp (expected ISO datetime)"}
    if timezone.is_naive(ts):
        ts = timezone.make_aware(ts, timezone=timezone.utc)

    # 1) DEDUPE rápido (si ya existe mensaje, corto)
    if Message.objects.filter(tenant=tenant, wamid=wamid).exists():
        return {"ok": True, "deduped": True}

    try:
        with transaction.atomic():
            # 2) Upsert Contact
            contact, created = Contact.objects.get_or_create(
                tenant=tenant,
                contact_key=contact_key,
                defaults={
                    "wa_id": payload.contact.wa_id,
                    "profile_name": payload.contact.profile_name,
                    "updated_at": timezone.now(),
                },
            )
            if not created:
                changed = False
                if payload.contact.wa_id and contact.wa_id != payload.contact.wa_id:
                    contact.wa_id = payload.contact.wa_id
                    changed = True
                if payload.contact.profile_name and contact.profile_name != payload.contact.profile_name:
                    contact.profile_name = payload.contact.profile_name
                    changed = True
                if changed:
                    contact.updated_at = timezone.now()
                    contact.save(update_fields=["wa_id", "profile_name", "updated_at"])

            # 3) Conversation activa
            conv = (
                Conversation.objects.filter(tenant=tenant, contact=contact, status=Conversation.STATUS_ACTIVE)
                .order_by("-opened_at")
                .first()
            )
            if conv is None:
                conv = Conversation.objects.create(tenant=tenant, contact=contact, status=Conversation.STATUS_ACTIVE)

            # 4) Insert Message inbound (idempotencia real por unique constraint)
            text_body = None
            if payload.message.type == "text":
                text_body = (payload.message.text.body if payload.message.text else None)

            msg = Message.objects.create(
                tenant=tenant,
                conversation=conv,
                contact=contact,
                direction=Message.DIR_IN,
                channel=payload.channel,
                wamid=wamid,
                timestamp=ts,
                type=payload.message.type,
                text_body=text_body,
                payload_json={
                    "metadata": payload.metadata.model_dump(),
                    "message_raw": payload.message.raw,
                    "referral": payload.referral,
                    "value_raw": payload.raw,
                    "trace_id": payload.trace_id,
                },
            )

            # 5) Attribution (si existe referral real)
            if payload.referral:
                # Meta referral suele tener: source_type, source_id, ctwa_clid, headline, body, image_url, etc.
                Attribution.objects.create(
                    tenant=tenant,
                    contact=contact,
                    message_wamid=wamid,
                    source_type=str(payload.referral.get("source_type") or "unknown"),
                    ctwa_clid=payload.referral.get("ctwa_clid"),
                    source_id=payload.referral.get("source_id"),
                    headline=payload.referral.get("headline"),
                    body=payload.referral.get("body"),
                    raw_json=payload.referral,
                )

            # 6) MemoryRecord mínimo (solo timestamps)
            MemoryRecord.objects.get_or_create(
                tenant=tenant,
                contact=contact,
                defaults={
                    "last_user_message_at": ts,
                    "updated_at": timezone.now(),
                },
            )
            MemoryRecord.objects.filter(tenant=tenant, contact=contact).update(
                last_user_message_at=ts,
                updated_at=timezone.now(),
            )

            return {
                "ok": True,
                "deduped": False,
                "tenant": str(tenant.id),
                "contact_id": str(contact.id),
                "conversation_id": str(conv.id),
                "turn_wamid": wamid,
            }

    except IntegrityError:
        # si hubo carrera y entró duplicado por wamid, lo tratamos como dedupe
        return {"ok": True, "deduped": True}


@api.get("/health")
def health(request):
    return {"ok": True}


@api.get("/health/db")
def health_db(request):
    try:
        connection.ensure_connection()
        engine = connection.settings_dict.get("ENGINE", "")
        name = connection.settings_dict.get("NAME", "")
        return {"db_ok": True, "engine": engine, "name": name}
    except Exception as e:
        return 500, {"db_ok": False, "error": str(e)}


@api.get("/v1/whatsapp/inbound/logs", response=MessageLogResponse)
def whatsapp_inbound_logs(request, tenant_id: str | None = None, limit: int = 50):
    qs = Message.objects.order_by("-timestamp")
    if tenant_id:
        t = Tenant.objects.filter(name=tenant_id).first()
        if not t:
            return {"items": []}
        qs = qs.filter(tenant=t)
    qs = qs.select_related("tenant", "contact")[: max(1, min(limit, 200))]
    items = []
    for m in qs:
        items.append(
            MessageLogItem(
                tenant=m.tenant.name,
                contact_key=m.contact.contact_key,
                wamid=m.wamid,
                timestamp=m.timestamp.isoformat(),
                type=m.type,
                text_body=m.text_body,
                channel=m.channel,
            )
        )
    return {"items": items}
