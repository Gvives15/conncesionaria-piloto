from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("whatsapp_inbound", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenant",
            name="name",
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="tenant_key",
            field=models.CharField(max_length=120, unique=True, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="business_name",
            field=models.CharField(max_length=200, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="domain",
            field=models.CharField(max_length=80, default="generic"),
        ),
        migrations.AddField(
            model_name="tenant",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
