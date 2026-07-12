from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class RecurringTripManager(models.Manager):
    def create_instances_for_date(self, date):
        day_name = date.strftime('%A').lower()
        templates = self.filter(is_active=True, **{day_name: True})
        created = []
        for template in templates:
            departure_dt = timezone.make_aware(
                timezone.datetime.combine(date, template.departure_time),
                timezone.get_current_timezone(),
            )
            already_exists = Trip.objects.filter(
                recurring_template=template,
                departure_time__date=date,
            ).exists()
            if not already_exists:
                trip = Trip.objects.create(
                    driver=template.driver,
                    vehicle=template.vehicle,
                    origin_name=template.origin_name,
                    origin_lat=template.origin_lat,
                    origin_lng=template.origin_lng,
                    destination_name=template.destination_name,
                    destination_lat=template.destination_lat,
                    destination_lng=template.destination_lng,
                    departure_time=departure_dt,
                    total_seats=template.total_seats,
                    available_seats=template.total_seats,
                    minimum_riders=template.minimum_riders,
                    mode=template.mode,
                    recurring_template=template,
                    route_fare=template.route_fare,
                    private_fare=template.private_fare,
                )
                created.append(trip)
        return created


class TripManager(models.Manager):
    def cancel_trips_minimum_not_met(self, now):
        from django.db.models import Count, Q, F
        trips = (
            self.filter(status=Trip.STATUS_SCHEDULED, departure_time__lte=now)
            .annotate(confirmed=Count('bookings', filter=Q(bookings__status='confirmed')))
            .filter(confirmed__lt=F('minimum_riders'))
        )
        count = trips.count()
        trips.update(status=Trip.STATUS_CANCELLED)
        return count


class RecurringTrip(models.Model):
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recurring_trips'
    )
    vehicle = models.ForeignKey(
        'accounts.Vehicle', on_delete=models.PROTECT, related_name='recurring_trips'
    )

    origin_name = models.CharField(max_length=255)
    origin_lat = models.DecimalField(max_digits=9, decimal_places=6)
    origin_lng = models.DecimalField(max_digits=9, decimal_places=6)

    destination_name = models.CharField(max_length=255)
    destination_lat = models.DecimalField(max_digits=9, decimal_places=6)
    destination_lng = models.DecimalField(max_digits=9, decimal_places=6)

    departure_time = models.TimeField()

    MODE_SHARED = 'shared'
    MODE_PRIVATE = 'private'
    MODE_DYNAMIC = 'dynamic'
    MODE_CHOICES = [
        (MODE_SHARED, 'Shared'),
        (MODE_PRIVATE, 'Private'),
        (MODE_DYNAMIC, 'Dynamic'),
    ]
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_SHARED)

    monday = models.BooleanField(default=False)
    tuesday = models.BooleanField(default=False)
    wednesday = models.BooleanField(default=False)
    thursday = models.BooleanField(default=False)
    friday = models.BooleanField(default=False)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)

    total_seats = models.PositiveSmallIntegerField()
    minimum_riders = models.PositiveSmallIntegerField(default=1)

    # Cached fares so trip instances don't need to recalculate
    route_fare = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    private_fare = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RecurringTripManager()

    class Meta:
        db_table = 'recurring_trips'

    def __str__(self):
        days = [
            d for d in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            if getattr(self, d)
        ]
        return f"{self.driver} | {self.origin_name}→{self.destination_name} @ {self.departure_time} [{', '.join(days)}]"


class Trip(models.Model):
    STATUS_SCHEDULED = 'scheduled'
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    MODE_SHARED = 'shared'
    MODE_PRIVATE = 'private'
    MODE_DYNAMIC = 'dynamic'
    MODE_CHOICES = [
        (MODE_SHARED, 'Shared'),
        (MODE_PRIVATE, 'Private'),
        (MODE_DYNAMIC, 'Dynamic'),
    ]

    TYPE_CITY = 'city'
    TYPE_HIKE = 'hike'
    TYPE_CHOICES = [
        (TYPE_CITY, 'City'),
        (TYPE_HIKE, 'Hike'),
    ]

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='trips_as_driver'
    )
    vehicle = models.ForeignKey(
        'accounts.Vehicle', on_delete=models.PROTECT, related_name='trips'
    )

    origin_name = models.CharField(max_length=255)
    origin_lat = models.DecimalField(max_digits=9, decimal_places=6)
    origin_lng = models.DecimalField(max_digits=9, decimal_places=6)

    destination_name = models.CharField(max_length=255)
    destination_lat = models.DecimalField(max_digits=9, decimal_places=6)
    destination_lng = models.DecimalField(max_digits=9, decimal_places=6)

    departure_time = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_SCHEDULED, db_index=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_SHARED)
    trip_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_CITY, db_index=True)

    total_seats = models.PositiveSmallIntegerField()
    available_seats = models.PositiveSmallIntegerField()
    minimum_riders = models.PositiveSmallIntegerField(default=1)

    # route_fare = full route cost (shared, not per-rider). Divide by seats_taken for per-rider fare.
    route_fare = models.DecimalField(max_digits=8, decimal_places=2)
    private_fare = models.DecimalField(max_digits=8, decimal_places=2)

    booking_window_open = models.BooleanField(default=True)
    booking_window_closes_at = models.DateTimeField(null=True, blank=True)

    recurring_template = models.ForeignKey(
        RecurringTrip, null=True, blank=True, on_delete=models.SET_NULL, related_name='instances'
    )

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TripManager()

    class Meta:
        db_table = 'trips'
        ordering = ['departure_time']

    def __str__(self):
        return f"[{self.status}] {self.origin_name}→{self.destination_name} @ {self.departure_time}"

    @property
    def seats_taken(self):
        return self.total_seats - self.available_seats

    @property
    def current_shared_fare(self):
        """Per-rider fare.

        Hike trips: route_fare IS the per-seat price — every city pickup pays the
        full amount regardless of how many others are in the car.  The driver
        earns more as occupancy grows.

        City trips: route_fare is the total cost split equally among riders, so
        the per-seat price falls as more people join.
        """
        if self.trip_type == 'hike':
            return self.route_fare.quantize(Decimal('0.01'))
        taken = max(self.seats_taken, 1)
        return (self.route_fare / taken).quantize(Decimal('0.01'))

    def start(self):
        self.status = self.STATUS_ACTIVE
        self.started_at = timezone.now()
        self.booking_window_open = False
        self.save(update_fields=['status', 'started_at', 'booking_window_open', 'updated_at'])

    def complete(self):
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def cancel(self):
        self.status = self.STATUS_CANCELLED
        self.save(update_fields=['status', 'updated_at'])


class RideRequest(models.Model):
    """A rider's broadcast request for a dynamic/private ride."""
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_requests'
    )

    origin_name = models.CharField(max_length=255)
    origin_lat = models.DecimalField(max_digits=9, decimal_places=6)
    origin_lng = models.DecimalField(max_digits=9, decimal_places=6)

    destination_name = models.CharField(max_length=255)
    destination_lat = models.DecimalField(max_digits=9, decimal_places=6)
    destination_lng = models.DecimalField(max_digits=9, decimal_places=6)

    mode = models.CharField(max_length=10, choices=Trip.MODE_CHOICES, default=Trip.MODE_DYNAMIC)
    fare_estimate = models.DecimalField(max_digits=8, decimal_places=2)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    # For broadcast requests: null until a driver accepts
    accepted_trip = models.ForeignKey(
        Trip, null=True, blank=True, on_delete=models.SET_NULL, related_name='joined_requests'
    )
    # For EN ROUTE join requests: rider directly targets a specific active trip
    requested_trip = models.ForeignKey(
        Trip, null=True, blank=True, on_delete=models.SET_NULL, related_name='join_requests'
    )

    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ride_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'RideRequest #{self.pk} | {self.rider} [{self.status}] {self.origin_name}→{self.destination_name}'
