from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/trips/(?P<trip_id>[^/]+)/$', consumers.TripConsumer.as_asgi()),
    re_path(r'ws/driver/(?P<driver_id>[^/]+)/$', consumers.DriverLocationConsumer.as_asgi()),
]
