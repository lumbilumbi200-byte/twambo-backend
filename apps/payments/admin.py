from django.contrib import admin
from .models import DriverWallet, WalletTransaction, Commission


@admin.register(DriverWallet)
class DriverWalletAdmin(admin.ModelAdmin):
    list_display = ['driver', 'balance', 'minimum_float', 'can_accept_rides', 'updated_at']
    search_fields = ['driver__full_name', 'driver__phone_number']
    readonly_fields = ['updated_at']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'transaction_type', 'amount', 'description', 'created_at']
    list_filter = ['transaction_type']
    readonly_fields = ['created_at']


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ['driver', 'trip', 'trip_revenue', 'rate', 'amount', 'status', 'deducted_at']
    list_filter = ['status']
    readonly_fields = ['created_at', 'deducted_at']
    raw_id_fields = ['driver', 'trip']
