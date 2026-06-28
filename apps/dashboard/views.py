from functools import wraps
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse

from apps.accounts.models import User, DriverProfile, RiderProfile, Strike
from apps.bookings.models import Booking
from apps.trips.models import Trip
from apps.payments.models import Commission, TopUpCode
from .models import MarketingSlide


# ── Auth guard ────────────────────────────────────────────────────────────────

def staff_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect(f'/dashboard/login/?next={request.path}')
        return view_func(request, *args, **kwargs)
    return _wrapped


# ── Login / logout ────────────────────────────────────────────────────────────

def dash_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('dashboard:home')
    error = None
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        password = request.POST.get('password', '')
        # Look up staff user by full name, then authenticate via phone_number
        try:
            staff_user = User.objects.get(full_name__iexact=name, is_staff=True)
            user = authenticate(request, username=staff_user.phone_number, password=password)
        except User.DoesNotExist:
            user = None
        if user and user.is_staff:
            login(request, user)
            return redirect(request.GET.get('next', '/dashboard/'))
        error = 'Invalid name or password.'
    return render(request, 'dashboard/login.html', {'error': error})


def dash_logout(request):
    logout(request)
    return redirect('dashboard:login')


# ── Dashboard home ────────────────────────────────────────────────────────────

@staff_required
def home(request):
    today = timezone.now().date()
    month_start = today.replace(day=1)

    context = {
        'page': 'home',
        'total_riders':        User.objects.filter(role='rider').count(),
        'total_drivers':       User.objects.filter(role='driver').count(),
        'pending_drivers':     DriverProfile.objects.filter(verification_status='pending').count(),
        'banned_users':        User.objects.filter(is_banned=True).count(),
        'users_with_strikes':  User.objects.filter(strike_count__gt=0).count(),
        'trips_today':         Trip.objects.filter(departure_time__date=today).count(),
        'active_trips':        Trip.objects.filter(status='active').count(),
        'bookings_today':      Booking.objects.filter(created_at__date=today).count(),
        'revenue_month': Commission.objects.filter(
            created_at__date__gte=month_start
        ).aggregate(t=Sum('amount'))['t'] or 0,
        'recent_strikes': Strike.objects.select_related('user', 'given_by').order_by('-created_at')[:8],
        'pending_driver_list': DriverProfile.objects.filter(
            verification_status='pending'
        ).select_related('user').order_by('created_at')[:6],
    }
    return render(request, 'dashboard/home.html', context)


# ── Riders ────────────────────────────────────────────────────────────────────

@staff_required
def riders(request):
    qs = User.objects.filter(role='rider').order_by('-created_at')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(phone_number__icontains=q))

    status = request.GET.get('status', '')
    if status == 'banned':
        qs = qs.filter(is_banned=True)
    elif status == 'strikes':
        qs = qs.filter(strike_count__gt=0)
    elif status == 'clean':
        qs = qs.filter(strike_count=0, is_banned=False)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/riders.html', {
        'page': 'riders',
        'page_obj': page_obj,
        'q': q,
        'status': status,
        'strike_reasons': Strike.REASON_CHOICES,
    })


# ── Drivers ───────────────────────────────────────────────────────────────────

@staff_required
def drivers(request):
    qs = User.objects.filter(role='driver').select_related('driver_profile').order_by('created_at')

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(phone_number__icontains=q))

    vstatus = request.GET.get('vstatus', '')
    if vstatus:
        qs = qs.filter(driver_profile__verification_status=vstatus)

    status = request.GET.get('status', '')
    if status == 'banned':
        qs = qs.filter(is_banned=True)
    elif status == 'strikes':
        qs = qs.filter(strike_count__gt=0)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/drivers.html', {
        'page': 'drivers',
        'page_obj': page_obj,
        'q': q,
        'vstatus': vstatus,
        'status': status,
        'strike_reasons': Strike.REASON_CHOICES,
    })


# ── Driver detail / approval ──────────────────────────────────────────────────

@staff_required
def driver_detail(request, pk):
    driver = get_object_or_404(User, pk=pk, role='driver')
    try:
        profile = driver.driver_profile
    except Exception:
        profile = None
    strikes = driver.strikes.order_by('-created_at')
    trips = Trip.objects.filter(driver=driver).order_by('-departure_time')[:10]
    return render(request, 'dashboard/driver_detail.html', {
        'page': 'drivers',
        'driver': driver,
        'profile': profile,
        'strikes': strikes,
        'trips': trips,
        'strike_reasons': Strike.REASON_CHOICES,
    })


@staff_required
@require_POST
def driver_approve(request, pk):
    profile = get_object_or_404(DriverProfile, user_id=pk)
    profile.verification_status = DriverProfile.STATUS_APPROVED
    profile.rejection_reason = ''
    profile.approved_at = timezone.now()
    profile.save(update_fields=['verification_status', 'rejection_reason', 'approved_at'])
    messages.success(request, f'{profile.user.full_name} approved as driver.')
    return redirect(request.POST.get('next', 'dashboard:drivers'))


@staff_required
@require_POST
def driver_reject(request, pk):
    profile = get_object_or_404(DriverProfile, user_id=pk)
    reason = request.POST.get('reason', '').strip()
    profile.verification_status = DriverProfile.STATUS_REJECTED
    profile.rejection_reason = reason
    profile.approved_at = None
    profile.save(update_fields=['verification_status', 'rejection_reason', 'approved_at'])
    messages.warning(request, f'{profile.user.full_name} rejected.')
    return redirect(request.POST.get('next', 'dashboard:drivers'))


@staff_required
@require_POST
def driver_toggle_approval(request, pk):
    """Quick approve / revoke from the drivers list without going to detail page."""
    profile = get_object_or_404(DriverProfile, user_id=pk)
    if profile.verification_status == DriverProfile.STATUS_APPROVED:
        profile.verification_status = DriverProfile.STATUS_PENDING
        profile.approved_at = None
        profile.is_online = False
        profile.save(update_fields=['verification_status', 'approved_at', 'is_online'])
        messages.warning(request, f'{profile.user.full_name} approval revoked — taken offline.')
    else:
        profile.verification_status = DriverProfile.STATUS_APPROVED
        profile.rejection_reason = ''
        profile.approved_at = timezone.now()
        profile.save(update_fields=['verification_status', 'rejection_reason', 'approved_at'])
        messages.success(request, f'{profile.user.full_name} approved to operate.')
    return redirect(request.POST.get('next', 'dashboard:drivers'))


# ── Rider detail ──────────────────────────────────────────────────────────────

@staff_required
def rider_detail(request, pk):
    rider = get_object_or_404(User, pk=pk, role='rider')
    strikes = rider.strikes.order_by('-created_at')
    bookings = Booking.objects.filter(rider=rider).select_related('trip').order_by('-created_at')[:10]
    return render(request, 'dashboard/rider_detail.html', {
        'page': 'riders',
        'rider': rider,
        'strikes': strikes,
        'bookings': bookings,
        'strike_reasons': Strike.REASON_CHOICES,
    })


# ── Strike actions (shared for riders + drivers) ──────────────────────────────

@staff_required
@require_POST
def give_strike(request, pk):
    user = get_object_or_404(User, pk=pk)
    reason = request.POST.get('reason', 'other')
    notes = request.POST.get('notes', '').strip()
    user.give_strike(reason=reason, notes=notes, given_by=request.user)
    suffix = '  — USER BANNED.' if user.is_banned else ''
    msg = f'Strike added for {user.full_name}. Total: {user.strike_count}/5.{suffix}'
    if user.is_banned:
        messages.error(request, msg)
    else:
        messages.warning(request, msg)
    return redirect(request.POST.get('next', 'dashboard:home'))


@staff_required
@require_POST
def remove_strike(request, strike_pk):
    strike = get_object_or_404(Strike, pk=strike_pk)
    user = strike.user
    user.remove_strike(strike_pk)
    messages.success(request, f'Strike removed from {user.full_name}.')
    return redirect(request.POST.get('next', 'dashboard:home'))


@staff_required
@require_POST
def ban_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.is_banned = True
    user.save(update_fields=['is_banned', 'updated_at'])
    messages.error(request, f'{user.full_name} has been banned.')
    return redirect(request.POST.get('next', 'dashboard:home'))


@staff_required
@require_POST
def unban_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.is_banned = False
    user.save(update_fields=['is_banned', 'updated_at'])
    messages.success(request, f'{user.full_name} has been unbanned.')
    return redirect(request.POST.get('next', 'dashboard:home'))


# ── Strikes log ───────────────────────────────────────────────────────────────

@staff_required
def strikes_log(request):
    qs = Strike.objects.select_related('user', 'given_by').order_by('-created_at')

    reason_filter = request.GET.get('reason', '')
    if reason_filter:
        qs = qs.filter(reason=reason_filter)

    kind = request.GET.get('kind', '')
    if kind == 'auto':
        qs = qs.filter(auto_generated=True)
    elif kind == 'manual':
        qs = qs.filter(auto_generated=False)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(user__full_name__icontains=q) | Q(user__phone_number__icontains=q))

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/strikes.html', {
        'page': 'strikes',
        'page_obj': page_obj,
        'reason_filter': reason_filter,
        'kind': kind,
        'q': q,
        'strike_reasons': Strike.REASON_CHOICES,
    })


# ── Trips ─────────────────────────────────────────────────────────────────────

@staff_required
def trips(request):
    qs = Trip.objects.select_related('driver').order_by('-departure_time')

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(driver__full_name__icontains=q) |
            Q(origin_name__icontains=q) |
            Q(destination_name__icontains=q)
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/trips.html', {
        'page': 'trips',
        'page_obj': page_obj,
        'status_filter': status_filter,
        'q': q,
    })


# ── Earnings / Commission ─────────────────────────────────────────────────────

@staff_required
def earnings(request):
    today = timezone.now().date()
    month_start = today.replace(day=1)
    week_start = today - timezone.timedelta(days=today.weekday())

    total_all   = Commission.objects.aggregate(t=Sum('amount'))['t'] or 0
    total_month = Commission.objects.filter(created_at__date__gte=month_start).aggregate(t=Sum('amount'))['t'] or 0
    total_week  = Commission.objects.filter(created_at__date__gte=week_start).aggregate(t=Sum('amount'))['t'] or 0
    total_today = Commission.objects.filter(created_at__date=today).aggregate(t=Sum('amount'))['t'] or 0

    # Last 6 months labels + amounts for chart
    months, month_amounts = [], []
    for i in range(5, -1, -1):
        ref = today.replace(day=1) - timezone.timedelta(days=1) * (i * 28)
        ref = ref.replace(day=1)
        label = ref.strftime('%b %Y')
        amt = Commission.objects.filter(
            created_at__year=ref.year,
            created_at__month=ref.month,
        ).aggregate(t=Sum('amount'))['t'] or 0
        months.append(label)
        month_amounts.append(float(amt))

    top_drivers = (
        Commission.objects
        .values('driver__pk', 'driver__full_name', 'driver__phone_number')
        .annotate(total=Sum('amount'), trips=Count('id'))
        .order_by('-total')[:10]
    )

    recent = Commission.objects.select_related('driver', 'trip').order_by('-created_at')[:20]

    return render(request, 'dashboard/earnings.html', {
        'page': 'earnings',
        'total_all': total_all,
        'total_month': total_month,
        'total_week': total_week,
        'total_today': total_today,
        'chart_labels': months,
        'chart_data': month_amounts,
        'top_drivers': top_drivers,
        'recent': recent,
    })


# ── Marketing Slides ──────────────────────────────────────────────────────────

@staff_required
def slides(request):
    slide_list = MarketingSlide.objects.all()
    return render(request, 'dashboard/slides.html', {
        'page': 'slides',
        'slides': slide_list,
        'icon_choices': MarketingSlide.ICON_CHOICES,
    })


@staff_required
def slide_new(request):
    if request.method == 'POST':
        _slide_save(request, None)
        messages.success(request, 'Slide created.')
        return redirect('dashboard:slides')
    return render(request, 'dashboard/slide_form.html', {
        'page': 'slides',
        'slide': None,
        'icon_choices': MarketingSlide.ICON_CHOICES,
    })


@staff_required
def slide_edit(request, pk):
    slide = get_object_or_404(MarketingSlide, pk=pk)
    if request.method == 'POST':
        _slide_save(request, slide)
        messages.success(request, 'Slide updated.')
        return redirect('dashboard:slides')
    return render(request, 'dashboard/slide_form.html', {
        'page': 'slides',
        'slide': slide,
        'icon_choices': MarketingSlide.ICON_CHOICES,
    })


@staff_required
@require_POST
def slide_delete(request, pk):
    get_object_or_404(MarketingSlide, pk=pk).delete()
    messages.success(request, 'Slide deleted.')
    return redirect('dashboard:slides')


@staff_required
@require_POST
def slide_toggle(request, pk):
    slide = get_object_or_404(MarketingSlide, pk=pk)
    slide.is_active = not slide.is_active
    slide.save(update_fields=['is_active'])
    return redirect('dashboard:slides')


def _slide_save(request, slide):
    data = {
        'label':       request.POST.get('label', '').strip(),
        'tagline':     request.POST.get('tagline', '').strip(),
        'icon_key':    request.POST.get('icon_key', 'car'),
        'bg_color':    request.POST.get('bg_color', '#FFC300'),
        'text_color':  request.POST.get('text_color', '#1A1A1A'),
        'accent_color':request.POST.get('accent_color', '#E6A800'),
        'order':       int(request.POST.get('order', 0) or 0),
        'is_active':   request.POST.get('is_active') == 'on',
    }
    if slide:
        for k, v in data.items():
            setattr(slide, k, v)
        slide.save()
    else:
        MarketingSlide.objects.create(**data)


# ── Float codes ──────────────────────────────────────────────────────────────

@staff_required
def float_codes(request):
    generated_code = None
    error = None

    if request.method == 'POST':
        import secrets, string
        from decimal import Decimal, InvalidOperation
        from datetime import timedelta

        try:
            amount = Decimal(str(request.POST.get('amount', '0')).strip())
            if amount <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            error = 'Enter a valid amount greater than zero.'
        else:
            expires_days = int(request.POST.get('expires_days', '30') or '30')
            alphabet = string.ascii_uppercase + string.digits
            raw = ''.join(secrets.choice(alphabet) for _ in range(8))
            code_str = f'TWMB-{raw[:4]}-{raw[4:]}'
            TopUpCode.objects.create(
                code=code_str,
                amount=amount,
                generated_by=request.user,
                expires_at=timezone.now() + timedelta(days=expires_days),
            )
            generated_code = {'code': code_str, 'amount': amount, 'expires_days': expires_days}

    codes = TopUpCode.objects.select_related('generated_by', 'used_by').order_by('-created_at')
    paginator = Paginator(codes, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/float_codes.html', {
        'page': 'float_codes',
        'page_obj': page_obj,
        'generated_code': generated_code,
        'error': error,
        'now': timezone.now(),
    })


# ── Public API: active slides for Flutter ────────────────────────────────────

def public_slides(request):
    qs = MarketingSlide.objects.filter(is_active=True).values(
        'label', 'tagline', 'icon_key', 'bg_color', 'text_color', 'accent_color', 'order'
    )
    return JsonResponse({'slides': list(qs)})
