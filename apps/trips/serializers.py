from rest_framework import serializers
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from apps.pricing.engine import FareEngine
from .models import Trip, RecurringTrip, RideRequest


class TripCreateSerializer(serializers.ModelSerializer):
    route_fare = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, write_only=True,
    )

    class Meta:
        model = Trip
        fields = [
            'origin_name', 'origin_lat', 'origin_lng',
            'destination_name', 'destination_lat', 'destination_lng',
            'departure_time', 'mode', 'trip_type', 'total_seats', 'minimum_riders',
            'route_fare',
        ]

    def validate_departure_time(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError('Departure time must be in the future.')
        return value

    def validate(self, data):
        if data.get('mode') == Trip.MODE_PRIVATE:
            data['minimum_riders'] = 1
        return data

    def create(self, validated_data):
        driver = self.context['request'].user
        try:
            vehicle = driver.vehicle
        except Exception:
            raise serializers.ValidationError('Driver has no registered vehicle.')

        client_route_fare = validated_data.pop('route_fare', None)

        preview = FareEngine.fare_preview(
            float(validated_data['origin_lat']),
            float(validated_data['origin_lng']),
            float(validated_data['destination_lat']),
            float(validated_data['destination_lng']),
            vehicle_multiplier=vehicle.price_multiplier,
            trip_type=validated_data.get('trip_type', 'city'),
        )

        # For hike trips the client sends the agreed market fare from kRouteFares;
        # use it when provided, fall back to FareEngine for unknown city pairs.
        is_hike = validated_data.get('trip_type') == Trip.TYPE_HIKE
        route_fare = (
            client_route_fare
            if is_hike and client_route_fare is not None
            else Decimal(str(preview['shared_fare']))
        )

        booking_window_closes_at = (
            validated_data['departure_time']
            - timezone.timedelta(minutes=settings.TWAMBO_BOOKING_WINDOW_MINUTES)
        )

        return Trip.objects.create(
            driver=driver,
            vehicle=vehicle,
            route_fare=route_fare,
            private_fare=Decimal(str(preview['private_fare'])),
            available_seats=validated_data['total_seats'],
            booking_window_closes_at=booking_window_closes_at,
            **validated_data,
        )


class TripListSerializer(serializers.ModelSerializer):
    current_shared_fare = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    seats_taken = serializers.IntegerField(read_only=True)
    driver_id = serializers.IntegerField(source='driver.id', read_only=True)
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    vehicle_type = serializers.CharField(source='vehicle.vehicle_type', read_only=True)
    vehicle_make_model = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            'id', 'driver_id', 'driver_name', 'vehicle_type', 'vehicle_make_model',
            'origin_name', 'origin_lat', 'origin_lng',
            'destination_name', 'destination_lat', 'destination_lng',
            'departure_time', 'status', 'mode', 'trip_type',
            'total_seats', 'available_seats', 'seats_taken',
            'current_shared_fare', 'private_fare',
            'booking_window_open', 'minimum_riders',
        ]

    def get_vehicle_make_model(self, obj):
        v = obj.vehicle
        return f'{v.make} {v.model} ({v.color})'


class TripDetailSerializer(serializers.ModelSerializer):
    current_shared_fare = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    seats_taken = serializers.IntegerField(read_only=True)
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    driver_id = serializers.IntegerField(source='driver.id', read_only=True)
    vehicle_type = serializers.CharField(source='vehicle.vehicle_type', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate_number', read_only=True)
    vehicle_make_model = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            'id', 'driver_id', 'driver_name',
            'vehicle_type', 'vehicle_plate', 'vehicle_make_model',
            'origin_name', 'origin_lat', 'origin_lng',
            'destination_name', 'destination_lat', 'destination_lng',
            'departure_time', 'status', 'mode', 'trip_type',
            'total_seats', 'available_seats', 'seats_taken', 'minimum_riders',
            'route_fare', 'current_shared_fare', 'private_fare',
            'booking_window_open', 'booking_window_closes_at',
            'started_at', 'completed_at', 'created_at',
        ]

    def get_vehicle_make_model(self, obj):
        v = obj.vehicle
        return f'{v.make} {v.model} ({v.color})'


class RideRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideRequest
        fields = [
            'origin_name', 'origin_lat', 'origin_lng',
            'destination_name', 'destination_lat', 'destination_lng',
            'mode', 'fare_estimate',
        ]

    def create(self, validated_data):
        expires_at = timezone.now() + timezone.timedelta(minutes=10)
        return RideRequest.objects.create(
            rider=self.context['request'].user,
            expires_at=expires_at,
            **validated_data,
        )


class RideRequestListSerializer(serializers.ModelSerializer):
    """Returns fields compatible with Flutter's Booking.fromJson() so the My Bookings
    screen can display pending ride requests and confirmed bookings in one list."""
    trip_id = serializers.SerializerMethodField()
    driver_id = serializers.SerializerMethodField()
    trip_origin = serializers.CharField(source='origin_name')
    trip_destination = serializers.CharField(source='destination_name')
    trip_departure = serializers.DateTimeField(source='created_at')
    driver_name = serializers.SerializerMethodField()
    pickup_name = serializers.CharField(source='origin_name')
    dropoff_name = serializers.CharField(source='destination_name')
    seats_booked = serializers.SerializerMethodField()
    fare_at_booking = serializers.DecimalField(source='fare_estimate', max_digits=8, decimal_places=2)
    fare_final = serializers.SerializerMethodField()
    amount_due = serializers.DecimalField(source='fare_estimate', max_digits=8, decimal_places=2)
    detour_fee = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()

    class Meta:
        model = RideRequest
        fields = [
            'id', 'trip_id', 'driver_id',
            'trip_origin', 'trip_destination', 'trip_departure',
            'driver_name', 'pickup_name', 'dropoff_name',
            'seats_booked', 'fare_at_booking', 'fare_final', 'amount_due', 'detour_fee',
            'status', 'payment_method', 'created_at',
        ]

    def get_trip_id(self, obj):
        return obj.accepted_trip_id if obj.accepted_trip_id else -1

    def get_driver_id(self, obj):
        return 0

    def get_driver_name(self, obj):
        if obj.mode == Trip.MODE_DYNAMIC:
            return 'Finding riders…'
        return 'Searching driver…'

    def get_seats_booked(self, obj):
        return 1

    def get_fare_final(self, obj):
        return None

    def get_detour_fee(self, obj):
        return '0.00'

    def get_payment_method(self, obj):
        return 'cash'


class DriverRideRequestSerializer(serializers.ModelSerializer):
    """Ride requests visible to a driver scoped to one of their trips."""
    rider_initials = serializers.SerializerMethodField()
    created_mins_ago = serializers.SerializerMethodField()

    class Meta:
        model = RideRequest
        fields = [
            'id', 'origin_name', 'origin_lat', 'origin_lng',
            'destination_name', 'destination_lat', 'destination_lng',
            'mode', 'fare_estimate', 'status',
            'rider_initials', 'created_at', 'created_mins_ago',
        ]

    def get_rider_initials(self, obj):
        name = getattr(obj, '_rider_name', '') or (obj.rider.full_name if hasattr(obj, 'rider') else '')
        return name[0].upper() if name else '?'

    def get_created_mins_ago(self, obj):
        delta = timezone.now() - obj.created_at
        return max(0, int(delta.total_seconds() / 60))


class RecurringTripSerializer(serializers.ModelSerializer):
    DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    route_fare = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    private_fare = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    days_of_week = serializers.SerializerMethodField()

    class Meta:
        model = RecurringTrip
        exclude = ['driver']
        extra_kwargs = {
            'vehicle': {'read_only': True},
            'monday': {'required': False},
            'tuesday': {'required': False},
            'wednesday': {'required': False},
            'thursday': {'required': False},
            'friday': {'required': False},
            'saturday': {'required': False},
            'sunday': {'required': False},
        }

    def get_days_of_week(self, obj):
        return [d for d in self.DAYS if getattr(obj, d, False)]

    def validate(self, data):
        days = self.initial_data.get('days_of_week', [])
        if isinstance(days, list) and days:
            for d in self.DAYS:
                data[d] = d in days
        if not any(data.get(d, False) for d in self.DAYS):
            raise serializers.ValidationError('Select at least one day of the week.')
        return data

    def create(self, validated_data):
        driver = self.context['request'].user
        try:
            vehicle = driver.vehicle
        except Exception:
            raise serializers.ValidationError('Driver has no registered vehicle.')

        preview = FareEngine.fare_preview(
            float(validated_data['origin_lat']),
            float(validated_data['origin_lng']),
            float(validated_data['destination_lat']),
            float(validated_data['destination_lng']),
            vehicle_multiplier=vehicle.price_multiplier,
        )

        validated_data['driver'] = driver
        validated_data['vehicle'] = vehicle
        validated_data['route_fare'] = Decimal(str(preview['shared_fare']))
        validated_data['private_fare'] = Decimal(str(preview['private_fare']))
        template = super().create(validated_data)

        # Create a trip for the next matching day only (today if it qualifies,
        # otherwise the nearest upcoming day that matches the template's schedule).
        # Future days are handled by the daily scheduled task.
        from datetime import date, timedelta
        today = date.today()
        for i in range(7):
            candidate = today + timedelta(days=i)
            day_name = candidate.strftime('%A').lower()
            if getattr(template, day_name, False):
                RecurringTrip.objects.create_instances_for_date(candidate)
                break

        return template
