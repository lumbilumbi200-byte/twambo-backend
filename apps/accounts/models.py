from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings as django_settings
from django.db import models
from decimal import Decimal


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Phone number is required')
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_DRIVER = 'driver'
    ROLE_RIDER = 'rider'
    ROLE_CHOICES = [(ROLE_DRIVER, 'Driver'), (ROLE_RIDER, 'Rider')]

    phone_number = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_RIDER, blank=True)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)
    fcm_token = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    strike_count = models.PositiveIntegerField(default=0)
    is_banned = models.BooleanField(default=False)
    ban_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f'{self.full_name} ({self.phone_number})'

    @property
    def is_driver(self):
        return self.role == self.ROLE_DRIVER

    @property
    def is_rider(self):
        return self.role == self.ROLE_RIDER

    @property
    def fare_surcharge_pct(self):
        """Fare surcharge for riders with multiple strikes: 3→10%, 4→20%, 5+→30%."""
        if self.strike_count >= 5:
            return 30
        elif self.strike_count >= 4:
            return 20
        elif self.strike_count >= 3:
            return 10
        return 0

    def give_strike(self, reason, notes='', given_by=None, auto_generated=False):
        Strike.objects.create(
            user=self,
            reason=reason,
            notes=notes,
            given_by=given_by,
            auto_generated=auto_generated,
        )
        self.strike_count = self.strikes.count()
        self.save(update_fields=['strike_count', 'updated_at'])

    def remove_strike(self, strike_id):
        Strike.objects.filter(pk=strike_id, user=self).delete()
        self.strike_count = self.strikes.count()
        self.save(update_fields=['strike_count', 'updated_at'])


class Vehicle(models.Model):
    TYPE_SEDAN = 'sedan'
    TYPE_SUV = 'suv'
    TYPE_MINIBUS = 'minibus'
    TYPE_CHOICES = [
        (TYPE_SEDAN, 'Sedan'),
        (TYPE_SUV, 'SUV / 4x4'),
        (TYPE_MINIBUS, 'Minibus'),
    ]

    PRICE_MULTIPLIERS = {
        TYPE_SEDAN: 1.0,
        TYPE_SUV: 1.1,
        TYPE_MINIBUS: 0.85,
    }

    driver = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vehicle')
    vehicle_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    color = models.CharField(max_length=30)
    plate_number = models.CharField(max_length=20, unique=True)
    total_seats = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    photo_front = models.ImageField(upload_to='vehicles/', blank=True, null=True)
    photo_back = models.ImageField(upload_to='vehicles/', blank=True, null=True)
    photo_interior = models.ImageField(upload_to='vehicles/', blank=True, null=True)
    # ── Financial / maintenance fields ──────────────────────────────────────
    FUEL_PETROL = 'petrol'
    FUEL_DIESEL = 'diesel'
    FUEL_CHOICES = [(FUEL_PETROL, 'Petrol'), (FUEL_DIESEL, 'Diesel')]
    fuel_type = models.CharField(max_length=10, choices=FUEL_CHOICES, default=FUEL_PETROL)
    fuel_consumption_l_per_100km = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    last_service_date = models.DateField(null=True, blank=True)
    last_service_odometer_km = models.PositiveIntegerField(default=0)
    service_interval_km = models.PositiveIntegerField(default=5000)
    service_interval_months = models.PositiveSmallIntegerField(default=3)
    estimated_service_cost_zmw = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('500.00'))
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicles'

    def __str__(self):
        return f'{self.make} {self.model} ({self.plate_number})'

    @property
    def price_multiplier(self):
        return self.PRICE_MULTIPLIERS.get(self.vehicle_type, 1.0)


class DriverProfile(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
    national_id = models.ImageField(upload_to='documents/', blank=True, null=True)
    drivers_license = models.ImageField(upload_to='documents/', blank=True, null=True)
    vehicle_registration = models.ImageField(upload_to='documents/', blank=True, null=True)
    fitness_certificate = models.ImageField(upload_to='documents/', blank=True, null=True)
    insurance_certificate = models.ImageField(upload_to='documents/', blank=True, null=True)
    plate_photo = models.ImageField(upload_to='documents/', blank=True, null=True)
    verification_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    rejection_reason = models.TextField(blank=True)
    is_online = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    total_trips = models.PositiveIntegerField(default=0)
    approved_at = models.DateTimeField(null=True, blank=True)
    # ── Driver financial preferences ─────────────────────────────────────────
    fuel_price_per_litre = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('35.00'))
    vehicle_notes = models.TextField(blank=True)
    budget_dismissed_week = models.DateField(null=True, blank=True)
    budget_dismissed_month = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'driver_profiles'

    def __str__(self):
        return f'Driver: {self.user.full_name} [{self.verification_status}]'

    @property
    def is_approved(self):
        return self.verification_status == self.STATUS_APPROVED


class RiderProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rider_profile')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    total_rides = models.PositiveIntegerField(default=0)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rider_profiles'

    def __str__(self):
        return f'Rider: {self.user.full_name}'


class Strike(models.Model):
    REASON_LOW_RATING   = 'low_rating'
    REASON_NO_SHOW      = 'no_show'
    REASON_MISCONDUCT   = 'misconduct'
    REASON_FRAUD        = 'fraud'
    REASON_OTHER        = 'other'
    REASON_CHOICES = [
        (REASON_LOW_RATING,  'Low Rating (auto)'),
        (REASON_NO_SHOW,     'No Show / Late Cancellation'),
        (REASON_MISCONDUCT,  'Misconduct / Complaint'),
        (REASON_FRAUD,       'Fraud / Payment Issue'),
        (REASON_OTHER,       'Other'),
    ]

    user           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='strikes')
    reason         = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes          = models.TextField(blank=True)
    given_by       = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='strikes_given'
    )
    auto_generated = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'strikes'
        ordering = ['-created_at']

    def __str__(self):
        return f'Strike #{self.pk} on {self.user.full_name} [{self.reason}]'


class SavedPlace(models.Model):
    LABEL_HOME = 'home'
    LABEL_WORK = 'work'
    LABEL_CUSTOM = 'custom'
    LABEL_CHOICES = [
        (LABEL_HOME, 'Home'),
        (LABEL_WORK, 'Work'),
        (LABEL_CUSTOM, 'Custom'),
    ]

    rider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_places')
    label = models.CharField(max_length=10, choices=LABEL_CHOICES, default=LABEL_CUSTOM)
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'saved_places'

    def __str__(self):
        return f'{self.rider.full_name} — {self.name}'
