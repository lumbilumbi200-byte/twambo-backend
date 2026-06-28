from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.accounts.admin import TwamboAdminSite
from apps.dashboard.views import public_slides

# Replace the default admin site with our custom one
admin.site.__class__ = TwamboAdminSite

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('api/v1/slides/', public_slides, name='public_slides'),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/trips/', include('apps.trips.urls')),
    path('api/v1/bookings/', include('apps.bookings.urls')),
    path('api/v1/pricing/', include('apps.pricing.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
