import asyncio
import httpx
import time
import uuid
from datetime import datetime, timezone

URL_INBOUND = "http://localhost:8000/v1/whatsapp/inbound"
URL_VERIFY = "http://localhost:8000/v1/whatsapp/inbound/verify"
TENANT_ID = "distri_cig_001"
PHONE_NUMBER_ID = "100987654321"
DISPLAY_NUMBER = "5491112345678"

def make_payload(i, with_referral=False):
    phone = f"54911000000{i:02d}"
    contact_key = f"wa:{phone}"
    wamid = f"wamid.HBgL.loadtest.{uuid.uuid4()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_ts = str(int(time.time()))
    text = f"Hola, quiero saber precios de cigarrillos - Msg {i}"
    referral = None
    if with_referral:
        referral = {
            "source_type": "ad_click",
            "ctwa_clid": f"clid{i}",
            "source_id": f"ad_{i}",
            "headline": "Anuncio Test",
            "body": "Campaña CTA WhatsApp"
        }
    return [{
        "tenant_id": TENANT_ID,
        "trace_id": f"exec_loadtest_{i}",
        "received_at": now_iso,
        "channel": "whatsapp",
        "metadata": {
            "provider": "cloud_api",
            "waba_id": "100123456789",
            "phone_number_id": PHONE_NUMBER_ID,
            "display_phone_number": DISPLAY_NUMBER
        },
        "contact": {
            "wa_id": phone,
            "contact_key": contact_key,
            "profile_name": f"Usuario Test {i}"
        },
        "message": {
            "wamid": wamid,
            "timestamp": now_iso,
            "type": "text",
            "text": {"body": text},
            "raw": {
                "from": phone,
                "id": wamid,
                "timestamp": raw_ts,
                "text": {"body": text},
                "type": "text"
            }
        },
        "referral": referral,
        "raw": {
            "messaging_product": "whatsapp",
            "metadata": {
                "display_phone_number": DISPLAY_NUMBER,
                "phone_number_id": PHONE_NUMBER_ID
            },
            "contacts": [{
                "profile": {"name": f"Usuario Test {i}"},
                "wa_id": phone
            }],
            "messages": [{
                "from": phone,
                "id": wamid,
                "timestamp": raw_ts,
                "text": {"body": text},
                "type": "text"
            }]
        }
    }]

async def post_inbound(client, payload):
    r = await client.post(URL_INBOUND, json=payload, timeout=10.0)
    return r.status_code, r.json()

async def get_verify(client, tenant_id, contact_key, wamid=None):
    params = {"tenant_id": tenant_id, "contact_key": contact_key}
    if wamid:
        params["wamid"] = wamid
    r = await client.get(URL_VERIFY, params=params, timeout=10.0)
    return r.status_code, r.json()

async def run():
    async with httpx.AsyncClient() as client:
        p1 = make_payload(1, with_referral=False)
        status1, body1 = await post_inbound(client, p1)
        assert status1 == 200 and body1.get("ok") and not body1.get("deduped")
        wamid1 = p1[0]["message"]["wamid"]
        contact_key1 = p1[0]["contact"]["contact_key"]
        statusv1, ver1 = await get_verify(client, TENANT_ID, contact_key1, wamid1)
        assert statusv1 == 200
        assert ver1["contact"]["exists"] is True
        assert ver1["contact"]["messages_count"] >= 1
        assert ver1["last_message"]["wamid"] == wamid1
        assert ver1["last_message"]["type"] == "text"
        assert ver1["last_message"]["text_body"].startswith("Hola, quiero saber precios")
        assert ver1["last_message"]["channel"] == "whatsapp"
        assert ver1["last_message"]["has_attribution"] is False
        assert ver1["contact"]["active_conversation_id"] is not None
        assert ver1["contact"]["memory_last_user_message_at"] is not None
        wp1 = ver1["webhook_preview"]
        assert wp1["tenant_id"] == TENANT_ID
        assert wp1["contact_key"] == contact_key1
        assert wp1["wa_id"] == p1[0]["contact"]["wa_id"]
        assert wp1["phone_number_id"] == PHONE_NUMBER_ID
        assert wp1["turn_wamid"] == wamid1
        assert wp1["text"] == p1[0]["message"]["text"]["body"]
        assert wp1["channel"] == "whatsapp"
        status1b, body1b = await post_inbound(client, p1)
        assert status1b == 200 and body1b.get("ok") and body1b.get("deduped")
        statusv1b, ver1b = await get_verify(client, TENANT_ID, contact_key1, wamid1)
        assert statusv1b == 200
        assert ver1b["dedupe_for_wamid"] == 1
        p2 = make_payload(2, with_referral=True)
        status2, body2 = await post_inbound(client, p2)
        assert status2 == 200 and body2.get("ok") and not body2.get("deduped")
        wamid2 = p2[0]["message"]["wamid"]
        contact_key2 = p2[0]["contact"]["contact_key"]
        statusv2, ver2 = await get_verify(client, TENANT_ID, contact_key2, wamid2)
        assert statusv2 == 200
        assert ver2["contact"]["exists"] is True
        assert ver2["last_message"]["wamid"] == wamid2
        assert ver2["last_message"]["has_attribution"] is True
        print("OK: Dedupe, Upsert Contact, Conversación Activa, Insert Message, Attribution, MemoryRecord, Webhook Preview")

if __name__ == "__main__":
    asyncio.run(run())
