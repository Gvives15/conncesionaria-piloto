import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from whatsapp_inbound.models import OutboxEvent

wamid = os.getenv("WAMID")

if wamid:
    evts = OutboxEvent.objects.filter(turn_wamid=wamid).order_by("-created_at")
else:
    evts = OutboxEvent.objects.order_by("-created_at")[:10]

for e in evts:
    print(f"id={e.id} status={e.status} topic={e.topic} turn_wamid={e.turn_wamid} attempts={e.attempts} next_retry_at={e.next_retry_at}")
