from celery import shared_task
from celery.schedules import crontab


@shared_task
def create_recurring_trip_instances():
    from apps.trips.models import RecurringTrip
    from django.utils import timezone
    tomorrow = (timezone.now() + timezone.timedelta(days=1)).date()
    created = RecurringTrip.objects.create_instances_for_date(tomorrow)
    return f'Created {len(created)} trip instances for {tomorrow}'


@shared_task
def auto_cancel_trips_minimum_not_met():
    from apps.trips.models import Trip
    from django.utils import timezone
    count = Trip.objects.cancel_trips_minimum_not_met(timezone.now())
    return f'Cancelled {count} trips (minimum riders not met)'


@shared_task
def expire_stale_ride_requests():
    """Expire pending RideRequests older than TWAMBO_BOOKING_WINDOW_MINUTES."""
    from apps.trips.models import RideRequest
    from django.utils import timezone
    from django.conf import settings
    from datetime import timedelta

    minutes = getattr(settings, 'TWAMBO_BOOKING_WINDOW_MINUTES', 7)
    cutoff = timezone.now() - timedelta(minutes=minutes)
    updated = RideRequest.objects.filter(
        status=RideRequest.STATUS_PENDING,
        created_at__lt=cutoff,
    ).update(status=RideRequest.STATUS_EXPIRED)
    return f'Expired {updated} stale ride request(s)'
