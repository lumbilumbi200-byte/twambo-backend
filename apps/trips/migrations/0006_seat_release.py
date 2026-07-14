from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0005_trip_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='SeatRelease',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('city_name', models.CharField(max_length=100)),
                ('city_id', models.CharField(db_index=True, max_length=50)),
                ('seats', models.PositiveSmallIntegerField(default=1)),
                ('status', models.CharField(
                    choices=[('active', 'Active'), ('filled', 'Filled'), ('cancelled', 'Cancelled')],
                    default='active',
                    max_length=15,
                )),
                ('announced_at', models.DateTimeField(auto_now_add=True)),
                ('trip', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='seat_releases',
                    to='trips.trip',
                )),
            ],
            options={'db_table': 'seat_releases', 'ordering': ['-announced_at']},
        ),
    ]
