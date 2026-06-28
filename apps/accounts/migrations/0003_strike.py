from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_driverprofile_budget_dismissed_month_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Strike',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(
                    choices=[
                        ('low_rating', 'Low Rating (auto)'),
                        ('no_show', 'No Show / Late Cancellation'),
                        ('misconduct', 'Misconduct / Complaint'),
                        ('fraud', 'Fraud / Payment Issue'),
                        ('other', 'Other'),
                    ],
                    max_length=20,
                )),
                ('notes', models.TextField(blank=True)),
                ('auto_generated', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('given_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='strikes_given',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='strikes',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'strikes',
                'ordering': ['-created_at'],
            },
        ),
    ]
