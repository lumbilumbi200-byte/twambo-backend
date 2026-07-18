from celery import shared_task


@shared_task
def send_push_notification(user_id, title, body, data=None):
    from apps.accounts.models import User
    from apps.notifications.models import Notification
    try:
        user = User.objects.get(id=user_id)
        # Always persist the notification in DB
        Notification.objects.create(
            user=user,
            notification_type=data.get('type', 'general') if data else 'general',
            title=title,
            body=body,
            data=data or {},
        )
        if user.fcm_token:
            from apps.notifications.services import FCMService
            FCMService.send(user.fcm_token, title, body, data or {})
    except User.DoesNotExist:
        pass


@shared_task
def send_push_to_trip_riders(trip_id, title, body, data=None):
    """Notify all confirmed riders on a trip."""
    from apps.bookings.models import Booking
    bookings = Booking.objects.filter(
        trip_id=trip_id,
        status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_PENDING],
    ).select_related('rider')

    for booking in bookings:
        send_push_notification(
            booking.rider_id, title, body, data or {}
        )
