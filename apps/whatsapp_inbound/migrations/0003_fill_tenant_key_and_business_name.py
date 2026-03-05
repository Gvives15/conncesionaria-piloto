from django.db import migrations


def forwards(apps, schema_editor):
    Tenant = apps.get_model("whatsapp_inbound", "Tenant")
    for t in Tenant.objects.all():
        bn = t.business_name or (t.name or "Sin nombre")
        key = t.tenant_key or f"tenant_{str(t.id)[:8]}"
        if bn != t.business_name or key != t.tenant_key:
            t.business_name = bn
            t.tenant_key = key
            t.save(update_fields=["business_name", "tenant_key"])


def backwards(apps, schema_editor):
    # No revert needed; keep populated values
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("whatsapp_inbound", "0002_alter_tenant_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
