from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Booking, Rating
from .serializers import (
    BookingCreateSerializer, BookingListSerializer,
    BookingDetailSerializer, DriverBookingSerializer, RatingSerializer,
)


class IsRider(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'rider'


class IsDriver(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'driver'


# ── Rider views ──────────────────────────────────────────────────────────────

class RiderBookingCreateView(generics.CreateAPIView):
    serializer_class = BookingCreateSerializer
    permission_classes = [IsRider]


class RiderBookingListView(generics.ListAPIView):
    serializer_class = BookingListSerializer
    permission_classes = [IsRider]

    def get_queryset(self):
        return (
            Booking.objects
            .filter(rider=self.request.user)
            .select_related('trip', 'trip__driver', 'trip__vehicle')
        )


class RiderBookingDetailView(generics.RetrieveAPIView):
    serializer_class = BookingDetailSerializer
    permission_classes = [IsRider]

    def get_queryset(self):
        return Booking.objects.filter(rider=self.request.user).select_related(
            'trip', 'trip__driver', 'trip__vehicle'
        )


@api_view(['POST'])
@permission_classes([IsRider])
def rider_cancel_booking(request, pk):
    try:
        booking = Booking.objects.get(pk=pk, rider=request.user)
    except Booking.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if booking.status not in (Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED):
        return Response(
            {'detail': f'Cannot cancel a {booking.status} booking.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from django.utils import timezone
    from datetime import timedelta
    was_confirmed = booking.status == Booking.STATUS_CONFIRMED
    close_to_departure = booking.trip.departure_time - timezone.now() < timedelta(minutes=15)

    reason = request.data.get('reason', 'Rider cancelled')
    booking.cancel(reason=reason)

    if was_confirmed and close_to_departure:
        request.user.give_strike(
            reason='no_show',
            notes='Cancelled a confirmed booking within 15 min of departure.',
        )

    return Response({'status': 'cancelled'})


# ── Driver views ─────────────────────────────────────────────────────────────

class DriverTripBookingsView(generics.ListAPIView):
    """Driver sees all bookings for a specific trip."""
    serializer_class = DriverBookingSerializer
    permission_classes = [IsDriver]

    def get_queryset(self):
        trip_id = self.kwargs['trip_id']
        return Booking.objects.filter(
            trip_id=trip_id,
            trip__driver=self.request.user,
        ).select_related('rider')


@api_view(['POST'])
@permission_classes([IsDriver])
def driver_mark_picked_up(request, pk):
    """Driver marks a rider as boarded. Notifies the rider and all other passengers."""
    try:
        booking = Booking.objects.select_related('rider', 'trip').get(
            pk=pk, trip__driver=request.user, status=Booking.STATUS_CONFIRMED
        )
    except Booking.DoesNotExist:
        return Response({'detail': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

    if booking.is_picked_up:
        return Response({'detail': 'Already marked as picked up.'}, status=status.HTTP_400_BAD_REQUEST)

    booking.mark_picked_up()

    from apps.notifications.tasks import send_push_notification
    # Notify the picked-up rider
    send_push_notification(
        booking.rider_id,
        'You\'ve been picked up!',
        f'Welcome aboard — enjoy your ride to {booking.dropoff_name}.',
        {'type': 'picked_up', 'booking_id': str(booking.id), 'trip_id': str(booking.trip_id)},
    )
    # Notify other confirmed passengers so they see the sequence update
    others = Booking.objects.filter(
        trip=booking.trip, status=Booking.STATUS_CONFIRMED
    ).exclude(pk=pk).values_list('rider_id', flat=True)
    for rider_id in others:
        send_push_notification(
            rider_id,
            'Passenger picked up',
            f'{booking.rider.full_name.split()[0]} has been picked up — you\'re getting closer!',
            {'type': 'co_passenger_picked_up', 'trip_id': str(booking.trip_id)},
        )

    return Response({'picked_up_at': booking.picked_up_at})


class TripPassengersView(generics.ListAPIView):
    """Rider sees all confirmed passengers on their active trip (for sequencing).
    Only accessible if the requesting rider has a confirmed booking on this trip."""
    serializer_class = DriverBookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        trip_id = self.kwargs['trip_id']
        user = self.request.user
        # Drivers see all; riders must have a booking on this trip
        if user.role == 'driver':
            return Booking.objects.filter(
                trip_id=trip_id, trip__driver=user, status=Booking.STATUS_CONFIRMED
            ).select_related('rider')
        # Rider: verify they have a booking on this trip
        has_booking = Booking.objects.filter(
            trip_id=trip_id, rider=user,
            status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_COMPLETED]
        ).exists()
        if not has_booking:
            return Booking.objects.none()
        return Booking.objects.filter(
            trip_id=trip_id, status=Booking.STATUS_CONFIRMED
        ).select_related('rider').order_by('created_at')


@api_view(['POST'])
@permission_classes([IsDriver])
def driver_mark_no_show(request, pk):
    try:
        booking = Booking.objects.get(pk=pk, trip__driver=request.user)
    except Booking.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if booking.status != Booking.STATUS_CONFIRMED:
        return Response(
            {'detail': 'Can only mark confirmed bookings as no-show.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    booking.mark_no_show()
    booking.rider.give_strike(
        reason='no_show',
        notes=f'No-show on trip {booking.trip_id} — marked by driver.',
    )
    return Response({'status': 'no_show'})


# ── Ratings ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_rating(request, pk):
    """Submit a rating for a completed booking.
    Rider rates the driver; driver rates the rider.
    """
    try:
        booking = Booking.objects.select_related('trip__driver', 'rider').get(pk=pk)
    except Booking.DoesNotExist:
        return Response({'detail': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

    if booking.status not in (Booking.STATUS_COMPLETED, Booking.STATUS_CONFIRMED):
        return Response({'detail': 'Booking must be confirmed or completed to rate.'}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    is_rider = (booking.rider_id == user.id)
    is_driver = (booking.trip.driver_id == user.id)

    if not is_rider and not is_driver:
        return Response({'detail': 'You were not part of this booking.'}, status=status.HTTP_403_FORBIDDEN)

    if Rating.objects.filter(booking=booking, rated_by=user).exists():
        return Response({'detail': 'You have already rated this booking.'}, status=status.HTTP_400_BAD_REQUEST)

    stars = request.data.get('stars')
    comment = request.data.get('comment', '')

    serializer = RatingSerializer(data={'booking': booking.id, 'stars': stars, 'comment': comment})
    serializer.is_valid(raise_exception=True)

    rated_user = booking.trip.driver if is_rider else booking.rider
    rating = Rating.objects.create(
        booking=booking,
        rated_by=user,
        rated_user=rated_user,
        stars=serializer.validated_data['stars'],
        comment=serializer.validated_data.get('comment', ''),
    )

    # Update rated user's average rating on their profile
    from django.db.models import Avg
    from django.conf import settings as cfg
    qs = Rating.objects.filter(rated_user=rated_user)
    rating_count = qs.count()
    avg = qs.aggregate(a=Avg('stars'))['a'] or 0
    try:
        profile = rated_user.driver_profile if is_rider else rated_user.rider_profile
        if hasattr(profile, 'rating'):
            profile.rating = round(avg, 2)
            profile.save(update_fields=['rating'])
    except Exception:
        pass

    # Auto-strike if average drops below floor after enough ratings
    floor = getattr(cfg, 'TWAMBO_AUTO_STRIKE_RATING_FLOOR', 3.0)
    min_ratings = getattr(cfg, 'TWAMBO_AUTO_STRIKE_MIN_RATINGS', 5)
    if rating_count >= min_ratings and avg < floor:
        rated_user.give_strike(
            reason='low_rating',
            notes=f'Average rating dropped to {avg:.2f} after {rating_count} ratings.',
            auto_generated=True,
        )

    return Response(RatingSerializer(rating).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def my_rating_for_booking(request, pk):
    """Check if the current user already rated booking pk."""
    try:
        rating = Rating.objects.get(booking_id=pk, rated_by=request.user)
        return Response({'rated': True, 'stars': rating.stars})
    except Rating.DoesNotExist:
        return Response({'rated': False})
