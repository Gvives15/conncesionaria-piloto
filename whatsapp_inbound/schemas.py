from ninja import Schema
from typing import Any, Dict, Optional


class WANormalizedContact(Schema):
    wa_id: str
    contact_key: str
    profile_name: Optional[str] = None


class WANormalizedMessageText(Schema):
    body: Optional[str] = None


class WANormalizedMessage(Schema):
    wamid: str
    timestamp: str  # ISO
    type: str
    text: Optional[WANormalizedMessageText] = None
    interactive: Optional[Dict[str, Any]] = None
    media: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any]


class WANormalizedMetadata(Schema):
    provider: str = "cloud_api"
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    display_phone_number: Optional[str] = None


class WANormalizedInbound(Schema):
    tenant_id: str
    trace_id: str
    received_at: str
    channel: str = "whatsapp"

    metadata: WANormalizedMetadata
    contact: WANormalizedContact
    message: WANormalizedMessage

    referral: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any]
