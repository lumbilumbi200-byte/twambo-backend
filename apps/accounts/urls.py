from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.MeView.as_view(), name='me'),
    path('fcm-token/', views.update_fcm_token, name='fcm_token'),
    path('verify-phone/', views.verify_phone, name='verify_phone'),

    # Driver
    path('driver/profile/', views.DriverProfileView.as_view(), name='driver_profile'),
    path('driver/documents/', views.DriverDocumentsView.as_view(), name='driver_documents'),
    path('driver/online/', views.DriverOnlineToggleView.as_view(), name='driver_online_toggle'),
    path('driver/vehicle/', views.VehicleView.as_view(), name='driver_vehicle'),
    path('driver/finance-prefs/', views.DriverFinancePrefsView.as_view(), name='driver_finance_prefs'),

    # Rider
    path('rider/profile/', views.RiderProfileView.as_view(), name='rider_profile'),
    path('rider/saved-places/', views.SavedPlaceListCreateView.as_view(), name='saved_places'),
    path('rider/saved-places/<int:pk>/', views.SavedPlaceDetailView.as_view(), name='saved_place_detail'),
]
