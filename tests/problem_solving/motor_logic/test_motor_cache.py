import pytest
from django.core.cache import cache
from whatsapp_inbound.models import Tenant, TenantEvent
from motor_response.api import _load_tenant_events

@pytest.mark.django_db
def test_tenant_events_cache():
    # Setup
    tenant = Tenant.objects.create(tenant_key="cache_test", name="Cache Test")
    event = TenantEvent.objects.create(
        tenant=tenant,
        name="TEST_EVENT",
        max_points=10,
        triggers=["test"],
        is_active=True
    )

    # First load - should hit DB and populate cache
    events1 = _load_tenant_events(tenant)
    assert len(events1) == 1
    assert events1[0]["name"] == "TEST_EVENT"

    # Modify DB directly
    event.name = "CHANGED_EVENT"
    event.save()

    # Second load - should hit cache and return OLD name
    events2 = _load_tenant_events(tenant)
    assert len(events2) == 1
    assert events2[0]["name"] == "TEST_EVENT"  # Should be stale

    # Clear cache
    cache.clear()

    # Third load - should hit DB and return NEW name
    events3 = _load_tenant_events(tenant)
    assert len(events3) == 1
    assert events3[0]["name"] == "CHANGED_EVENT"
