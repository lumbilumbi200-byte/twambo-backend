from django.urls import path
from . import views

urlpatterns = [
    # Driver — trip CRUD
    path('driver/create/', views.DriverTripCreateView.as_view(), name='driver-trip-create'),
    path('driver/', views.DriverTripListView.as_view(), name='driver-trip-list'),
    path('driver/<int:pk>/', views.DriverTripDetailView.as_view(), name='driver-trip-detail'),

    # Driver — FSM actions
    path('driver/<int:pk>/start/', views.trip_start, name='trip-start'),
    path('driver/<int:pk>/complete/', views.trip_complete, name='trip-complete'),
    path('driver/<int:pk>/cancel/', views.trip_cancel, name='trip-cancel'),
    path('driver/<int:pk>/requests/', views.DriverTripRideRequestsView.as_view(), name='driver-trip-requests'),
    path('driver/<int:pk>/close-window/', views.close_booking_window, name='trip-close-window'),
    path('driver/<int:pk>/announce-dropoff/', views.announce_dropoff, name='trip-announce-dropoff'),
    path('driver/<int:pk>/requests/<int:request_pk>/accept/', views.accept_ride_request, name='ride-request-accept'),
    path('driver/<int:pk>/requests/<int:request_pk>/reject/', views.reject_ride_request, name='ride-request-reject'),

    # Driver — recurring templates
    path('driver/recurring/', views.RecurringTripListCreateView.as_view(), name='recurring-list-create'),
    path('driver/recurring/<int:pk>/', views.RecurringTripDetailView.as_view(), name='recurring-detail'),

    # Rider / public
    path('search/', views.TripSearchView.as_view(), name='trip-search'),
    path('<int:pk>/', views.TripDetailPublicView.as_view(), name='trip-detail'),

    # Driver: broadcast inbox
    path('driver/broadcast-requests/', views.DriverBroadcastInboxView.as_view(), name='driver-broadcast-inbox'),
    path('driver/broadcast-requests/<int:pk>/accept/', views.accept_broadcast_request, name='broadcast-accept'),
    path('driver/broadcast-requests/<int:pk>/decline/', views.decline_broadcast_request, name='broadcast-decline'),

    # Rider: EN ROUTE join request for a specific trip
    path('<int:pk>/join-request/', views.request_join_trip, name='trip-join-request'),

    # Rider: ride request broadcasts
    path('ride-requests/', views.RideRequestListCreateView.as_view(), name='ride-request-list-create'),
    path('ride-requests/<int:pk>/cancel/', views.cancel_ride_request, name='ride-request-cancel'),
]
