import os
import time
import uuid
import logging
from datetime import timedelta

import httpx
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from whatsapp_inbound.models import OutboxEvent

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Consume OutboxEvent pending rows and delivers them to n8n webhook."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process one batch and exit")

    def handle(self, *args, **opts):
        worker_id = os.getenv("WORKER_ID", str(uuid.uuid4())[:8])
        # URL por defecto basada en tu docker-compose
        url = os.getenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/whatsapp-inbound-event")

        poll_sleep = float(os.getenv("OUTBOX_POLL_SLEEP", "1.0"))
        batch_size = int(os.getenv("OUTBOX_BATCH_SIZE", "25"))
        http_timeout = float(os.getenv("OUTBOX_HTTP_TIMEOUT", "10"))
        max_attempts = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "8"))

        # Reaper: rescatar "processing" colgados (ej. si el worker muere a mitad de proceso)
        reaper_every = int(os.getenv("OUTBOX_REAPER_EVERY_SEC", "60"))
        processing_ttl = int(os.getenv("OUTBOX_PROCESSING_TTL_SEC", "300"))  # 5 min
        last_reaper = 0

        self.stdout.write(f"Worker {worker_id} started. Target: {url}")

        with httpx.Client(timeout=http_timeout) as client:
            while True:
                now = time.time()
                # 1. Reaper de procesos zombies
                if now - last_reaper >= reaper_every:
                    self._reap_stuck(processing_ttl=processing_ttl)
                    last_reaper = now

                # 2. Buscar trabajo
                events = self._claim_batch(batch_size=batch_size, worker_id=worker_id)
                
                if not events:
                    if opts.get("once"):
                        self.stdout.write("No events pending. Exiting (--once).")
                        return
                    time.sleep(poll_sleep)
                    continue

                # 3. Procesar lote
                self.stdout.write(f"Processing batch of {len(events)} events...")
                for evt in events:
                    ok, err, status_code = self._deliver(client, url, evt)
                    self._finalize(evt, ok, err, status_code, max_attempts)

                if opts.get("once"):
                    return

    def _claim_batch(self, batch_size: int, worker_id: str):
        """
        Claim a batch safely. Uses row-level locks (SKIP LOCKED) to avoid duplicates across workers.
        """
        with transaction.atomic():
            # Seleccionamos eventos pendientes o reintentos listos
            now = timezone.now()
            qs = (
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(status=OutboxEvent.STATUS_PENDING)
                .filter(next_retry_at__lte=now)  # Solo procesar si ya pasó el tiempo de espera
                .order_by("created_at")
            )
            events = list(qs[:batch_size])
            
            if not events:
                return []

            # Marcamos como 'processing'
            for e in events:
                e.status = OutboxEvent.STATUS_PROCESSING
                e.attempts = (e.attempts or 0) + 1
                e.locked_at = now
                e.locked_by = worker_id
                e.updated_at = now
                # Optimizamos el save para solo escribir campos necesarios
                e.save(update_fields=["status", "attempts", "locked_at", "locked_by", "updated_at"])

            return events

    def _deliver(self, client: httpx.Client, url: str, evt: OutboxEvent):
        payload = evt.payload_json

        headers = {
            "X-Outbox-Event-Id": str(evt.id),
            "Content-Type": "application/json",
        }
        if evt.dedupe_key:
            headers["X-Dedupe-Key"] = evt.dedupe_key
        if evt.topic:
            headers["X-Topic"] = evt.topic

        try:
            r = client.post(url, json=payload, headers=headers)
            
            # Éxito (2xx)
            if 200 <= r.status_code < 300:
                return True, None, r.status_code

            # Errores transitorios (429, 5xx) -> Reintentar
            if r.status_code == 429 or 500 <= r.status_code < 600:
                return False, f"HTTP {r.status_code}: {r.text[:200]}", r.status_code

            # Errores permanentes (4xx) -> Fallar
            return False, f"HTTP {r.status_code}: {r.text[:200]}", r.status_code

        except Exception as e:
            return False, str(e), None

    def _finalize(self, evt: OutboxEvent, ok: bool, err: str | None, status_code: int | None, max_attempts: int):
        now = timezone.now()

        if ok:
            evt.status = OutboxEvent.STATUS_SENT
            # Nota: Si agregas 'delivered_at' al modelo, descomenta esto:
            # evt.delivered_at = now
            # evt.last_error = None
            evt.updated_at = now
            evt.save(update_fields=["status", "updated_at"])
            return

        # Fallo -> Decidir si reintentar o marcar como failed
        permanent_4xx = (status_code is not None and 400 <= status_code < 500 and status_code != 429)

        if permanent_4xx or evt.attempts >= max_attempts:
            evt.status = OutboxEvent.STATUS_FAILED
            logger.error(f"Event {evt.id} FAILED permanently. Error: {err}")
        else:
            evt.status = OutboxEvent.STATUS_PENDING
            # Backoff exponencial: 2s, 4s, 8s... hasta 60s
            delay = min(60, 2 ** min(evt.attempts, 6))
            evt.next_retry_at = now + timedelta(seconds=delay)
            logger.warning(f"Event {evt.id} retry scheduled in {delay}s. Error: {err}")

        # Nota: Si agregas 'last_error' al modelo, descomenta esto:
        # evt.last_error = (err or "")[:2000]
        
        evt.updated_at = now
        # Guardamos campos relevantes. next_retry_at solo si cambió
        fields_to_update = ["status", "updated_at"]
        if evt.status == OutboxEvent.STATUS_PENDING:
            fields_to_update.append("next_retry_at")
            
        evt.save(update_fields=fields_to_update)

    def _reap_stuck(self, processing_ttl: int):
        """
        Reset stuck processing events back to pending.
        """
        cutoff = timezone.now() - timedelta(seconds=processing_ttl)
        qs = OutboxEvent.objects.filter(status=OutboxEvent.STATUS_PROCESSING, updated_at__lt=cutoff)
        
        count = 0
        # Procesamos en lotes pequeños para no bloquear
        for evt in qs[:100]:
            evt.status = OutboxEvent.STATUS_PENDING
            evt.updated_at = timezone.now()
            evt.save(update_fields=["status", "updated_at"])
            count += 1
            
        if count > 0:
            self.stdout.write(f"Reaper: Reset {count} stuck events to PENDING.")
