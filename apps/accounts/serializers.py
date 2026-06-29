from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Vehicle, DriverProfile, RiderProfile, SavedPlace


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['phone_number', 'full_name', 'email', 'role', 'password']

    def create(self, validated_data):
        from django.conf import settings
        user = User.objects.create_user(**validated_data)
        if user.is_driver:
            # Auto-approve in DEBUG so dev accounts can go online immediately
            status = 'approved' if settings.DEBUG else 'pending'
            DriverProfile.objects.create(user=user, verification_status=status)
        else:
            RiderProfile.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['phone_number'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid credentials')
        if not user.is_active:
            raise serializers.ValidationError('Account is inactive')
        if user.is_banned:
            from django.utils import timezone
            if user.ban_until and user.ban_until > timezone.now():
                raise serializers.ValidationError(f'Account banned until {user.ban_until}')
        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    driver_verification_status = serializers.SerializerMethodField()
    fare_surcharge_pct = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'phone_number', 'full_name', 'email', 'role',
                  'profile_photo', 'is_verified', 'is_banned', 'strike_count',
                  'fare_surcharge_pct', 'driver_verification_status', 'created_at']
        read_only_fields = ['id', 'is_verified', 'is_banned', 'strike_count',
                            'fare_surcharge_pct', 'created_at']

    def get_driver_verification_status(self, obj):
        if obj.role != 'driver':
            return None
        try:
            return obj.driver_profile.verification_status
        except Exception:
            return 'pending'


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            'id', 'vehicle_type', 'make', 'model', 'color',
            'plate_number', 'total_seats', 'year',
            'photo_front', 'photo_back', 'photo_interior',
            # financial / maintenance
            'fuel_type', 'fuel_consumption_l_per_100km',
            'last_service_date', 'last_service_odometer_km',
            'service_interval_km', 'service_interval_months',
            'estimated_service_cost_zmw', 'admin_notes',
        ]
        read_only_fields = ['id', 'admin_notes']

    def validate_total_seats(self, value):
        vehicle_type = self.initial_data.get('vehicle_type')
        max_seats = Vehicle.PRICE_MULTIPLIERS  # just checking field exists
        limits = {Vehicle.TYPE_SEDAN: 4, Vehicle.TYPE_SUV: 6, Vehicle.TYPE_MINIBUS: 14}
        if vehicle_type in limits and value > limits[vehicle_type]:
            raise serializers.ValidationError(
                f'Max seats for {vehicle_type} is {limits[vehicle_type]}'
            )
        return value


class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    vehicle = VehicleSerializer(read_only=True)

    class Meta:
        model = DriverProfile
        fields = [
            'user', 'vehicle', 'national_id', 'drivers_license',
            'vehicle_registration', 'verification_status',
            'is_online', 'rating', 'total_trips',
            'fuel_price_per_litre', 'vehicle_notes',
            'budget_dismissed_week', 'budget_dismissed_month',
        ]
        read_only_fields = ['verification_status', 'is_online', 'rating', 'total_trips']


class DriverFinancePrefsSerializer(serializers.ModelSerializer):
    """Driver updates their fuel price and personal vehicle notes."""
    class Meta:
        model = DriverProfile
        fields = ['fuel_price_per_litre', 'vehicle_notes']


class DriverDocumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverProfile
        fields = ['national_id', 'drivers_license', 'vehicle_registration',
                  'fitness_certificate', 'insurance_certificate', 'plate_photo']


class RiderProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = RiderProfile
        fields = ['user', 'rating', 'total_rides',
                  'emergency_contact_name', 'emergency_contact_phone']
        read_only_fields = ['rating', 'total_rides']


class SavedPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedPlace
        fields = ['id', 'label', 'name', 'address', 'latitude', 'longitude']
        read_only_fields = ['id']


class FCMTokenSerializer(serializers.Serializer):
    fcm_token = serializers.CharField()
