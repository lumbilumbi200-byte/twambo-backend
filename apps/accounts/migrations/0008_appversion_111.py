from django.db import migrations


def bump_to_111(apps, schema_editor):
    AppVersion = apps.get_model('accounts', 'AppVersion')
    AppVersion.objects.update_or_create(
        pk=1,
        defaults={
            'latest_version': '1.1.1',
            'min_required_version': '1.0.0',
            'release_notes': (
                'Seat release broadcast: drivers can pre-announce a drop-off at an intermediate city '
                'so waiting riders get notified and can request the freed seat. '
                'Hike trip visibility fix: riders now see all trips passing through their city, '
                'not just trips starting there. '
                'Boarding pickup now defaults to your city on pass-through trips. '
                'Updated GPS-verified highway waypoints and corrected route fares across '
                'the Copperbelt and Northwestern corridor. '
                '12% roadside discount for highway waypoint boardings. '
                'Reliability: seat booking race conditions fixed, WebSocket auto-reconnects on network change.'
            ),
        },
    )


class Migration(migrations.Migration):
    dependencies = [('accounts', '0007_appversion_110')]
    operations = [migrations.RunPython(bump_to_111, migrations.RunPython.noop)]
