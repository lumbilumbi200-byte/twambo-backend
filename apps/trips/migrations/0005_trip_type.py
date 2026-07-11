from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0004_add_mode_to_recurring_trip'),
    ]

    operations = [
        migrations.AddField(
            model_name='trip',
            name='trip_type',
            field=models.CharField(
                choices=[('city', 'City'), ('hike', 'Hike')],
                default='city',
                db_index=True,
                max_length=10,
            ),
        ),
    ]
