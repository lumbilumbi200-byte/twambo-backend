from django.conf import settings
from decimal import Decimal


class FareEngine:
    ZONE_RATES = settings.TWAMBO_ZONE_RATES
    ZONE_BOUNDARIES_KM = settings.TWAMBO_ZONE_BOUNDARIES_KM
    PRIVATE_MULTIPLIER = settings.TWAMBO_PRIVATE_MULTIPLIER
    DETOUR_RATE = settings.TWAMBO_DETOUR_RATE_PER_KM
    DETOUR_MAX_FEE_CITY = settings.TWAMBO_DETOUR_MAX_FEE_CITY
    DETOUR_MAX_FEE_HIKE = settings.TWAMBO_DETOUR_MAX_FEE_HIKE
    MIN_FARE = settings.TWAMBO_MIN_FARE
    MIN_PRIVATE_FARE = settings.TWAMBO_MIN_PRIVATE_FARE

    @classmethod
    def _surge_multiplier(cls):
        from django.utils import timezone
        hour = timezone.localtime().hour
        start = getattr(settings, 'TWAMBO_SURGE_START_HOUR', 19)
        end = getattr(settings, 'TWAMBO_SURGE_END_HOUR', 22)
        mult = getattr(settings, 'TWAMBO_SURGE_MULTIPLIER', 1.0)
        return Decimal(str(mult)) if start <= hour < end else Decimal('1')

    @classmethod
    def calculate_fare(cls, pickup_lat, pickup_lng, dropoff_lat, dropoff_lng,
                       vehicle_multiplier=1.0, is_private=False, detour_km=0.0):
        distance_km = cls._haversine_km(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        base_fare = cls._tiered_fare(distance_km)
        detour_fee = Decimal(str(detour_km)) * Decimal(str(cls.DETOUR_RATE))
        fare = (base_fare + detour_fee) * Decimal(str(vehicle_multiplier)) * cls._surge_multiplier()

        if is_private:
            fare = fare * Decimal(str(cls.PRIVATE_MULTIPLIER))
            return max(fare, Decimal(str(cls.MIN_PRIVATE_FARE))).quantize(Decimal('0.01'))

        return max(fare, Decimal(str(cls.MIN_FARE))).quantize(Decimal('0.01'))

    @classmethod
    def _tiered_fare(cls, distance_km):
        boundaries = cls.ZONE_BOUNDARIES_KM
        rates = cls.ZONE_RATES
        fare = Decimal('0')
        remaining = Decimal(str(distance_km))

        # local: 0-5km at K5/km
        local_limit = Decimal(str(boundaries['local']))
        if remaining > 0:
            local_km = min(remaining, local_limit)
            fare += local_km * Decimal(str(rates['local']))
            remaining -= local_km

        # city: 5-15km at K2.50/km
        city_limit = Decimal(str(boundaries['city'] - boundaries['local']))
        if remaining > 0:
            city_km = min(remaining, city_limit)
            fare += city_km * Decimal(str(rates['city']))
            remaining -= city_km

        # intercity: 15-50km at K0.80/km
        intercity_limit = Decimal(str(boundaries['intercity'] - boundaries['city']))
        if remaining > 0:
            intercity_km = min(remaining, intercity_limit)
            fare += intercity_km * Decimal(str(rates['intercity']))
            remaining -= intercity_km

        # longhaul: 50km+ at K0.60/km
        if remaining > 0:
            fare += remaining * Decimal(str(rates['longhaul']))

        return fare

    @classmethod
    def calculate_detour_km(cls, driver_pickup_lat, driver_pickup_lng,
                             rider_lat, rider_lng, pickup_radius_km):
        distance_to_rider = cls._haversine_km(
            driver_pickup_lat, driver_pickup_lng, rider_lat, rider_lng
        )
        if distance_to_rider <= pickup_radius_km:
            return 0.0
        return round(distance_to_rider - pickup_radius_km, 3)

    @classmethod
    def calculate_detour_fee(cls, detour_km, trip_type='city'):
        """Return the detour fee in ZMW, capped by trip type."""
        cap = cls.DETOUR_MAX_FEE_HIKE if trip_type == 'hike' else cls.DETOUR_MAX_FEE_CITY
        return min(round(detour_km * cls.DETOUR_RATE, 2), cap)

    @staticmethod
    def _haversine_km(lat1, lng1, lat2, lng2):
        import math
        R = 6371
        dlat = math.radians(float(lat2) - float(lat1))
        dlng = math.radians(float(lng2) - float(lng1))
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(float(lat1))) *
             math.cos(math.radians(float(lat2))) *
             math.sin(dlng / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    @classmethod
    def fare_preview(cls, pickup_lat, pickup_lng, dropoff_lat, dropoff_lng,
                     vehicle_multiplier=1.0, detour_km=0.0, total_seats=4,
                     trip_type='city'):
        distance_km = cls._haversine_km(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        shared_fare = cls.calculate_fare(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng,
            vehicle_multiplier=vehicle_multiplier,
            is_private=False,
            detour_km=detour_km,
        )
        private_fare = cls.calculate_fare(
            pickup_lat, pickup_lng, dropoff_lat, dropoff_lng,
            vehicle_multiplier=vehicle_multiplier,
            is_private=True,
            detour_km=detour_km,
        )
        detour_fee = cls.calculate_detour_fee(detour_km, trip_type)
        return {
            'distance_km': round(distance_km, 2),
            'shared_fare': float(shared_fare),
            'private_fare': float(private_fare),
            'detour_km': detour_km,
            'detour_fee': detour_fee,
        }
