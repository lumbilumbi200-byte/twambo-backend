from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_BOOKING_CONFIRMED = 'booking_confirmed'
    TYPE_TRIP_STARTING = 'trip_starting'
    TYPE_TRIP_COMPLETED = 'trip_completed'
    TYPE_TRIP_CANCELLED = 'trip_cancelled'
    TYPE_BOOKING_CANCELLED = 'booking_cancelled'
    TYPE_NO_SHOW = 'no_show'
    TYPE_STRIKE = 'strike'
    TYPE_CHOICES = [
        (TYPE_BOOKING_CONFIRMED, 'Booking Confirmed'),
        (TYPE_TRIP_STARTING, 'Trip Starting'),
        (TYPE_TRIP_COMPLETED, 'Trip Completed'),
        (TYPE_TRIP_CANCELLED, 'Trip Cancelled'),
        (TYPE_BOOKING_CANCELLED, 'Booking Cancelled'),
        (TYPE_NO_SHOW, 'No Show'),
        (TYPE_STRIKE, 'Strike Issued'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    notification_type = models.CharField(max_length=25, choices=TYPE_CHOICES)
    title = models.CharField(max_length=100)
    body = models.CharField(max_length=255)
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} — {self.title}'
