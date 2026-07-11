from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_driver_docs_fitness_insurance_plate'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('latest_version', models.CharField(default='1.0.0', max_length=20)),
                ('min_required_version', models.CharField(default='1.0.0', max_length=20)),
                ('download_url', models.URLField(
                    default='https://github.com/lumbilumbi200-byte/twambo/releases/latest'
                )),
                ('release_notes', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'App Version'},
        ),
    ]
