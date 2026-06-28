from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from django.db.models import Q
from .models import Trip, RecurringTrip, RideRequest
from rest_framework.exceptions import PermissionDenied
from .serializers import (
    TripCreateSerializer, TripListSerializer,
    TripDetailSerializer, RecurringTripSerializer,
    RideRequestCreateSerializer, RideRequestListSerializer,
    DriverRideRequestSerializer,
)


def _finalize_trip(trip):
    """
    Called when a driver marks a trip as completed.
    1. Locks final fares and completes all confirmed bookings.
    2. Creates a Commission record and deducts from driver wallet.
    3. Notifies all riders.
    """
    from apps.bookings.models import Booking
    from apps.payments.models import Commission, DriverWallet
    from apps.notifications.tasks import send_push_notification

    bookings = Booking.objects.filter(
        trip=trip, status=Booking.STATUS_CONFIRMED
    ).select_related('rider')

    final_fare = trip.current_shared_fare
    total_revenue = Decimal('0')

    for booking in bookings:
        booking.complete(final_fare=final_fare + booking.detour_fee)
        total_revenue += booking.fare_final or Decimal('0')
        # Bump rider stats
        try:
            profile = booking.rider.rider_profile
            profile.total_rides += 1
            profile.save(update_fields=['total_rides'])
        except Exception:
            pass
        # Notify rider
        send_push_notification.delay(
            booking.rider_id,
            'Trip Completed',
            f'Your ride to {trip.destination_name} is complete. Amount due: K{booking.fare_final}',
            {'type': 'trip_completed', 'trip_id': str(trip.id), 'booking_id': str(booking.id)},
        )

    # Commission — 10% launch rate
    if total_revenue > 0:
        rate = Decimal(str(settings.TWAMBO_COMMISSION_RATE_LAUNCH))
        commission_amount = (total_revenue * rate).quantize(Decimal('0.01'))
        commission = Commission.objects.create(
            driver=trip.driver,
            trip=trip,
            trip_revenue=total_revenue,
            rate=rate,
            amount=commission_amount,
        )
        commission.deduct()

        # Auto-offline if float drops below K50 minimum
        try:
            wallet = DriverWallet.objects.get(driver=trip.driver)
            if wallet.balance < wallet.minimum_float:
                profile = trip.driver.driver_profile
                if profile.is_online:
                    profile.is_online = False
                    profile.save(update_fields=['is_online'])
                    from apps.notifications.tasks import send_push_notification
                    send_push_notification.delay(
                        trip.driver_id,
                        'Float Too Low',
                        f'Your float (K{wallet.balance}) is below K{wallet.minimum_float}. Top up to go online again.',
                        {'type': 'float_low', 'balance': str(wallet.balance)},
                    )
        except Exception:
            pass

    # Bump driver stats
    try:
        profile = trip.driver.driver_profile
        profile.total_trips += 1
        profile.save(update_fields=['total_trips'])
    except Exception:
        pass


class IsApprovedDriver(permissions.BasePermission):
    def has_permission(self, request, view):
        if not (request.user.is_authenticated and request.user.role == 'driver'):
            return False
        try:
            return request.user.driver_profile.is_approved
        except Exception:
            return False


# ── Driver: create / list / detail ──────────────────────────────────────────

class DriverTripCreateView(generics.CreateAPIView):
    serializer_class = TripCreateSerializer
    permission_classes = [IsApprovedDriver]


class DriverTripListView(generics.ListAPIView):
    serializer_class = TripListSerializer
    permission_classes = [IsApprovedDriver]

    def get_queryset(self):
        return Trip.objects.filter(driver=self.request.user).select_related('vehicle').order_by('-created_at')


class DriverTripDetailView(generics.RetrieveAPIView):
    serializer_class = TripDetailSerializer
    permission_classes = [IsApprovedDriver]

    def get_queryset(self):
        return Trip.objects.filter(driver=self.request.user)


# ── Driver: FSM actions ──────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsApprovedDriver])
def trip_start(request, pk):
    try:
        trip = Trip.objects.get(pk=pk, driver=request.user)
    except Trip.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if trip.status != Trip.STATUS_SCHEDULED:
        return Response(
            {'detail': f'Cannot start a {trip.status} trip.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    trip.start()
    from apps.notifications.tasks import send_push_to_trip_riders
    send_push_to_trip_riders.delay(
        trip.id,
        'Your driver is on the way!',
        f'{trip.driver.full_name} has started the trip to {trip.destination_name}.',
        {'type': 'trip_starting', 'trip_id': str(trip.id)},
    )
    return Response({'status': 'active', 'started_at': trip.started_at})


@api_view(['POST'])
@permission_classes([IsApprovedDriver])
def trip_complete(request, pk):
    try:
        trip = Trip.objects.get(pk=pk, driver=request.user)
    except Trip.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if trip.status != Trip.STATUS_ACTIVE:
        return Response(
            {'detail': f'Cannot complete a {trip.status} trip.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    trip.complete()
    _finalize_trip(trip)
    return Response({'status': 'completed', 'completed_at': trip.completed_at})


@api_view(['POST'])
@permission_classes([IsApprovedDriver])
def trip_cancel(request, pk):
    try:
        trip = Trip.objects.get(pk=pk, driver=request.user)
    except Trip.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if trip.status not in (Trip.STATUS_SCHEDULED, Trip.STATUS_ACTIVE):
        return Response(
            {'detail': f'Cannot cancel a {trip.status} trip.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    trip.cancel()
    return Response({'status': 'cancelled'})


# ── Driver: recurring trips ──────────────────────────────────────────────────

class RecurringTripListCreateView(generics.ListCreateAPIView):
    serializer_class = RecurringTripSerializer
    permission_classes = [IsApprovedDriver]

    def get_queryset(self):
        return RecurringTrip.objects.filter(driver=self.request.user).order_by('-created_at')


class RecurringTripDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RecurringTripSerializer
    permission_classes = [IsApprovedDriver]

    def get_queryset(self):
        return RecurringTrip.objects.filter(driver=self.request.user)


# ── Rider / Public: browse & search ─────────────────────────────────────────

class TripSearchView(generics.ListAPIView):
    """
    Riders browse available trips.
    Query params:
      origin        — partial match on origin_name
      destination   — partial match on destination_name
      mode          — 'shared' | 'private' | 'hike'
      date          — YYYY-MM-DD  filter departure to that day
      min_seats     — integer, only trips with available_seats >= min_seats
    """
    serializer_class = TripListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        params = self.request.query_params
        now = timezone.now()
        qs = Trip.objects.filter(
            available_seats__gt=0,
        ).filter(
            Q(status=Trip.STATUS_SCHEDULED, booking_window_open=True, departure_time__gte=now) |
            Q(status=Trip.STATUS_ACTIVE)
        ).select_related('driver', 'vehicle')

        if origin := params.get('origin'):
            qs = qs.filter(origin_name__icontains=origin)
        if destination := params.get('destination'):
            qs = qs.filter(destination_name__icontains=destination)
        if mode := params.get('mode'):
            qs = qs.filter(mode=mode)
        if date_str := params.get('date'):
            try:
                from datetime import date as _date
                d = _date.fromisoformat(date_str)
                qs = qs.filter(departure_time__date=d)
            except ValueError:
                pass
        if min_seats := params.get('min_seats'):
            try:
                qs = qs.filter(available_seats__gte=int(min_seats))
            except ValueError:
                pass

        return qs.order_by('status', 'departure_time')


class TripDetailPublicView(generics.RetrieveAPIView):
    serializer_class = TripDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Trip.objects.select_related('driver', 'vehicle')


# ── Rider: ride requests (broadcast) ────────────────────────────────────────

class RideRequestListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RideRequestCreateSerializer
        return RideRequestListSerializer

    def get_queryset(self):
        return RideRequest.objects.filter(
            rider=self.request.user,
            status__in=[RideRequest.STATUS_PENDING, RideRequest.STATUS_ACCEPTED],
        ).order_by('-created_at')


class DriverTripRideRequestsView(generics.ListAPIView):
    """Pending RideRequests a driver can see for one of their trips.
    Mode-matched: shows requests whose mode matches the trip or is dynamic.
    Proximity filtering (near-route radius) is TODO once spatial DB is configured."""
    serializer_class = DriverRideRequestSerializer
    permission_classes = [IsApprovedDriver]

    def get_queryset(self):
        trip_id = self.kwargs['pk']
        try:
            trip = Trip.objects.get(pk=trip_id, driver=self.request.user)
        except Trip.DoesNotExist:
            raise PermissionDenied('Trip not found or not yours.')

        return RideRequest.objects.filter(
            status=RideRequest.STATUS_PENDING,
        ).filter(
            Q(requested_trip=trip) |
            Q(mode=trip.mode, accepted_trip__isnull=True) |
            Q(mode=Trip.MODE_DYNAMIC, accepted_trip__isnull=True)
        ).select_related('rider').order_by('-created_at')


@api_view(['POST'])
@permission_classes([IsApprovedDriver])
def close_booking_window(request, pk):
    """Driver manually closes the booking window — locks final fares for all confirmed bookings."""
    try:
        trip = Trip.objects.get(pk=pk, driver=request.user)
    except Trip.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not trip.booking_window_open:
        return Response({'detail': 'Window already closed.'}, status=status.HTTP_400_BAD_REQUEST)

    from apps.bookings.models import Booking
    from django.db import transaction as dbt

    with dbt.atomic():
        trip.booking_window_open = False
        trip.save(update_fields=['booking_window_open', 'updated_at'])
        final_fare = trip.current_shared_fare
        Booking.objects.filter(trip=trip, status=Booking.STATUS_CONFIRMED).update(fare_final=final_fare)

    return Response({
        'window_open': False,
        'riders_count': trip.seats_taken,
        'minimum_riders': trip.minimum_riders,
        'minimum_met': trip.seats_taken >= trip.minimum_riders,
        'final_shared_fare': str(final_fare),
    })


@api_view(['POST'])
@permission_classes([IsApprovedDriver])
def accept_ride_request(request, pk, request_pk):
    """Driver accepts a RideRequest → creates a confirmed Booking on the trip."""
    try:
        trip = Trip.objects.get(pk=pk, driver=request.user)
    except Trip.DoesNotExist:
        return Response({'detail': 'Trip not found.'}, status=status.HTTP_404_NOT_FOUND)

    if trip.status not in [Trip.STATUS_SCHEDULED, Trip.STATUS_ACTIVE]:
        return Response({'detail': 'Trip is not accepting riders.'}, status=status.HTTP_400_BAD_REQUEST)

    if trip.available_seats < 1:
        return Response({'detail': 'No seats available on this trip.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ride_req = RideRequest.objects.get(pk=request_pk, status=RideRequest.STATUS_PENDING)
    except RideRequest.DoesNotExist:
        return Response({'detail': 'Request not found or already handled.'}, status=status.HTTP_404_NOT_FOUND)

    from apps.bookings.models import Booking
    from django.db import transaction as dbt

    if Booking.objects.filter(
        trip=trip, rider=ride_req.rider,
        status__in=[Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED],
    ).exists():
        return Response({'detail': 'Rider already has a booking on this trip.'}, status=status.HTTP_400_BAD_REQUEST)

    with dbt.atomic():
        Booking.objects.create(
            trip=trip,
            rider=ride_req.rider,
            seats_booked=1,
            pickup_name=ride_req.origin_name,
            pickup_lat=ride_req.origin_lat,
            pickup_lng=ride_req.origin_lng,
            dropoff_name=ride_req.destination_name,
            dropoff_lat=ride_req.destination_lat,
            dropoff_lng=ride_req.destination_lng,
            detour_km=Decimal('0'),
            detour_fee=Decimal('0'),
            fare_at_booking=trip.current_shared_fare,
            status=Booking.STATUS_CONFIRMED,
        )
        trip.available_seats -= 1
        trip.save(update_fields=['available_seats', 'updated_at'])
        ride_req.status = RideRequest.STATUS_ACCEPTED
        ride_req.accepted_trip = trip
        ride_req.save(update_fields=['status', 'accepted_trip', 'updated_at'])

    from apps.notifications.tasks import send_push_notification
    send_push_notification.delay(
        ride_req.rider_id,
        'Request Accepted!',
        f'{trip.driver.full_name} accepted your ride to {trip.destination_name}.',
        {'type': 'ride_request_accepted', 'trip_id': str(trip.id)},
    )
    return Response({'status': 'accepted', 'trip_id': trip.id})


@api_view(['POST'])
@permission_classes([IsApprovedDriver])
def reject_ride_request(request, pk, request_pk):
    """Driver rejects a pending RideRequest."""
    try:
        Trip.objects.get(pk=pk, driver=request.user)
    except Trip.DoesNotExist:
        return Response({'detail': 'Trip not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        ride_req = RideRequest.objects.get(pk=request_pk, status=RideRequest.STATUS_PENDING)
    except RideRequest.DoesNotExist:
        return Response({'detail': 'Request not found or already handled.'}, status=status.HTTP_404_NOT_FOUND)

    ride_req.status = RideRequest.STATUS_CANCELLED
    ride_req.save(update_fields=['status', 'updated_at'])

    from apps.notifications.tasks import send_push_notification
    send_push_notification.delay(
        ride_req.rider_id,
        'Request Declined',
        f'Your ride request to {ride_req.destination_name} was not accepted.',
        {'type': 'ride_request_rejected'},
    )
    return Response({'status': 'rejected'})


# ── Driver: broadcast inbox ───────────────────────────────────────────────────

class DriverBroadcastInboxView(generics.ListAPIView):
    """All pending RideRequests visible to any online approved driver."""
    serializer_class = DriverRideRequestSerializer
    permission_classes = [IsApprovedDriver]

    def get_queryset(self):
        return RideRequest.objects.filter(
            status=RideRequest.STATUS_PENDING,
            accepted_trip__isnull=True,
            requested_trip__isnull=True,  # exclude EN ROUTE join requests (those go to the targeted trip's inbox)
            expires_at__gt=timezone.now(),
        ).select_related('rider').order_by('-created_at')


@api_view(['POST'])
@permission_classes([IsApprovedDriver])
def accept_broadcast_request(request, pk):
    """Driver accepts a broadcast RideRequest → attaches rider to driver's latest active/scheduled trip."""
    try:
        ride_req = RideRequest.objects.get(
            pk=pk, status=RideRequest.STATUS_PENDING,
            accepted_trip__isnull=True, requested_trip__isnull=True,
        )
    except RideRequest.DoesNotExist:
        return Response({'detail': 'Request not found or already handled.'}, status=status.HTTP_404_NOT_FOUND)

    if ride_req.expires_at < timezone.now():
        return Response({'detail': 'This request has expired.'}, status=status.HTTP_400_BAD_REQUEST)

    trip = Trip.objects.filter(
        driver=request.user,
        status__in=[Trip.STATUS_ACTIVE, Trip.STATUS_SCHEDULED],
        available_seats__gte=1,
    ).order_by('-created_at').first()

    if trip is None:
        return Response(
            {'detail': 'No active or scheduled trip available to assign this rider to.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from apps.bookings.models import Booking
    from django.db import transaction as dbt

    if Booking.objects.filter(
        trip=trip, rider=ride_req.rider,
        status__in=[Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED],
    ).exists():
        return Response({'detail': 'Rider already has a booking on your trip.'}, status=status.HTTP_400_BAD_REQUEST)

    with dbt.atomic():
        Booking.objects.create(
            trip=trip,
            rider=ride_req.rider,
            seats_booked=1,
            pickup_name=ride_req.origin_name,
            pickup_lat=ride_req.origin_lat,
            pickup_lng=ride_req.origin_lng,
            dropoff_name=ride_req.destination_name,
            dropoff_lat=ride_req.destination_lat,
            dropoff_lng=ride_req.destination_lng,
            detour_km=Decimal('0'),
            detour_fee=Decimal('0'),
            fare_at_booking=trip.current_shared_fare,
            status=Booking.STATUS_CONFIRMED,
        )
        trip.available_seats -= 1
        trip.save(update_fields=['available_seats', 'updated_at'])
        ride_req.status = RideRequest.STATUS_ACCEPTED
        ride_req.accepted_trip = trip
        ride_req.save(update_fields=['status', 'accepted_trip', 'updated_at'])

    from apps.notifications.tasks import send_push_notification
    send_push_notification.delay(
        ride_req.rider_id,
        'Request Accepted!',
        f'{trip.driver.full_name} accepted your ride to {trip.destination_name}.',
        {'type': 'ride_request_accepted', 'trip_id': str(trip.id)},
    )
    # Notify existing passengers about the detour if trip is already active
    if trip.status == Trip.STATUS_ACTIVE:
        existing_rider_ids = list(
            Booking.objects.filter(trip=trip, status=Booking.STATUS_CONFIRMED)
            .exclude(rider_id=ride_req.rider_id)
            .values_list('rider_id', flat=True)
        )
        for rider_id in existing_rider_ids:
            send_push_notification.delay(
                rider_id,
                'New Pickup Added',
                f'Your driver is picking up another passenger near {ride_req.origin_name}.',
                {'type': 'detour_pickup', 'trip_id': str(trip.id)},
            )
    return Response({'status': 'accepted', 'trip_id': trip.id})


@api_view(['POST'])
@permission_classes([IsApprovedDriver])
def decline_broadcast_request(request, pk):
    """Driver declines a broadcast RideRequest."""
    try:
        ride_req = RideRequest.objects.get(pk=pk, status=RideRequest.STATUS_PENDING, accepted_trip__isnull=True)
    except RideRequest.DoesNotExist:
        return Response({'detail': 'Request not found or already handled.'}, status=status.HTTP_404_NOT_FOUND)

    ride_req.status = RideRequest.STATUS_CANCELLED
    ride_req.save(update_fields=['status', 'updated_at'])

    from apps.notifications.tasks import send_push_notification
    send_push_notification.delay(
        ride_req.rider_id,
        'Request Declined',
        f'Your ride request to {ride_req.destination_name} was not accepted.',
        {'type': 'ride_request_rejected'},
    )
    return Response({'status': 'declined'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def request_join_trip(request, pk):
    """Rider requests to join a specific active (EN ROUTE) trip.
    Creates a RideRequest linked to the trip — driver must approve before a booking is created."""
    from django.utils import timezone
    from django.conf import settings as cfg
    try:
        trip = Trip.objects.get(pk=pk, status=Trip.STATUS_ACTIVE, available_seats__gte=1)
    except Trip.DoesNotExist:
        return Response({'detail': 'Trip not found or no seats available.'}, status=status.HTTP_404_NOT_FOUND)

    if request.user.role != 'rider':
        return Response({'detail': 'Only riders can send join requests.'}, status=status.HTTP_403_FORBIDDEN)

    if RideRequest.objects.filter(
        rider=request.user, requested_trip=trip, status=RideRequest.STATUS_PENDING
    ).exists():
        return Response({'detail': 'You already have a pending join request for this trip.'}, status=status.HTTP_400_BAD_REQUEST)

    pickup_name = request.data.get('pickup_name', trip.origin_name)
    dropoff_name = request.data.get('dropoff_name', trip.destination_name)
    try:
        pickup_lat = Decimal(str(request.data.get('pickup_lat', trip.origin_lat)))
        pickup_lng = Decimal(str(request.data.get('pickup_lng', trip.origin_lng)))
        dropoff_lat = Decimal(str(request.data.get('dropoff_lat', trip.destination_lat)))
        dropoff_lng = Decimal(str(request.data.get('dropoff_lng', trip.destination_lng)))
    except Exception:
        return Response({'detail': 'Invalid coordinates.'}, status=status.HTTP_400_BAD_REQUEST)

    from apps.notifications.tasks import send_push_notification
    window_minutes = getattr(cfg, 'TWAMBO_BOOKING_WINDOW_MINUTES', 10)
    ride_req = RideRequest.objects.create(
        rider=request.user,
        requested_trip=trip,
        origin_name=pickup_name,
        origin_lat=pickup_lat,
        origin_lng=pickup_lng,
        destination_name=dropoff_name,
        destination_lat=dropoff_lat,
        destination_lng=dropoff_lng,
        mode=trip.mode,
        fare_estimate=trip.current_shared_fare,
        expires_at=timezone.now() + timezone.timedelta(minutes=window_minutes),
    )

    # Notify driver
    send_push_notification.delay(
        trip.driver_id,
        'New Join Request!',
        f'{request.user.full_name} wants to join your active trip.',
        {'type': 'join_request', 'trip_id': str(trip.id), 'request_id': str(ride_req.id)},
    )
    return Response({'status': 'pending', 'request_id': ride_req.id}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def cancel_ride_request(request, pk):
    try:
        ride_req = RideRequest.objects.get(pk=pk, rider=request.user)
    except RideRequest.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if ride_req.status not in [RideRequest.STATUS_PENDING, RideRequest.STATUS_ACCEPTED]:
        return Response(
            {'detail': f'Cannot cancel a {ride_req.status} request.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    ride_req.status = RideRequest.STATUS_CANCELLED
    ride_req.save(update_fields=['status', 'updated_at'])
    return Response({'status': 'cancelled'})
