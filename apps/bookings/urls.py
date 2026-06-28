from django.urls import path
from . import views

urlpatterns = [
    # Rider
    path('', views.RiderBookingCreateView.as_view(), name='booking-create'),
    path('my/', views.RiderBookingListView.as_view(), name='rider-booking-list'),
    path('my/<int:pk>/', views.RiderBookingDetailView.as_view(), name='rider-booking-detail'),
    path('my/<int:pk>/cancel/', views.rider_cancel_booking, name='rider-booking-cancel'),

    # Driver
    path('trip/<int:trip_id>/', views.DriverTripBookingsView.as_view(), name='driver-trip-bookings'),
    path('trip/<int:trip_id>/passengers/', views.TripPassengersView.as_view(), name='trip-passengers'),
    path('<int:pk>/pickup/', views.driver_mark_picked_up, name='driver-mark-picked-up'),
    path('<int:pk>/no-show/', views.driver_mark_no_show, name='driver-mark-no-show'),

    # Ratings
    path('<int:pk>/rate/', views.submit_rating, name='booking-rate'),
    path('<int:pk>/my-rating/', views.my_rating_for_booking, name='booking-my-rating'),
]
