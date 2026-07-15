from django.contrib import admin
from django.utils.html import format_html
from .models import Trip, RecurringTrip, RideRequest, SeatRelease


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'driver_link', 'route_display', 'departure_time',
        'status_badge', 'mode', 'seats_display', 'created_at',
    ]
    list_per_page = 20
    list_filter = ['status', 'mode', 'booking_window_open']
    search_fields = ['driver__full_name', 'driver__phone_number', 'origin_name', 'destination_name']
    readonly_fields = ['started_at', 'completed_at', 'created_at', 'updated_at', 'seats_taken']
    raw_id_fields = ['driver', 'vehicle', 'recurring_template']
    date_hierarchy = 'departure_time'

    @admin.display(description='Driver')
    def driver_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:accounts_user_change', args=[obj.driver_id])
        return format_html('<a href="{}">{}</a>', url, obj.driver.full_name)

    @admin.display(description='Route')
    def route_display(self, obj):
        return f'{obj.origin_name.split(",")[0]} → {obj.destination_name.split(",")[0]}'

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'scheduled': '#1565c0', 'active': '#2e7d32',
            'completed': '#555', 'cancelled': '#c62828',
        }
        color = colors.get(obj.status, '#555')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;font-size:10px;'
            'font-weight:700;border-radius:2px;">{}</span>',
            color, obj.status.upper(),
        )

    @admin.display(description='Seats')
    def seats_display(self, obj):
        taken = obj.total_seats - obj.available_seats
        return f'{taken}/{obj.total_seats}'


@admin.register(RecurringTrip)
class RecurringTripAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'driver', 'origin_name', 'destination_name',
        'departure_time', 'is_active',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    ]
    list_filter = ['is_active']
    search_fields = ['driver__full_name', 'origin_name', 'destination_name']
    raw_id_fields = ['driver', 'vehicle']


@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'rider', 'origin_name', 'destination_name', 'mode', 'fare_estimate', 'status', 'created_at']
    list_filter = ['status', 'mode']
    search_fields = ['rider__full_name', 'rider__phone_number']
    readonly_fields = ['created_at', 'updated_at', 'expires_at']
    raw_id_fields = ['rider', 'accepted_trip']


@admin.register(SeatRelease)
class SeatReleaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'trip', 'city_name', 'city_id', 'seats', 'status', 'announced_at']
    list_filter = ['status', 'city_id']
    search_fields = ['city_name', 'trip__origin_name', 'trip__destination_name']
    readonly_fields = ['announced_at']
    raw_id_fields = ['trip']
