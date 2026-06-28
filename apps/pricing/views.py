from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import serializers
from .engine import FareEngine


class FareCalculateSerializer(serializers.Serializer):
    pickup_lat = serializers.FloatField()
    pickup_lng = serializers.FloatField()
    dropoff_lat = serializers.FloatField()
    dropoff_lng = serializers.FloatField()
    vehicle_type = serializers.ChoiceField(choices=['sedan', 'suv', 'minibus'], default='sedan')
    detour_km = serializers.FloatField(default=0.0)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_fare(request):
    serializer = FareCalculateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data

    multipliers = {'sedan': 1.0, 'suv': 1.1, 'minibus': 0.85}
    vehicle_multiplier = multipliers.get(d['vehicle_type'], 1.0)

    preview = FareEngine.fare_preview(
        pickup_lat=d['pickup_lat'],
        pickup_lng=d['pickup_lng'],
        dropoff_lat=d['dropoff_lat'],
        dropoff_lng=d['dropoff_lng'],
        vehicle_multiplier=vehicle_multiplier,
        detour_km=d['detour_km'],
    )
    return Response(preview)
