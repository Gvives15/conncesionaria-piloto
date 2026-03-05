from ninja import Router, NinjaAPI
import os
import time
import httpx
from typing import Any, Dict, List
import asyncio
from django.db import transaction, IntegrityError, connection
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from .schemas import (
    WANormalizedInbound,
    MessageLogResponse,
    MessageLogItem,
    SeedEventsIn,
    SeedTemplatesIn,
)
from .models import (
    Tenant,
    Contact,
    Conversation,
    Message,
    Attribution,
    MemoryRecord,
    TenantEvent,
    Template,
    OutboxEvent,
)

router = Router()


def _get_or_create_tenant(tenant_id: str) -> Tenant:
    t = Tenant.objects.filter(tenant_key=tenant_id).first()
    if t:
        return t
    t = Tenant.objects.filter(name=tenant_id).first()
    if t:
        if not t.tenant_key:
            t.tenant_key = tenant_id
            if not t.business_name:
                t.business_name = t.name or tenant_id
            t.save(update_fields=["tenant_key", "business_name"])
        return t
    tenant, _ = Tenant.objects.get_or_create(
        tenant_key=tenant_id,
        defaults={"business_name": tenant_id, "name": tenant_id},
    )
    return tenant


@router.post("/v1/tenants/events/seed")
def seed_events(request, payload: SeedEventsIn):
    # 1) tenant
    tenant = _get_or_create_tenant(payload.tenant_id)
    if payload.business_name and tenant.business_name != payload.business_name:
        tenant.business_name = payload.business_name
        tenant.save(update_fields=["business_name", "updated_at"])

    created = 0
    updated = 0

    # 2) upsert eventos
    for ev in payload.events:
        _, was_created = TenantEvent.objects.update_or_create(
            tenant=tenant,
            name=ev.name,
            defaults={
                "max_points": ev.max_points,
                "triggers": [t.model_dump() for t in ev.triggers],
                "freeform_reply": ev.freeform_reply,
                "template_key": ev.template_key or "",
                "is_active": True,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {
        "ok": True,
        "tenant_id": tenant.tenant_key or payload.tenant_id,
        "created": created,
        "updated": updated,
        "total": created + updated,
    }


@router.post("/v1/tenants/templates/seed")
def seed_templates(request, payload: SeedTemplatesIn):
    # 1) tenant
    tenant = _get_or_create_tenant(payload.tenant_id)

    created = 0
    updated = 0

    # 2) upsert templates
    for tmpl in payload.templates:
        _, was_created = Template.objects.update_or_create(
            tenant=tenant,
            name=tmpl.name,
            defaults={
                "category": tmpl.category,
                "language": tmpl.language,
                "components_json": tmpl.components_json,
                "meta_status": tmpl.meta_status,
                "active": True,
                "updated_at": timezone.now(),
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {
        "ok": True,
        "tenant_id": tenant.tenant_key or payload.tenant_id,
        "created": created,
        "updated": updated,
        "total": created + updated,
    }


from asgiref.sync import sync_to_async

def _process_inbound_db_sync(payload: WANormalizedInbound, tenant_id_in: str):
    tenant = _get_or_create_tenant(tenant_id_in)

    contact_key = payload.contact.contact_key
    wamid = payload.message.wamid

    # timestamp ISO -> datetime
    ts = parse_datetime(payload.message.timestamp)
    if ts is None:
        return {"status": 400, "body": {"ok": False, "error": "invalid message.timestamp (expected ISO datetime)"}}
    if timezone.is_naive(ts):
        ts = timezone.make_aware(ts, timezone=timezone.utc)

    # 1) DEDUPE rápido (si ya existe mensaje, corto)
    # We rely on DB IntegrityError for Message(tenant, wamid) unique constraint.
    # This saves 1 query.

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

            # 3) Conversation activa (opcional, se mantiene por auditoría)
            conv = (
                Conversation.objects.filter(tenant=tenant, contact=contact, status=Conversation.STATUS_ACTIVE)
                .order_by("-opened_at")
                .first()
            )
            if conv is None:
                conv = Conversation.objects.create(tenant=tenant, contact=contact, status=Conversation.STATUS_ACTIVE)

            # 4) Insert Message inbound (solo audit, SIN decisiones)
            text_body = None
            if payload.message.type == "text":
                text_body = (payload.message.text.body if payload.message.text else None)

            # This might raise IntegrityError if wamid exists -> caught below
            Message.objects.create(
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

            # 5) Attribution (si existe referral real) — opcional
            if payload.referral:
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

            # 6) MemoryRecord: SOLO timestamps (contexto lo arma motor_response consultando BD)
            mem, _ = MemoryRecord.objects.get_or_create(
                tenant=tenant,
                contact=contact,
                defaults={
                    "last_user_message_at": ts,
                    "updated_at": timezone.now(),
                },
            )
            MemoryRecord.objects.filter(id=mem.id).update(
                last_user_message_at=ts,
                updated_at=timezone.now(),
            )
        
            # Prepare data for Outbox/N8N
            phone_number_id = payload.metadata.phone_number_id or ""
            
            webhook_payload = {
                "tenant_id": tenant.tenant_key or tenant_id_in,
                "contact_key": contact.contact_key,
                "wa_id": contact.wa_id,
                "phone_number_id": phone_number_id,
                "turn_wamid": wamid,
                "text": text_body,
                "timestamp_in": payload.message.timestamp,
                "channel": payload.channel,
            }

            # 7) OUTBOX on_commit (idempotente)
            # Encolamos el evento para que un worker posterior (o cron) lo envíe a n8n.
            # O incluso, si mantenemos el push, podemos hacerlo aquí pero garantizando atomicidad.
            # Según instrucción A2: "encolar OutboxEvent en transaction.on_commit"
            
            def enqueue_outbox():
                dedupe_key = f"{webhook_payload['tenant_id']}::{wamid}::INBOUND_SAVED"
                try:
                    OutboxEvent.objects.create(
                        topic=OutboxEvent.TOPIC_INBOUND_SAVED,
                        tenant_id=webhook_payload["tenant_id"],
                        contact_key=webhook_payload["contact_key"],
                        turn_wamid=wamid,
                        dedupe_key=dedupe_key,
                        payload_json=webhook_payload,
                        status=OutboxEvent.STATUS_PENDING,
                        next_retry_at=timezone.now(),
                    )
                except IntegrityError:
                    # ya estaba encolado
                    pass

            transaction.on_commit(enqueue_outbox)

        return {
            "status": 200, 
            "body": {
                "ok": True,
                "deduped": False,
                "tenant_id": tenant.tenant_key or tenant_id_in,
                "contact_key": contact.contact_key,
                "turn_wamid": wamid,
            },
            # No retornamos webhook_payload para que el view no intente enviarlo
            "webhook_payload": None 
        }

    except IntegrityError:
        # Esto atrapa duplicados de Message (unique wamid)
        return {"status": 200, "body": {"ok": True, "deduped": True, "tenant_id": tenant.tenant_key or tenant_id_in, "turn_wamid": wamid}}


@router.post("/v1/whatsapp/inbound")
async def whatsapp_inbound(request, payload: List[WANormalizedInbound]):
    t_start_req = time.time()
    
    # Process the first item for now (MVP) or loop if needed.
    if not payload:
        return {"ok": True, "ignored": "empty_list"}
        
    # We take the first one as primary for response/logging
    normalized_payload = payload[0]
    
    print(f"[API-INBOUND] {t_start_req:.4f} | WAMID: {normalized_payload.message.wamid} | Received Request (List Batch size: {len(payload)})")

    # 1) DB Operations (Sync -> Async wrapper)
    # Ahora esto incluye la creación del OutboxEvent en la misma transacción lógica
    t_db_start = time.time()
    result = await sync_to_async(_process_inbound_db_sync)(normalized_payload, normalized_payload.tenant_id)
    t_db_end = time.time()
    print(f"[API-DB] {t_db_end:.4f} | WAMID: {normalized_payload.message.wamid} | DB Sync Done | Duration: {t_db_end - t_db_start:.4f}s")
    
    if result.get("status", 200) != 200:
        return result["status"], result["body"]
    
    body = result["body"]
    
    # El envío directo a n8n se ha ELIMINADO en favor del Outbox pattern.
    # Un proceso separado (worker) deberá leer OutboxEvent y enviarlo.
    # Por ahora, solo confirmamos recepción y encolado.

    t_api_end = time.time()
    wamid_log_end = body.get('turn_wamid', 'unknown')
    print(f"[API-RESPONSE] {t_api_end:.4f} | WAMID: {wamid_log_end} | Sending 200 OK to Meta | Total Request Time: {t_api_end - t_start_req:.4f}s")
    return body


@router.get("/health")
def health(request):
    return {"ok": True}


@router.get("/health/db")
def health_db(request):
    try:
        connection.ensure_connection()
        engine = connection.settings_dict.get("ENGINE", "")
        name = connection.settings_dict.get("NAME", "")
        return {"db_ok": True, "engine": engine, "name": name}
    except Exception as e:
        return 500, {"db_ok": False, "error": str(e)}


@router.get("/v1/whatsapp/inbound/logs", response=MessageLogResponse)
def whatsapp_inbound_logs(request, tenant_id: str | None = None, limit: int = 50):
    qs = Message.objects.order_by("-timestamp")
    if tenant_id:
        t = Tenant.objects.filter(tenant_key=tenant_id).first() or Tenant.objects.filter(name=tenant_id).first()
        if not t:
            return {"items": []}
        qs = qs.filter(tenant=t)
    qs = qs.select_related("tenant", "contact")[: max(1, min(limit, 200))]

    items = []
    for m in qs:
        items.append(
            MessageLogItem(
                tenant=(m.tenant.tenant_key or m.tenant.name or ""),
                contact_key=m.contact.contact_key,
                wamid=m.wamid,
                timestamp=m.timestamp.isoformat(),
                type=m.type,
                text_body=m.text_body,
                channel=m.channel,
            )
        )
    return {"items": items}


@router.get("/v1/whatsapp/inbound/verify")
def whatsapp_inbound_verify(
    request,
    tenant_id: str,
    contact_key: str | None = None,
    wamid: str | None = None,
    limit: int = 50,
):
    t = Tenant.objects.filter(tenant_key=tenant_id).first() or Tenant.objects.filter(name=tenant_id).first()
    if not t:
        return {"ok": False, "error": "tenant_not_found"}

    contacts_total = Contact.objects.filter(tenant=t).count()
    messages_total = Message.objects.filter(tenant=t).count()

    dedupe_for_wamid = None
    if wamid:
        dedupe_for_wamid = Message.objects.filter(tenant=t, wamid=wamid).count()

    contact_summary = None
    last_message_summary = None
    webhook_preview = None
    outbox_status = None

    if contact_key:
        c = Contact.objects.filter(tenant=t, contact_key=contact_key).first()
        if c:
            active_conv = (
                Conversation.objects.filter(tenant=t, contact=c, status=Conversation.STATUS_ACTIVE)
                .order_by("-opened_at")
                .first()
            )
            msgs_qs = Message.objects.filter(tenant=t, contact=c).order_by("-timestamp")
            msgs_count = msgs_qs.count()
            last_msg = msgs_qs.first()

            mem = MemoryRecord.objects.filter(tenant=t, contact=c).first()
            mem_last = mem.last_user_message_at.isoformat() if mem and mem.last_user_message_at else None

            contact_summary = {
                "exists": True,
                "wa_id": c.wa_id,
                "contact_key": c.contact_key,
                "profile_name": c.profile_name,
                "messages_count": msgs_count,
                "active_conversation_id": active_conv.id if active_conv else None,
                "active_conversation_opened_at": active_conv.opened_at.isoformat() if active_conv else None,
                "memory_last_user_message_at": mem_last,
            }

            if last_msg:
                attrib_exists = Attribution.objects.filter(
                    tenant=t, contact=c, message_wamid=last_msg.wamid
                ).exists()
                last_message_summary = {
                    "wamid": last_msg.wamid,
                    "timestamp": last_msg.timestamp.isoformat(),
                    "type": last_msg.type,
                    "text_body": last_msg.text_body,
                    "channel": last_msg.channel,
                    "has_attribution": attrib_exists,
                }
                md = {}
                try:
                    md = last_msg.payload_json.get("metadata") or {}
                except Exception:
                    md = {}
                webhook_preview = {
                    "tenant_id": t.tenant_key or tenant_id,
                    "contact_key": c.contact_key,
                    "wa_id": c.wa_id,
                    "phone_number_id": md.get("phone_number_id"),
                    "turn_wamid": last_msg.wamid,
                    "text": last_msg.text_body,
                    "timestamp_in": last_msg.timestamp.isoformat(),
                    "channel": last_msg.channel,
                }
                
                # Check Outbox
                outbox_evt = OutboxEvent.objects.filter(turn_wamid=last_msg.wamid).first()
                if outbox_evt:
                    outbox_status = {
                        "exists": True,
                        "status": outbox_evt.status,
                        "topic": outbox_evt.topic,
                        "created_at": outbox_evt.created_at.isoformat()
                    }
                else:
                    outbox_status = {"exists": False}
        else:
            contact_summary = {"exists": False}

    return {
        "ok": True,
        "tenant_id": t.tenant_key or tenant_id,
        "totals": {
            "contacts": contacts_total,
            "messages": messages_total,
        },
        "dedupe_for_wamid": dedupe_for_wamid,
        "contact": contact_summary,
        "last_message": last_message_summary,
        "webhook_preview": webhook_preview,
        "outbox_status": outbox_status
    }
