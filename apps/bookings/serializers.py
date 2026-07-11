from rest_framework import serializers
from django.db import transaction
from apps.pricing.engine import FareEngine
from apps.trips.models import Trip
from .models import Booking, Rating


class BookingCreateSerializer(serializers.ModelSerializer):
    trip_id = serializers.PrimaryKeyRelatedField(
        queryset=Trip.objects.all(), source='trip', write_only=True
    )
    seats_booked = serializers.IntegerField(min_value=1, max_value=6, default=1)

    class Meta:
        model = Booking
        fields = [
            'trip_id', 'seats_booked',
            'pickup_name', 'pickup_lat', 'pickup_lng',
            'dropoff_name', 'dropoff_lat', 'dropoff_lng',
        ]

    def validate(self, data):
        trip = data['trip']
        rider = self.context['request'].user
        seats = data.get('seats_booked', 1)

        if trip.status not in [Trip.STATUS_SCHEDULED, Trip.STATUS_ACTIVE]:
            raise serializers.ValidationError('This trip is no longer accepting bookings.')
        if trip.status == Trip.STATUS_SCHEDULED and not trip.booking_window_open:
            raise serializers.ValidationError('The booking window for this trip has closed.')
        if trip.available_seats < seats:
            raise serializers.ValidationError(f'Only {trip.available_seats} seat(s) available on this trip.')
        if trip.driver == rider:
            raise serializers.ValidationError('You cannot book your own trip.')

        if Booking.objects.filter(
            trip=trip, rider=rider, status__in=[Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED]
        ).exists():
            raise serializers.ValidationError('You already have a booking on this trip.')

        detour_km = FareEngine.calculate_detour_km(
            float(trip.origin_lat), float(trip.origin_lng),
            float(data['pickup_lat']), float(data['pickup_lng']),
            pickup_radius_km=0.5,
        )
        detour_fee = FareEngine.calculate_detour_fee(detour_km, trip.trip_type)

        from decimal import Decimal
        data['detour_km'] = detour_km
        data['detour_fee'] = detour_fee
        # Private trips have a locked fare — never divide by seat count.
        if trip.mode == Trip.MODE_PRIVATE:
            base_fare = trip.private_fare + Decimal(str(detour_fee))
        else:
            base_fare = trip.current_shared_fare + Decimal(str(detour_fee))
        surcharge = rider.fare_surcharge_pct
        if surcharge > 0:
            base_fare = base_fare * (1 + Decimal(str(surcharge)) / 100)
        data['fare_at_booking'] = base_fare.quantize(Decimal('0.01'))

        return data

    @transaction.atomic
    def create(self, validated_data):
        trip = validated_data['trip']
        rider = self.context['request'].user
        seats = validated_data.get('seats_booked', 1)

        trip.available_seats -= seats
        trip.save(update_fields=['available_seats', 'updated_at'])

        return Booking.objects.create(rider=rider, status=Booking.STATUS_CONFIRMED, **validated_data)


class BookingListSerializer(serializers.ModelSerializer):
    trip_origin = serializers.CharField(source='trip.origin_name', read_only=True)
    trip_destination = serializers.CharField(source='trip.destination_name', read_only=True)
    trip_departure = serializers.DateTimeField(source='trip.departure_time', read_only=True)
    amount_due = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    driver_id = serializers.IntegerField(source='trip.driver.id', read_only=True)
    driver_name = serializers.CharField(source='trip.driver.full_name', read_only=True)
    driver_phone = serializers.CharField(source='trip.driver.phone_number', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'trip_id', 'driver_id', 'trip_origin', 'trip_destination', 'trip_departure',
            'driver_name', 'driver_phone',
            'pickup_name', 'dropoff_name',
            'seats_booked', 'fare_at_booking', 'fare_final', 'amount_due',
            'detour_fee', 'status', 'payment_method', 'created_at',
        ]


class BookingDetailSerializer(serializers.ModelSerializer):
    amount_due = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    driver_name = serializers.CharField(source='trip.driver.full_name', read_only=True)
    driver_phone = serializers.CharField(source='trip.driver.phone_number', read_only=True)
    vehicle_plate = serializers.CharField(source='trip.vehicle.plate_number', read_only=True)
    vehicle_make_model = serializers.SerializerMethodField()
    trip_current_shared_fare = serializers.DecimalField(
        source='trip.current_shared_fare', max_digits=8, decimal_places=2, read_only=True
    )

    class Meta:
        model = Booking
        fields = [
            'id', 'trip_id',
            'driver_name', 'driver_phone', 'vehicle_plate', 'vehicle_make_model',
            'pickup_name', 'pickup_lat', 'pickup_lng',
            'dropoff_name', 'dropoff_lat', 'dropoff_lng',
            'seats_booked', 'detour_km', 'detour_fee',
            'fare_at_booking', 'fare_final', 'amount_due', 'trip_current_shared_fare',
            'status', 'payment_method',
            'cancelled_at', 'cancellation_reason',
            'created_at', 'updated_at',
        ]

    def get_vehicle_make_model(self, obj):
        v = obj.trip.vehicle
        return f'{v.make} {v.model} ({v.color})'


class DriverBookingSerializer(serializers.ModelSerializer):
    """Driver view of bookings on their trip."""
    rider_name = serializers.CharField(source='rider.full_name', read_only=True)
    rider_phone = serializers.CharField(source='rider.phone_number', read_only=True)
    amount_due = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    is_picked_up = serializers.BooleanField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'rider_name', 'rider_phone',
            'pickup_name', 'pickup_lat', 'pickup_lng',
            'dropoff_name', 'dropoff_lat', 'dropoff_lng',
            'seats_booked', 'detour_fee', 'amount_due',
            'status', 'payment_method', 'created_at',
            'picked_up_at', 'is_picked_up',
        ]


class RatingSerializer(serializers.ModelSerializer):
    rated_user_name = serializers.CharField(source='rated_user.full_name', read_only=True)
    rated_by_name = serializers.CharField(source='rated_by.full_name', read_only=True)

    class Meta:
        model = Rating
        fields = ['id', 'booking', 'stars', 'comment', 'rated_user_name', 'rated_by_name', 'created_at']
        read_only_fields = ['id', 'rated_user_name', 'rated_by_name', 'created_at']

    def validate_stars(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Stars must be between 1 and 5.')
        return value
