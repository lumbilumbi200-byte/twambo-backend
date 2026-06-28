from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from math import radians, cos, sin, asin, sqrt
from datetime import timedelta
from rest_framework import status
from .models import DriverWallet, WalletTransaction, Commission, OperationalLog, TopUpCode
from .serializers import (
    WalletSerializer, WalletTransactionSerializer,
    CommissionSerializer, OperationalLogSerializer,
)


class IsDriver(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'driver'


class IsApprovedDriver(permissions.BasePermission):
    def has_permission(self, request, view):
        if not (request.user.is_authenticated and request.user.role == 'driver'):
            return False
        try:
            return request.user.driver_profile.is_approved
        except Exception:
            return False


# ── Wallet ────────────────────────────────────────────────────────────────────

class WalletView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [IsDriver]

    def get_object(self):
        wallet, _ = DriverWallet.objects.get_or_create(driver=self.request.user)
        return wallet


class WalletTransactionListView(generics.ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsDriver]

    def get_queryset(self):
        try:
            return self.request.user.wallet.transactions.all()
        except DriverWallet.DoesNotExist:
            return WalletTransaction.objects.none()


class CommissionListView(generics.ListAPIView):
    serializer_class = CommissionSerializer
    permission_classes = [IsDriver]

    def get_queryset(self):
        return Commission.objects.filter(driver=self.request.user)


# ── Operational logs ──────────────────────────────────────────────────────────

class OperationalLogListCreateView(generics.ListCreateAPIView):
    serializer_class = OperationalLogSerializer
    permission_classes = [IsDriver]

    def get_queryset(self):
        return OperationalLog.objects.filter(driver=self.request.user)

    def perform_create(self, serializer):
        serializer.save(driver=self.request.user)


class OperationalLogDeleteView(generics.DestroyAPIView):
    serializer_class = OperationalLogSerializer
    permission_classes = [IsDriver]

    def get_queryset(self):
        return OperationalLog.objects.filter(driver=self.request.user)


# ── Budget suggestion ─────────────────────────────────────────────────────────

def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * R * asin(sqrt(max(0, a)))


class BudgetSuggestionView(APIView):
    permission_classes = [IsDriver]

    def get(self, request):
        period = request.query_params.get('period', 'weekly')
        driver = request.user
        days = 7 if period == 'weekly' else 30
        since = timezone.now() - timedelta(days=days)

        # ── Earnings ─────────────────────────────────────────────────────────
        from apps.bookings.models import Booking
        bookings = Booking.objects.filter(
            trip__driver=driver,
            trip__completed_at__gte=since,
            status=Booking.STATUS_COMPLETED,
        ).select_related('trip')

        earnings = sum(float(b.fare_final or 0) for b in bookings)
        unique_trips = {b.trip for b in bookings}

        if not unique_trips:
            return Response({
                'period': period,
                'has_enough_data': False,
                'earnings': '0.00',
                'estimated_fuel_cost': '0.00',
                'service_fund': '0.00',
                'logged_costs': '0.00',
                'net': '0.00',
                'total_km': '0.0',
                'advice': [],
                'is_dismissed': False,
            })

        # ── Distance estimate ─────────────────────────────────────────────────
        total_km = sum(
            _haversine_km(
                float(t.origin_lat), float(t.origin_lng),
                float(t.destination_lat), float(t.destination_lng),
            )
            for t in unique_trips
        )

        # ── Vehicle / profile data ────────────────────────────────────────────
        try:
            profile = driver.driver_profile
            fuel_price = float(profile.fuel_price_per_litre or 35)
        except Exception:
            fuel_price = 35.0

        try:
            vehicle = driver.vehicle
            consumption = float(vehicle.fuel_consumption_l_per_100km or 10)
            svc_km = vehicle.service_interval_km or 5000
            svc_months = vehicle.service_interval_months or 3
            svc_cost = float(vehicle.estimated_service_cost_zmw or 500)
            last_svc_date = vehicle.last_service_date
        except Exception:
            consumption = 10.0
            svc_km = 5000
            svc_months = 3
            svc_cost = 500.0
            last_svc_date = None

        # ── Calculations ──────────────────────────────────────────────────────
        litres_used = (total_km * consumption) / 100
        fuel_cost = litres_used * fuel_price
        service_fund = (total_km / svc_km) * svc_cost if svc_km > 0 else 0

        op_logs = OperationalLog.objects.filter(
            driver=driver, date__gte=since.date()
        )
        logged_costs = sum(float(log.cost_zmw) for log in op_logs)

        net = earnings - fuel_cost - logged_costs

        # ── Advice lines ──────────────────────────────────────────────────────
        advice = []
        if earnings > 0:
            fuel_pct = (fuel_cost / earnings) * 100
            advice.append(
                f'Estimated fuel spend: K{fuel_cost:.0f} ({fuel_pct:.0f}% of your earnings).'
            )

        if svc_km > 0 and total_km > 0:
            km_until_svc = svc_km - (total_km % svc_km)
            advice.append(
                f'At this pace your next service is due in ~{km_until_svc:.0f} km. '
                f'Consider setting aside K{service_fund:.0f} now.'
            )

        if last_svc_date:
            from datetime import date
            months_since = (date.today().year - last_svc_date.year) * 12 + \
                           (date.today().month - last_svc_date.month)
            if months_since >= svc_months - 1:
                advice.append(
                    f'Your last service was {months_since} month(s) ago '
                    f'(interval: {svc_months} months). Schedule one soon.'
                )

        if logged_costs > 0:
            advice.append(
                f'You logged K{logged_costs:.0f} in operational costs this {period.replace("ly", "")}.'
            )

        if net > 0:
            advice.append(f'Estimated take-home this {period.replace("ly", "")}: K{net:.0f}.')

        # ── Dismissed? ───────────────────────────────────────────────────────
        try:
            from datetime import date
            today = date.today()
            if period == 'weekly':
                week_start = today - timedelta(days=today.weekday())
                dismissed = profile.budget_dismissed_week
                is_dismissed = bool(dismissed and dismissed >= week_start)
            else:
                month_start = today.replace(day=1)
                dismissed = profile.budget_dismissed_month
                is_dismissed = bool(dismissed and dismissed >= month_start)
        except Exception:
            is_dismissed = False

        return Response({
            'period': period,
            'has_enough_data': True,
            'earnings': f'{earnings:.2f}',
            'estimated_fuel_cost': f'{fuel_cost:.2f}',
            'service_fund': f'{service_fund:.2f}',
            'logged_costs': f'{logged_costs:.2f}',
            'net': f'{net:.2f}',
            'total_km': f'{total_km:.1f}',
            'advice': advice,
            'is_dismissed': is_dismissed,
        })


@api_view(['POST'])
@permission_classes([IsDriver])
def wallet_topup(request):
    """
    Manual float top-up — for dev/admin use and future MTN Mobile Money integration.
    Expects: { "amount": 100, "reference": "MTN-TXN-123" }
    """
    try:
        amount = Decimal(str(request.data.get('amount', 0)))
    except Exception:
        return Response({'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)

    if amount <= 0:
        return Response({'detail': 'Amount must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)

    if amount < Decimal('50'):
        return Response({'detail': 'Minimum top-up is K50.'}, status=status.HTTP_400_BAD_REQUEST)

    reference = str(request.data.get('reference', '')).strip()
    wallet, _ = DriverWallet.objects.get_or_create(driver=request.user)
    wallet.top_up(amount, reference=reference, description='Wallet top-up')

    return Response({
        'balance': str(wallet.balance),
        'topped_up': str(amount),
    })


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def generate_topup_code(request):
    """Admin generates a one-time top-up code for a given amount.
    Expects: { "amount": 200, "expires_days": 30 }
    """
    import secrets
    import string
    try:
        amount = Decimal(str(request.data.get('amount', 0)))
    except Exception:
        return Response({'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)
    if amount <= 0:
        return Response({'detail': 'Amount must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)

    expires_days = int(request.data.get('expires_days', 30))
    alphabet = string.ascii_uppercase + string.digits
    raw = ''.join(secrets.choice(alphabet) for _ in range(8))
    code = f'TWMB-{raw[:4]}-{raw[4:]}'

    topup = TopUpCode.objects.create(
        code=code,
        amount=amount,
        generated_by=request.user,
        expires_at=timezone.now() + timedelta(days=expires_days),
    )
    return Response({
        'code': topup.code,
        'amount': str(topup.amount),
        'expires_at': topup.expires_at,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsApprovedDriver])
def redeem_topup_code(request):
    """Driver redeems a top-up code to credit their float.
    Expects: { "code": "TWMB-A3X9-P7QR" }
    """
    code_str = str(request.data.get('code', '')).strip().upper()
    if not code_str:
        return Response({'detail': 'Code is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        topup = TopUpCode.objects.get(code=code_str)
    except TopUpCode.DoesNotExist:
        return Response({'detail': 'Invalid code.'}, status=status.HTTP_404_NOT_FOUND)

    if topup.is_used:
        return Response({'detail': 'This code has already been used.'}, status=status.HTTP_400_BAD_REQUEST)
    if topup.expires_at < timezone.now():
        return Response({'detail': 'This code has expired.'}, status=status.HTTP_400_BAD_REQUEST)

    wallet, _ = DriverWallet.objects.get_or_create(driver=request.user)
    wallet.top_up(topup.amount, reference=topup.code, description=f'Float top-up via code {topup.code}')

    topup.is_used = True
    topup.used_by = request.user
    topup.used_at = timezone.now()
    topup.save(update_fields=['is_used', 'used_by', 'used_at'])

    return Response({
        'credited': str(topup.amount),
        'new_balance': str(wallet.balance),
        'can_go_online': wallet.balance >= wallet.minimum_float,
    })


@api_view(['POST'])
@permission_classes([IsDriver])
def dismiss_budget(request):
    period = request.data.get('period', 'weekly')
    from datetime import date
    today = date.today()
    try:
        profile = request.user.driver_profile
        if period == 'weekly':
            profile.budget_dismissed_week = today
            profile.save(update_fields=['budget_dismissed_week'])
        else:
            profile.budget_dismissed_month = today
            profile.save(update_fields=['budget_dismissed_month'])
    except Exception:
        pass
    return Response({'dismissed': True})
