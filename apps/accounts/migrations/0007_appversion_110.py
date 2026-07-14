from django.db import migrations


def bump_to_110(apps, schema_editor):
    AppVersion = apps.get_model('accounts', 'AppVersion')
    AppVersion.objects.update_or_create(
        pk=1,
        defaults={
            'latest_version': '1.1.0',
            'min_required_version': '1.0.0',
            'release_notes': (
                'Multi-city support across Copperbelt and Northwestern. '
                'Long distance trips with per-seat flat fares. '
                'Improved dynamic pricing and highway pickup points.'
            ),
        },
    )


class Migration(migrations.Migration):
    dependencies = [('accounts', '0006_appversion')]
    operations = [migrations.RunPython(bump_to_110, migrations.RunPython.noop)]
