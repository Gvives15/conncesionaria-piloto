import pytest
import os
import uuid
import logging
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from whatsapp_inbound.models import (
    Tenant, Contact, Template, TenantEvent, MemoryRecord
)

# Skip if env vars are missing
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if "llm_live" in item.keywords:
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY missing")
        if not os.getenv("LLM_CLASSIFIER_PROMPT_ID"):
            pytest.skip("LLM_CLASSIFIER_PROMPT_ID missing")

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield

@pytest.fixture
def api_client(client):
    return client

@pytest.fixture
def tenant(db):
    t, _ = Tenant.objects.get_or_create(
        tenant_key="distribuidora_001",
        defaults={
            "business_name": "Distribuidora Test",
            "domain": "distribuidora",
            "is_active": True
        }
    )
    # Ensure domain is correct if it already existed
    if t.domain != "distribuidora":
        t.domain = "distribuidora"
        t.save()
    return t

@pytest.fixture
def templates(db, tenant):
    # Templates activos: REOPEN_24H, SAFE_BOUNDARY, HANDOFF_GENERIC
    names = ["REOPEN_24H", "SAFE_BOUNDARY", "HANDOFF_GENERIC"]
    objs = []
    for name in names:
        tpl, _ = Template.objects.get_or_create(
            tenant=tenant,
            name=name,
            defaults={
                "active": True,
                "language": "es_AR",
                "components_json": [{"type": "body", "text": f"Template {name}"}]
            }
        )
        objs.append(tpl)
    return objs

@pytest.fixture
def catalog_distribuidora_mvp(db, tenant):
    # Crear eventos mínimos Distribuidora MVP (16 eventos)
    events_data = [
        ("SALUDO_INICIO", ["hola", "buen dia", "buenas", "que tal"]),
        ("CONSULTA_CATALOGO", ["catalogo", "lista", "precios", "productos"]),
        ("CONSULTA_PRECIO", ["precio", "cuanto sale", "a cuanto", "valor"]),
        ("CONSULTA_STOCK", ["stock", "tenes", "hay", "queda"]),
        ("ARMAR_PEDIDO", ["pedido", "quiero", "encargue", "necesito", "mandame"]),
        ("MODIFICAR_PEDIDO", ["agregar", "sacar", "cambiar", "modificar", "sumar", "quitar"]),
        ("CONFIRMAR_PEDIDO", ["confirmo", "cerrar", "listo", "dale", "envialo"]),
        ("CONSULTA_ENVIO", ["envio", "entrega", "cuando llega", "llevan"]),
        ("CONSULTA_ESTADO_PEDIDO", ["estado", "salio", "donde esta", "mi pedido"]),
        ("CONSULTA_PAGO", ["pago", "alias", "cbu", "qr", "transferencia", "efectivo"]),
        ("CUENTA_CORRIENTE_SALDO", ["saldo", "debo", "cuenta", "fio"]),
        ("FACTURACION_DATOS", ["factura", "cuit", "fiscal", "comprobante"]),
        ("RECLAMO", ["reclamo", "roto", "falta", "mal", "vino mal", "me falto", "incompleto", "problema", "falto en el pedido"]),
        ("DEVOLUCION_CAMBIO", ["devolver", "cambio", "vencido", "fechas"]),
        ("OPT_OUT", ["baja", "no quiero", "parar", "no me escribas"]),
        ("HABLAR_CON_HUMANO", ["humano", "asesor", "persona", "alguien"]),
    ]
    
    objs = []
    for name, keywords in events_data:
        triggers = [{"type": "kw", "value": k, "points": 5} for k in keywords]
        evt, _ = TenantEvent.objects.get_or_create(
            tenant=tenant,
            name=name,
            defaults={
                "triggers": triggers,
                "is_active": True,
                "max_points": 20,
                "template_key": ""
            }
        )
        # Ensure it's active and points are correct if existed
        if not evt.is_active or evt.max_points != 20:
            evt.is_active = True
            evt.max_points = 20
            evt.save()
            
        objs.append(evt)
    return objs

@pytest.fixture
def contact(db, tenant):
    c, _ = Contact.objects.get_or_create(
        tenant=tenant,
        contact_key="wa:5491122334455",
        defaults={
            "wa_id": "5491122334455",
            "phone_e164": "+5491122334455",
            "profile_name": "Test User"
        }
    )
    return c

@pytest.fixture
def memory_open(db, tenant, contact):
    # Window open: last message 1h ago
    last_msg = timezone.now() - timedelta(hours=1)
    mem, _ = MemoryRecord.objects.get_or_create(
        tenant=tenant,
        contact=contact,
        defaults={
            "last_user_message_at": last_msg,
            "summary": "Usuario nuevo",
            "facts_json": []
        }
    )
    mem.last_user_message_at = last_msg
    mem.save()
    return mem

@pytest.fixture
def memory_closed(db, tenant, contact):
    # Window closed: last message 30h ago
    last_msg = timezone.now() - timedelta(hours=30)
    
    mem, _ = MemoryRecord.objects.get_or_create(
        tenant=tenant,
        contact=contact
    )
    mem.last_user_message_at = last_msg
    mem.save()
    return mem

@pytest.fixture
def base_payload(tenant, contact):
    def _builder(text="hola", turn_wamid=None):
        return {
            "tenant_id": tenant.tenant_key,
            "contact_key": contact.contact_key,
            "wa_id": contact.wa_id,
            "phone_number_id": "123456",
            "turn_wamid": turn_wamid or f"wamid.{uuid.uuid4()}",
            "text": text,
            "channel": "whatsapp",
            "timestamp_in": timezone.now().isoformat()
        }
    return _builder
