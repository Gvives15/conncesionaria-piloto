# management/commands/seed_events.py
from django.core.management.base import BaseCommand
from django.db import transaction

from whatsapp_inbound.models import Tenant, TenantEvent  # <-- CAMBIAR si tu app se llama distinto


DEFAULT_EVENTS_DISTRI_CIG = [
    {
        "name": "SALUDO",
        "max_points": 10,
        "triggers": [
            {"type": "kw", "value": "hola", "points": 3},
            {"type": "kw", "value": "buenos", "points": 2},
            {"type": "kw", "value": "buenas", "points": 2},
            {"type": "kw", "value": "que tal", "points": 2},
            {"type": "kw", "value": "qué tal", "points": 2},
        ],
        "freeform_reply": "¡Hola! ¿En qué te ayudo? (precio, pedido, stock, envío, pago, cuenta corriente o reclamo)",
        "template_key": "",  # opcional
    },
    {
        "name": "PEDIDO",
        "max_points": 15,
        "triggers": [
            {"type": "kw", "value": "quiero", "points": 3},
            {"type": "kw", "value": "necesito", "points": 3},
            {"type": "kw", "value": "mandame", "points": 4},
            {"type": "kw", "value": "pedido", "points": 5},
            {"type": "kw", "value": "pasame", "points": 3},
        ],
        "freeform_reply": "Dale. Pasame marcas y cantidades (box/suelto) y tu zona para coordinar entrega.",
        "template_key": "",  # opcional
    },
    {
        "name": "CONSULTA_PRECIO_PROMO",
        "max_points": 18,
        "triggers": [
            {"type": "kw", "value": "precio", "points": 5},
            {"type": "kw", "value": "lista", "points": 4},
            {"type": "kw", "value": "promo", "points": 4},
            {"type": "kw", "value": "oferta", "points": 4},
            {"type": "kw", "value": "cuanto", "points": 3},
            {"type": "kw", "value": "vale", "points": 3},
            {"type": "kw", "value": "cuesta", "points": 3},
        ],
        "freeform_reply": "Decime la marca y presentación (box/suelto) y te paso precio y promos si hay.",
        "template_key": "",  # opcional
    },
    {
        "name": "DISPONIBILIDAD_STOCK",
        "max_points": 15,
        "triggers": [
            {"type": "kw", "value": "tenes", "points": 4},
            {"type": "kw", "value": "tenés", "points": 4},
            {"type": "kw", "value": "hay", "points": 3},
            {"type": "kw", "value": "stock", "points": 5},
            {"type": "kw", "value": "disponible", "points": 5},
            {"type": "kw", "value": "queda", "points": 2},
        ],
        "freeform_reply": "Para ver stock: decime marca y cantidad (box/suelto) y tu zona.",
        "template_key": "",  # opcional
    },
    {
        "name": "ENVIO_ENTREGA",
        "max_points": 16,
        "triggers": [
            {"type": "kw", "value": "envio", "points": 5},
            {"type": "kw", "value": "envío", "points": 5},
            {"type": "kw", "value": "reparto", "points": 5},
            {"type": "kw", "value": "entrega", "points": 4},
            {"type": "kw", "value": "llegan", "points": 4},
            {"type": "kw", "value": "cuando", "points": 2},
        ],
        "freeform_reply": "¿En qué zona estás y para cuándo lo necesitás? Así coordinamos el envío.",
        "template_key": "",  # opcional
    },
    {
        "name": "MEDIOS_DE_PAGO",
        "max_points": 15,
        "triggers": [
            {"type": "kw", "value": "transferencia", "points": 5},
            {"type": "kw", "value": "efectivo", "points": 4},
            {"type": "kw", "value": "tarjeta", "points": 4},
            {"type": "kw", "value": "mercado pago", "points": 3},
            {"type": "kw", "value": "mp", "points": 3},
            {"type": "kw", "value": "factura", "points": 3},
        ],
        "freeform_reply": "Podés pagar en efectivo o transferencia. ¿Cuál preferís? Si querés factura, pasame tus datos.",
        "template_key": "",  # opcional
    },
    {
        "name": "CUENTA_CORRIENTE_CREDITO",
        "max_points": 18,
        "triggers": [
            {"type": "kw", "value": "cuenta corriente", "points": 6},
            {"type": "kw", "value": "fiado", "points": 6},
            {"type": "kw", "value": "saldo", "points": 4},
            {"type": "kw", "value": "limite", "points": 4},
            {"type": "kw", "value": "límite", "points": 4},
            {"type": "kw", "value": "credito", "points": 4},
            {"type": "kw", "value": "crédito", "points": 4},
        ],
        "freeform_reply": "Para cuenta corriente, pasame nombre del kiosco y CUIT o teléfono y lo reviso.",
        "template_key": "CUENTA_HANDOFF",  # OBLIGATORIO para handoff (tu template aprobado)
    },
    {
        "name": "RECLAMO",
        "max_points": 20,
        "triggers": [
            {"type": "kw", "value": "reclamo", "points": 6},
            {"type": "kw", "value": "falto", "points": 5},
            {"type": "kw", "value": "faltó", "points": 5},
            {"type": "kw", "value": "no llego", "points": 5},
            {"type": "kw", "value": "no llegó", "points": 5},
            {"type": "kw", "value": "vino mal", "points": 5},
            {"type": "kw", "value": "error", "points": 4},
            {"type": "kw", "value": "devolucion", "points": 4},
            {"type": "kw", "value": "devolución", "points": 4},
        ],
        "freeform_reply": "Entiendo. Ya lo derivo para que lo resuelvan. ¿Qué faltó o qué vino mal?",
        "template_key": "RECLAMO_HANDOFF",  # OBLIGATORIO para handoff (tu template aprobado)
    },
]


class Command(BaseCommand):
    help = "Crea/actualiza eventos base por tenant (distri cigarrillos)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="tenant_key (ej: distri_cig_001)")
        parser.add_argument("--name", default=None, help="business_name si el tenant no existe (opcional)")

    @transaction.atomic
    def handle(self, *args, **opts):
        tenant_key = opts["tenant"]
        business_name = opts["name"] or tenant_key

        tenant, _ = Tenant.objects.get_or_create(
            tenant_key=tenant_key,
            defaults={"business_name": business_name, "name": business_name},
        )

        created = 0
        updated = 0

        for ev in DEFAULT_EVENTS_DISTRI_CIG:
            obj, was_created = TenantEvent.objects.update_or_create(
                tenant=tenant,
                name=ev["name"],
                defaults={
                    "max_points": ev["max_points"],
                    "triggers": ev["triggers"],
                    "freeform_reply": ev["freeform_reply"],
                    "template_key": ev["template_key"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"OK tenant={tenant.tenant_key} | created={created} updated={updated}"
        ))
