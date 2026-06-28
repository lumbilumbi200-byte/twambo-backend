from celery import shared_task


@shared_task
def expire_booking_windows():
    """
    Close booking windows for trips whose window time has passed.
    Lock the final shared fare for all confirmed bookings on those trips.
    Runs every 60 seconds via Celery Beat.
    """
    from apps.trips.models import Trip
    from apps.bookings.models import Booking
    from django.utils import timezone

    now = timezone.now()

    # Find trips whose window just expired
    expired_trips = Trip.objects.filter(
        status=Trip.STATUS_SCHEDULED,
        booking_window_open=True,
        booking_window_closes_at__lte=now,
    )

    locked = 0
    for trip in expired_trips:
        trip.booking_window_open = False
        trip.save(update_fields=['booking_window_open', 'updated_at'])

        # Lock the final fare for all confirmed bookings on this trip
        final_fare = trip.current_shared_fare
        confirmed_bookings = Booking.objects.filter(
            trip=trip,
            status=Booking.STATUS_CONFIRMED,
            fare_final__isnull=True,
        )
        updated = confirmed_bookings.update(fare_final=final_fare)
        locked += updated

    return f'Closed {expired_trips.count()} booking windows, locked fares for {locked} bookings'
