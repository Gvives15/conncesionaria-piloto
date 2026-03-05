
import pytest
from whatsapp_inbound.models import MemoryRecord, Tenant, Contact

@pytest.mark.django_db
def test_integrity_error_prevention():
    """
    Verifies that saving None to a JSONField that expects a list is prevented by the model's save method.
    """
    tenant = Tenant.objects.create(tenant_key="repro_tenant", name="Repro Tenant")
    contact = Contact.objects.create(tenant=tenant, contact_key="wa:repro", wa_id="repro")
    
    mem = MemoryRecord.objects.create(tenant=tenant, contact=contact)
    
    # This should NO LONGER fail because the model is hardened
    try:
        mem.active_secondary_events = None
        mem.save()
        print("\n[SUCCESS] Saved None successfully (handled by model.save())")
    except Exception as e:
        pytest.fail(f"Should have handled None but raised: {e}")
        
    mem.refresh_from_db()
    assert mem.active_secondary_events == [], "Should have defaulted to []"

    # Also test via api logic simulation (which now has hotfix)
    val_from_llm = None
    fallback_val = None
    
    # API simulation with hotfix
    mem.active_secondary_events = (val_from_llm or fallback_val) or []
    mem.save()
    
    mem.refresh_from_db()
    assert mem.active_secondary_events == [], "Should have defaulted to [] via API logic"

    # Test direct None assignment again to verify model hardening
    mem.active_secondary_events = None
    mem.save()
    mem.refresh_from_db()
    assert mem.active_secondary_events == [], "Model hardening should convert None to []"
