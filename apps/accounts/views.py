from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Vehicle, DriverProfile, RiderProfile, SavedPlace
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    VehicleSerializer, DriverProfileSerializer, DriverDocumentsSerializer,
    DriverFinancePrefsSerializer, RiderProfileSerializer, SavedPlaceSerializer, FCMTokenSerializer,
)


def get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = get_tokens(user)
        return Response(
            {'user': UserSerializer(user).data, 'access': tokens['access'], 'refresh': tokens['refresh']},
            status=status.HTTP_201_CREATED
        )


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        tokens = get_tokens(user)
        return Response({'user': UserSerializer(user).data, 'access': tokens['access'], 'refresh': tokens['refresh']})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class DriverProfileView(generics.RetrieveAPIView):
    serializer_class = DriverProfileSerializer

    def get_object(self):
        return self.request.user.driver_profile


class DriverDocumentsView(generics.UpdateAPIView):
    serializer_class = DriverDocumentsSerializer

    def get_object(self):
        return self.request.user.driver_profile

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.verification_status = instance.STATUS_PENDING
        instance.save(update_fields=['verification_status', 'updated_at'])


class DriverOnlineToggleView(generics.GenericAPIView):
    def post(self, request):
        profile = request.user.driver_profile
        if not profile.is_approved:
            return Response({'detail': 'Account not approved yet.'}, status=status.HTTP_403_FORBIDDEN)
        sent = request.data.get('is_online')
        going_online = bool(sent) if sent is not None else (not profile.is_online)
        if going_online:
            from apps.payments.models import DriverWallet
            from decimal import Decimal
            wallet, _ = DriverWallet.objects.get_or_create(driver=request.user)
            if wallet.balance < wallet.minimum_float:
                return Response(
                    {'detail': f'Float too low. You need at least K{wallet.minimum_float} to go online. Current balance: K{wallet.balance}.'},
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
        profile.is_online = going_online
        profile.save(update_fields=['is_online'])
        return Response({'is_online': profile.is_online})


class DriverFinancePrefsView(generics.RetrieveUpdateAPIView):
    """Driver updates their fuel price per litre and personal vehicle notes."""
    serializer_class = DriverFinancePrefsSerializer

    def get_object(self):
        return self.request.user.driver_profile


class VehicleView(generics.RetrieveUpdateAPIView):
    serializer_class = VehicleSerializer

    def get_object(self):
        vehicle, _ = Vehicle.objects.get_or_create(
            driver=self.request.user,
            defaults={
                'vehicle_type': 'sedan', 'total_seats': 4, 'year': 2020,
                'make': 'Unknown', 'model': 'Unknown', 'color': 'Unknown',
                'plate_number': f'PENDING-{self.request.user.pk}',
            },
        )
        return vehicle


class RiderProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = RiderProfileSerializer

    def get_object(self):
        return self.request.user.rider_profile


class SavedPlaceListCreateView(generics.ListCreateAPIView):
    serializer_class = SavedPlaceSerializer

    def get_queryset(self):
        return SavedPlace.objects.filter(rider=self.request.user)

    def perform_create(self, serializer):
        serializer.save(rider=self.request.user)


class SavedPlaceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SavedPlaceSerializer

    def get_queryset(self):
        return SavedPlace.objects.filter(rider=self.request.user)


@api_view(['POST'])
def update_fcm_token(request):
    serializer = FCMTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    request.user.fcm_token = serializer.validated_data['fcm_token']
    request.user.save(update_fields=['fcm_token'])
    return Response({'detail': 'FCM token updated'})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def verify_phone(request):
    id_token = request.data.get('id_token')
    if not id_token:
        return Response({'detail': 'id_token required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        import firebase_admin.auth as fb_auth
        fb_auth.verify_id_token(id_token)
        request.user.is_verified = True
        request.user.save(update_fields=['is_verified', 'updated_at'])
        return Response({'verified': True})
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def forgot_password(request):
    """Check that a user with this phone exists before triggering OTP on the client."""
    phone = request.data.get('phone_number', '').strip()
    if not phone:
        return Response({'detail': 'phone_number required.'}, status=status.HTTP_400_BAD_REQUEST)
    exists = User.objects.filter(phone_number=phone).exists()
    if not exists:
        return Response({'detail': 'No account found with this number.'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'detail': 'ok'})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def reset_password(request):
    """
    Verify Firebase OTP id_token (proves ownership of phone),
    then update the password for that phone number.
    """
    phone    = request.data.get('phone_number', '').strip()
    id_token = request.data.get('id_token', '').strip()
    new_pass = request.data.get('new_password', '')

    if not phone or not id_token or not new_pass:
        return Response({'detail': 'phone_number, id_token and new_password are required.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if len(new_pass) < 6:
        return Response({'detail': 'Password must be at least 6 characters.'},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        import firebase_admin.auth as fb_auth
        fb_auth.verify_id_token(id_token)
    except Exception as e:
        return Response({'detail': f'OTP verification failed: {e}'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(phone_number=phone)
    except User.DoesNotExist:
        return Response({'detail': 'No account found with this number.'}, status=status.HTTP_404_NOT_FOUND)

    user.set_password(new_pass)
    user.save(update_fields=['password'])
    return Response({'detail': 'Password reset successful.'})
