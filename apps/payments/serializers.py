from rest_framework import serializers
from .models import DriverWallet, WalletTransaction, Commission, OperationalLog


class WalletSerializer(serializers.ModelSerializer):
    can_accept_rides = serializers.BooleanField(read_only=True)

    class Meta:
        model = DriverWallet
        fields = ['id', 'balance', 'minimum_float', 'can_accept_rides', 'updated_at']


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = ['id', 'transaction_type', 'amount', 'description', 'reference', 'created_at']


class CommissionSerializer(serializers.ModelSerializer):
    trip_origin = serializers.CharField(source='trip.origin_name', read_only=True)
    trip_destination = serializers.CharField(source='trip.destination_name', read_only=True)

    class Meta:
        model = Commission
        fields = [
            'id', 'trip_id', 'trip_origin', 'trip_destination',
            'trip_revenue', 'rate', 'amount', 'status', 'deducted_at', 'created_at',
        ]


class OperationalLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalLog
        fields = ['id', 'log_type', 'description', 'cost_zmw', 'date', 'created_at']
        read_only_fields = ['id', 'created_at']
