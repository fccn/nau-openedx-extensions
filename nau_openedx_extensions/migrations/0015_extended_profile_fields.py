"""
Adds the NUTS and CAE4 fields, and moves employment_situation to the new
controlled list.

The employment values used to be stored as English display strings. They are
now short stable codes, so existing rows are remapped in place. The old
"Public service contract" option was split into ten "Função Pública" entries
upstream, so there is no single value to map it to: it keeps its own code and
stays selectable, and users pick a specific entry the next time they edit.
"""

from django.db import migrations, models

from nau_openedx_extensions.custom_registration_form.choices import (
    CAE4_CHOICES,
    EMPLOYMENT_SITUATION_CHOICES,
    EMPLOYMENT_SITUATION_LEGACY_MAP,
    NUTS_CHOICES,
)


def map_employment_situation_forwards(apps, _schema_editor):
    """Rewrite the old display strings as the new codes."""
    model = apps.get_model("nau_openedx_extensions", "NauUserExtendedModel")
    for old_value, new_value in EMPLOYMENT_SITUATION_LEGACY_MAP.items():
        model.objects.filter(employment_situation=old_value).update(
            employment_situation=new_value
        )


def map_employment_situation_backwards(apps, _schema_editor):
    """Restore the old display strings, so the migration is reversible."""
    model = apps.get_model("nau_openedx_extensions", "NauUserExtendedModel")
    for old_value, new_value in EMPLOYMENT_SITUATION_LEGACY_MAP.items():
        model.objects.filter(employment_situation=new_value).update(
            employment_situation=old_value
        )


class Migration(migrations.Migration):
    """Add NUTS and CAE4, and move employment_situation to the new coded list."""

    dependencies = [
        ('nau_openedx_extensions', '0014_alter_ssopartnerintegration_user_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='nauuserextendedmodel',
            name='nuts',
            field=models.CharField(
                blank=True, choices=NUTS_CHOICES, max_length=64, null=True,
                verbose_name='NUTS II - NUTS III',
            ),
        ),
        migrations.AddField(
            model_name='nauuserextendedmodel',
            name='cae4',
            field=models.CharField(
                blank=True, choices=CAE4_CHOICES, max_length=64, null=True,
                verbose_name='CAE4',
            ),
        ),
        migrations.AlterField(
            model_name='nauuserextendedmodel',
            name='employment_situation',
            field=models.TextField(
                blank=True, choices=EMPLOYMENT_SITUATION_CHOICES, null=True,
                verbose_name='Employment situation',
            ),
        ),
        migrations.RunPython(
            map_employment_situation_forwards,
            map_employment_situation_backwards,
        ),
    ]
