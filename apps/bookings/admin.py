from django.contrib import admin
from django.utils.html import format_html
from .models import Booking, Rating


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'rider_link', 'trip_route', 'status_badge',
        'seats_booked', 'fare_display', 'payment_method', 'created_at',
    ]
    list_filter = ['status', 'payment_method']
    search_fields = ['rider__full_name', 'rider__phone_number']
    readonly_fields = ['created_at', 'updated_at', 'cancelled_at']
    raw_id_fields = ['trip', 'rider']
    date_hierarchy = 'created_at'

    @admin.display(description='Rider')
    def rider_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:accounts_user_change', args=[obj.rider_id])
        return format_html('<a href="{}">{}</a>', url, obj.rider.full_name)

    @admin.display(description='Trip')
    def trip_route(self, obj):
        return f'{obj.trip.origin_name.split(",")[0]} → {obj.trip.destination_name.split(",")[0]}'

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'pending': '#f57c00', 'confirmed': '#1565c0',
            'completed': '#2e7d32', 'cancelled': '#c62828', 'no_show': '#6b6b6b',
        }
        color = colors.get(obj.status, '#555')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;font-size:10px;'
            'font-weight:700;border-radius:2px;">{}</span>',
            color, obj.status.upper(),
        )

    @admin.display(description='Fare')
    def fare_display(self, obj):
        if obj.fare_final:
            return f'K{obj.fare_final}'
        return f'K{obj.fare_at_booking} (est.)'


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['id', 'rated_by', 'rated_user', 'stars_display', 'comment_short', 'created_at']
    list_filter = ['stars']
    search_fields = ['rated_by__full_name', 'rated_user__full_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['booking', 'rated_by', 'rated_user']

    @admin.display(description='Stars')
    def stars_display(self, obj):
        return '★' * obj.stars + '☆' * (5 - obj.stars)

    @admin.display(description='Comment')
    def comment_short(self, obj):
        return (obj.comment[:50] + '…') if len(obj.comment) > 50 else obj.comment or '—'
