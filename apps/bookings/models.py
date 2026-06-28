from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_NO_SHOW = 'no_show'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_NO_SHOW, 'No Show'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    PAYMENT_CASH = 'cash'
    PAYMENT_CHOICES = [(PAYMENT_CASH, 'Cash')]

    trip = models.ForeignKey(
        'trips.Trip', on_delete=models.PROTECT, related_name='bookings'
    )
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='bookings'
    )

    seats_booked = models.PositiveSmallIntegerField(default=1)

    # Rider's actual pickup (may differ from trip origin — detour case)
    pickup_name = models.CharField(max_length=255)
    pickup_lat = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_lng = models.DecimalField(max_digits=9, decimal_places=6)

    # Rider's dropoff (same as trip destination or an earlier stop)
    dropoff_name = models.CharField(max_length=255)
    dropoff_lat = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_lng = models.DecimalField(max_digits=9, decimal_places=6)

    detour_km = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal('0'))
    detour_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))

    # Shown to rider during booking window — estimate, not final for shared rides.
    # For private bookings this IS the final fare (locked immediately).
    fare_at_booking = models.DecimalField(max_digits=8, decimal_places=2)

    # Set when booking window closes (shared) or at booking time (private).
    fare_final = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_CHOICES, default=PAYMENT_CASH
    )

    picked_up_at = models.DateTimeField(null=True, blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bookings'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['trip', 'rider'],
                condition=models.Q(status__in=['pending', 'confirmed']),
                name='unique_active_booking_per_trip_rider',
            )
        ]

    def __str__(self):
        return f'Booking #{self.pk} | {self.rider} on trip #{self.trip_id} [{self.status}]'

    @property
    def amount_due(self):
        return self.fare_final if self.fare_final is not None else self.fare_at_booking

    def cancel(self, reason=''):
        self.status = self.STATUS_CANCELLED
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])
        trip = self.trip
        trip.available_seats += self.seats_booked
        trip.save(update_fields=['available_seats', 'updated_at'])

    @property
    def is_picked_up(self):
        return self.picked_up_at is not None

    def mark_picked_up(self):
        if not self.picked_up_at:
            self.picked_up_at = timezone.now()
            self.save(update_fields=['picked_up_at', 'updated_at'])

    def mark_no_show(self):
        self.status = self.STATUS_NO_SHOW
        self.save(update_fields=['status', 'updated_at'])

    def complete(self, final_fare=None):
        self.status = self.STATUS_COMPLETED
        if final_fare is not None:
            self.fare_final = final_fare
        self.save(update_fields=['status', 'fare_final', 'updated_at'])


class Rating(models.Model):
    """One rating per (booking, rated_by) pair — both rider→driver and driver→rider."""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='ratings')
    rated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratings_given'
    )
    rated_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratings_received'
    )
    stars = models.PositiveSmallIntegerField()  # 1–5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ratings'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['booking', 'rated_by'],
                name='unique_rating_per_booking_rater',
            )
        ]

    def __str__(self):
        return f'Rating #{self.pk} | {self.rated_by} → {self.rated_user} ({self.stars}★)'
