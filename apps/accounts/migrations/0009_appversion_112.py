from django.db import migrations


def bump_to_112(apps, schema_editor):
    AppVersion = apps.get_model('accounts', 'AppVersion')
    AppVersion.objects.update_or_create(
        pk=1,
        defaults={
            'latest_version': '1.1.2',
            'min_required_version': '1.0.0',
            'release_notes': (
                'Fare fix: hike trip prices now use agreed market rates (e.g. Kitwe→Chingola K45) '
                'instead of the distance formula. '
                'Drop-off picker: riders on hike trips can now select which intermediate city '
                'they are alighting at and see their segment fare before booking.'
            ),
        },
    )


class Migration(migrations.Migration):
    dependencies = [('accounts', '0008_appversion_111')]
    operations = [migrations.RunPython(bump_to_112, migrations.RunPython.noop)]
