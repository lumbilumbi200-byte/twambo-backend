from django.db import migrations, models
from decimal import Decimal


def set_minimum_float(apps, schema_editor):
    DriverWallet = apps.get_model('payments', 'DriverWallet')
    DriverWallet.objects.all().update(minimum_float=Decimal('1'))


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_add_topup_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='driverwallet',
            name='minimum_float',
            field=models.DecimalField(decimal_places=2, default=Decimal('1'), max_digits=8),
        ),
        migrations.RunPython(set_minimum_float, migrations.RunPython.noop),
    ]
