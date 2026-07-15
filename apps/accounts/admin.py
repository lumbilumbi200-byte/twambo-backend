from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.contrib import messages
from django.template.response import TemplateResponse
from .models import User, Vehicle, DriverProfile, RiderProfile, SavedPlace, Strike, AppVersion


# ── Helpers ───────────────────────────────────────────────────────────────────

def _doc_img(field, label):
    if not field:
        return '—'
    return format_html(
        '<a href="{url}" target="_blank">'
        '<img src="{url}" style="max-height:120px;max-width:200px;border:1px solid #ddd;padding:2px;">'
        '<br><small>{label}</small></a>',
        url=field.url, label=label,
    )


def _strike_dots(count):
    dots = ''.join(
        f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
        f'background:{"#c62828" if i < count else "#e0e0e0"};margin:1px;"></span>'
        for i in range(5)
    )
    return format_html(dots)


# ── Strike inline ─────────────────────────────────────────────────────────────

class StrikeInline(admin.TabularInline):
    model = Strike
    fk_name = 'user'
    extra = 0
    readonly_fields = ['reason', 'notes', 'given_by', 'auto_generated', 'created_at']
    fields = ['reason', 'notes', 'given_by', 'auto_generated', 'created_at']
    can_delete = True
    verbose_name = 'Strike'
    verbose_name_plural = 'Strike Log'

    def has_add_permission(self, request, obj=None):
        return False


# ── User admin ────────────────────────────────────────────────────────────────

class TwamboUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


class TwamboUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('phone_number', 'full_name', 'role')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = TwamboUserChangeForm
    add_form = TwamboUserCreationForm

    list_display = [
        'full_name', 'phone_number', 'role',
        'strike_visual', 'is_banned', 'is_active',
        'rating_display', 'joined', 'quick_actions',
    ]
    list_per_page = 20
    list_filter = ['role', 'is_banned', 'is_active']
    search_fields = ['phone_number', 'full_name']
    ordering = ['-created_at']
    inlines = [StrikeInline]

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal', {'fields': ('full_name', 'email', 'role', 'profile_photo', 'fcm_token')}),
        ('Status', {
            'fields': ('is_active', 'is_staff', 'is_superuser',
                       'is_verified', 'is_banned', 'ban_until', 'strike_count'),
        }),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'full_name', 'role', 'password1', 'password2'),
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/give-strike/',
                 self.admin_site.admin_view(self._give_strike_view),
                 name='accounts_user_give_strike'),
            path('<int:pk>/ban/',
                 self.admin_site.admin_view(self._ban_view),
                 name='accounts_user_ban'),
            path('<int:pk>/unban/',
                 self.admin_site.admin_view(self._unban_view),
                 name='accounts_user_unban'),
            path('<int:pk>/delete-account/',
                 self.admin_site.admin_view(self._delete_account_view),
                 name='accounts_user_delete_account'),
        ]
        return custom + urls

    def _delete_account_view(self, request, pk):
        user = User.objects.get(pk=pk)
        if request.method == 'POST':
            name = user.full_name
            phone = user.phone_number
            user.delete()
            self.message_user(
                request,
                f'Account for {name} ({phone}) has been deleted. '
                f'That phone number is now free to re-register.',
                messages.SUCCESS,
            )
            return HttpResponseRedirect(reverse('admin:accounts_user_changelist'))
        context = dict(
            self.admin_site.each_context(request),
            target_user=user,
            title=f'Delete Account — {user.full_name}',
        )
        return TemplateResponse(request, 'admin/accounts/user/delete_account.html', context)

    def _give_strike_view(self, request, pk):
        user = User.objects.get(pk=pk)
        if request.method == 'POST':
            reason = request.POST.get('reason', 'other')
            notes = request.POST.get('notes', '').strip()
            user.give_strike(reason=reason, notes=notes, given_by=request.user)
            self.message_user(
                request,
                f'Strike added for {user.full_name}. '
                f'Total: {user.strike_count}{"  — User BANNED." if user.is_banned else ""}',
                messages.WARNING if not user.is_banned else messages.ERROR,
            )
            return HttpResponseRedirect(reverse('admin:accounts_user_change', args=[pk]))
        context = dict(
            self.admin_site.each_context(request),
            target_user=user,
            title=f'Give Strike — {user.full_name}',
            reason_choices=Strike.REASON_CHOICES,
        )
        return TemplateResponse(request, 'admin/accounts/user/give_strike.html', context)

    def _ban_view(self, request, pk):
        user = User.objects.get(pk=pk)
        user.is_banned = True
        user.save(update_fields=['is_banned', 'updated_at'])
        self.message_user(request, f'{user.full_name} has been banned.', messages.ERROR)
        return HttpResponseRedirect(reverse('admin:accounts_user_change', args=[pk]))

    def _unban_view(self, request, pk):
        user = User.objects.get(pk=pk)
        user.is_banned = False
        user.save(update_fields=['is_banned', 'updated_at'])
        self.message_user(request, f'{user.full_name} has been unbanned.', messages.SUCCESS)
        return HttpResponseRedirect(reverse('admin:accounts_user_change', args=[pk]))

    # ── Display columns ───────────────────────────────────────────────────────

    @admin.display(description='Strikes', ordering='strike_count')
    def strike_visual(self, obj):
        return _strike_dots(obj.strike_count)

    @admin.display(description='Rating')
    def rating_display(self, obj):
        try:
            r = obj.driver_profile.rating if obj.is_driver else obj.rider_profile.rating
            color = '#2e7d32' if r >= 4 else ('#f57c00' if r >= 3 else '#c62828')
            return format_html('<span style="color:{};font-weight:bold;">★ {}</span>', color, r)
        except Exception:
            return '—'

    @admin.display(description='Joined', ordering='created_at')
    def joined(self, obj):
        return obj.created_at.strftime('%d %b %Y')

    @admin.display(description='Actions')
    def quick_actions(self, obj):
        strike_url = reverse('admin:accounts_user_give_strike', args=[obj.pk])
        delete_url = reverse('admin:accounts_user_delete_account', args=[obj.pk])
        del_btn = (
            '<a href="{d}" style="background:#37474f;color:#fff;padding:3px 8px;'
            'border-radius:3px;text-decoration:none;font-size:11px;margin-left:4px;">Delete</a>'
        )
        if obj.is_banned:
            unban_url = reverse('admin:accounts_user_unban', args=[obj.pk])
            return format_html(
                '<a href="{s}" style="background:#e65100;color:#fff;padding:3px 8px;'
                'border-radius:3px;text-decoration:none;font-size:11px;margin-right:4px;">+Strike</a>'
                '<a href="{u}" style="background:#2e7d32;color:#fff;padding:3px 8px;'
                'border-radius:3px;text-decoration:none;font-size:11px;">Unban</a>' + del_btn,
                s=strike_url, u=unban_url, d=delete_url,
            )
        ban_url = reverse('admin:accounts_user_ban', args=[obj.pk])
        return format_html(
            '<a href="{s}" style="background:#e65100;color:#fff;padding:3px 8px;'
            'border-radius:3px;text-decoration:none;font-size:11px;margin-right:4px;">+Strike</a>'
            '<a href="{b}" style="background:#c62828;color:#fff;padding:3px 8px;'
            'border-radius:3px;text-decoration:none;font-size:11px;">Ban</a>' + del_btn,
            s=strike_url, b=ban_url, d=delete_url,
        )

    # ── Bulk actions ──────────────────────────────────────────────────────────

    actions = ['bulk_ban', 'bulk_unban', 'bulk_give_strike']

    @admin.action(description='Ban selected users')
    def bulk_ban(self, request, queryset):
        updated = queryset.update(is_banned=True)
        self.message_user(request, f'{updated} user(s) banned.', messages.ERROR)

    @admin.action(description='Unban selected users')
    def bulk_unban(self, request, queryset):
        updated = queryset.update(is_banned=False)
        self.message_user(request, f'{updated} user(s) unbanned.', messages.SUCCESS)

    @admin.action(description='Give strike (Other) to selected users')
    def bulk_give_strike(self, request, queryset):
        for user in queryset:
            user.give_strike(reason='other', notes='Bulk action by admin.', given_by=request.user)
        self.message_user(request, f'Strike added to {queryset.count()} user(s).', messages.WARNING)


# ── Strike admin ──────────────────────────────────────────────────────────────

@admin.register(Strike)
class StrikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'reason', 'notes_short', 'given_by', 'auto_generated', 'created_at']
    list_filter = ['reason', 'auto_generated', 'created_at']
    search_fields = ['user__full_name', 'user__phone_number', 'notes']
    readonly_fields = ['user', 'reason', 'notes', 'given_by', 'auto_generated', 'created_at']
    ordering = ['-created_at']

    @admin.display(description='Notes')
    def notes_short(self, obj):
        return (obj.notes[:60] + '…') if len(obj.notes) > 60 else obj.notes

    def has_add_permission(self, request):
        return False


# ── Driver profile admin ──────────────────────────────────────────────────────

@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = [
        'driver_name', 'phone_number', 'verification_status',
        'is_online', 'rating', 'total_trips', 'created_at', 'approval_actions',
    ]
    list_per_page = 20
    list_filter = ['verification_status', 'is_online']
    search_fields = ['user__phone_number', 'user__full_name']
    readonly_fields = [
        'driver_name', 'phone_number', 'created_at',
        'national_id_preview', 'drivers_license_preview', 'vehicle_registration_preview',
        'fitness_certificate_preview', 'insurance_certificate_preview', 'plate_photo_preview',
        'approval_actions',
    ]
    fieldsets = (
        ('Driver Info', {
            'fields': ('driver_name', 'phone_number', 'created_at', 'is_online', 'rating', 'total_trips'),
        }),
        ('Verification', {
            'fields': ('verification_status', 'rejection_reason'),
        }),
        ('Documents', {
            'fields': ('national_id_preview', 'drivers_license_preview', 'vehicle_registration_preview',
                       'fitness_certificate_preview', 'insurance_certificate_preview', 'plate_photo_preview'),
            'classes': ('wide',),
        }),
        ('Actions', {'fields': ('approval_actions',)}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pk>/approve/',
                 self.admin_site.admin_view(self._approve),
                 name='accounts_driverprofile_approve'),
            path('<int:pk>/reject/',
                 self.admin_site.admin_view(self._reject),
                 name='accounts_driverprofile_reject'),
        ]
        return custom + urls

    def _approve(self, request, pk):
        profile = DriverProfile.objects.get(pk=pk)
        profile.verification_status = DriverProfile.STATUS_APPROVED
        profile.rejection_reason = ''
        profile.approved_at = timezone.now()
        profile.save(update_fields=['verification_status', 'rejection_reason', 'approved_at'])
        self.message_user(request, f'{profile.user.full_name} approved as driver.', messages.SUCCESS)
        return HttpResponseRedirect(reverse('admin:accounts_driverprofile_change', args=[pk]))

    def _reject(self, request, pk):
        profile = DriverProfile.objects.get(pk=pk)
        if request.method == 'POST':
            reason = request.POST.get('rejection_reason', '').strip()
            profile.verification_status = DriverProfile.STATUS_REJECTED
            profile.rejection_reason = reason
            profile.approved_at = None
            profile.save(update_fields=['verification_status', 'rejection_reason', 'approved_at'])
            self.message_user(request, f'{profile.user.full_name} rejected.', messages.WARNING)
            return HttpResponseRedirect(reverse('admin:accounts_driverprofile_change', args=[pk]))
        context = dict(
            self.admin_site.each_context(request),
            profile=profile,
            title='Reject Driver',
        )
        return TemplateResponse(request, 'admin/accounts/driverprofile/reject_confirm.html', context)

    @admin.display(description='Name')
    def driver_name(self, obj):
        return obj.user.full_name

    @admin.display(description='Phone')
    def phone_number(self, obj):
        return obj.user.phone_number

    @admin.display(description='National ID')
    def national_id_preview(self, obj):
        return _doc_img(obj.national_id, 'National ID')

    @admin.display(description='Drivers Licence')
    def drivers_license_preview(self, obj):
        return _doc_img(obj.drivers_license, "Driver's Licence")

    @admin.display(description='Vehicle Registration')
    def vehicle_registration_preview(self, obj):
        return _doc_img(obj.vehicle_registration, 'Vehicle Registration')

    @admin.display(description='Fitness Certificate')
    def fitness_certificate_preview(self, obj):
        return _doc_img(obj.fitness_certificate, 'Fitness Certificate')

    @admin.display(description='Insurance Certificate')
    def insurance_certificate_preview(self, obj):
        return _doc_img(obj.insurance_certificate, 'Insurance Certificate')

    @admin.display(description='Number Plate Photo')
    def plate_photo_preview(self, obj):
        return _doc_img(obj.plate_photo, 'Number Plate')

    @admin.display(description='Quick Actions')
    def approval_actions(self, obj):
        if obj.pk is None:
            return '—'
        approve_url = reverse('admin:accounts_driverprofile_approve', args=[obj.pk])
        reject_url = reverse('admin:accounts_driverprofile_reject', args=[obj.pk])
        return format_html(
            '<a class="button" style="background:#2e7d32;color:#fff;padding:4px 10px;'
            'border-radius:3px;text-decoration:none;margin-right:6px;" href="{approve}">Approve</a>'
            '<a class="button" style="background:#c62828;color:#fff;padding:4px 10px;'
            'border-radius:3px;text-decoration:none;" href="{reject}">Reject</a>',
            approve=approve_url, reject=reject_url,
        )

    actions = ['bulk_approve', 'bulk_reject']

    @admin.action(description='Approve selected drivers')
    def bulk_approve(self, request, queryset):
        updated = queryset.update(
            verification_status=DriverProfile.STATUS_APPROVED,
            approved_at=timezone.now(),
        )
        self.message_user(request, f'{updated} driver(s) approved.', messages.SUCCESS)

    @admin.action(description='Reject selected drivers')
    def bulk_reject(self, request, queryset):
        updated = queryset.update(
            verification_status=DriverProfile.STATUS_REJECTED,
            approved_at=None,
        )
        self.message_user(request, f'{updated} driver(s) rejected.', messages.WARNING)


# ── Other models ──────────────────────────────────────────────────────────────

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['driver', 'vehicle_type', 'make', 'model', 'plate_number', 'total_seats']
    search_fields = ['plate_number', 'driver__full_name']


@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'rating', 'total_rides']
    search_fields = ['user__phone_number', 'user__full_name']


admin.site.register(SavedPlace)


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = ['latest_version', 'min_required_version', 'download_url', 'updated_at']
    fields = ['latest_version', 'min_required_version', 'download_url', 'release_notes']

    def has_add_permission(self, request):
        return not AppVersion.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ── Custom admin site with dashboard stats ────────────────────────────────────

class TwamboAdminSite(admin.AdminSite):
    site_header = 'TWAMBO Admin'
    site_title = 'TWAMBO'
    index_title = 'Operations Dashboard'

    def index(self, request, extra_context=None):
        from apps.trips.models import Trip
        from apps.bookings.models import Booking
        from apps.payments.models import Commission

        today = timezone.now().date()
        month_start = today.replace(day=1)

        stats = {
            'total_riders': User.objects.filter(role='rider').count(),
            'total_drivers': User.objects.filter(role='driver').count(),
            'pending_drivers': DriverProfile.objects.filter(
                verification_status=DriverProfile.STATUS_PENDING
            ).count(),
            'banned_users': User.objects.filter(is_banned=True).count(),
            'users_with_strikes': User.objects.filter(strike_count__gt=0).count(),
            'trips_today': Trip.objects.filter(departure_time__date=today).count(),
            'active_trips': Trip.objects.filter(status=Trip.STATUS_ACTIVE).count(),
            'bookings_today': Booking.objects.filter(created_at__date=today).count(),
            'revenue_month': Commission.objects.filter(
                created_at__date__gte=month_start
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'recent_strikes': Strike.objects.select_related('user', 'given_by').order_by('-created_at')[:8],
            'pending_driver_list': DriverProfile.objects.filter(
                verification_status=DriverProfile.STATUS_PENDING
            ).select_related('user').order_by('created_at')[:5],
            'rider_list': User.objects.filter(role='rider').order_by('-created_at')[:10],
        }

        extra_context = extra_context or {}
        extra_context.update(stats)
        return super().index(request, extra_context)


# Register the custom site — swap it in via apps.py or keep using default
# (default is fine; the stats page is auto-rendered via the template below)
