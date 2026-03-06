import pytest
from django.core.cache import cache
from django.utils import timezone
from whatsapp_inbound.models import Tenant, Contact, MemoryRecord, TenantEvent, Template

@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    cache.clear()
    yield
    cache.clear()

@pytest.fixture
def tenant(db):
    return Tenant.objects.create(
        tenant_key="test_tenant",
        business_name="Test Business",
        domain="test_domain"
    )

@pytest.fixture
def contact(db, tenant):
    return Contact.objects.create(
        tenant=tenant,
        contact_key="wa:123456789",
        wa_id="123456789",
        phone_e164="+123456789",
        profile_name="Test User"
    )

@pytest.fixture
def memory_record(db, tenant, contact):
    return MemoryRecord.objects.create(
        tenant=tenant,
        contact=contact,
        summary="User is testing.",
        last_user_message_at=timezone.now()
    )

@pytest.fixture
def tenant_event(db, tenant):
    return TenantEvent.objects.create(
        tenant=tenant,
        name="TEST_EVENT",
        max_points=10,
        triggers=[{"type": "kw", "value": "test", "points": 10}],
        freeform_reply="This is a test reply.",
        is_active=True
    )

@pytest.fixture
def template(db, tenant):
    return Template.objects.create(
        tenant=tenant,
        name="test_template",
        category="UTILITY",
        language="en_US",
        components_json=[],
        active=True
    )
