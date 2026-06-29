from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_role'),
    ]

    operations = [
        # Make existing doc fields nullable so existing rows don't break
        migrations.AlterField(
            model_name='driverprofile',
            name='national_id',
            field=models.ImageField(blank=True, null=True, upload_to='documents/'),
        ),
        migrations.AlterField(
            model_name='driverprofile',
            name='drivers_license',
            field=models.ImageField(blank=True, null=True, upload_to='documents/'),
        ),
        migrations.AlterField(
            model_name='driverprofile',
            name='vehicle_registration',
            field=models.ImageField(blank=True, null=True, upload_to='documents/'),
        ),
        migrations.AddField(
            model_name='driverprofile',
            name='fitness_certificate',
            field=models.ImageField(blank=True, null=True, upload_to='documents/'),
        ),
        migrations.AddField(
            model_name='driverprofile',
            name='insurance_certificate',
            field=models.ImageField(blank=True, null=True, upload_to='documents/'),
        ),
        migrations.AddField(
            model_name='driverprofile',
            name='plate_photo',
            field=models.ImageField(blank=True, null=True, upload_to='documents/'),
        ),
    ]
