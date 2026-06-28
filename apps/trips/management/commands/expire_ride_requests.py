from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.trips.models import RideRequest


class Command(BaseCommand):
    help = 'Expire pending RideRequests older than TWAMBO_BOOKING_WINDOW_MINUTES (default 7 min)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes', type=int, default=7,
            help='Minutes after which a pending request is considered stale (default: 7)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would be expired without making changes',
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(minutes=minutes)

        stale = RideRequest.objects.filter(
            status=RideRequest.STATUS_PENDING,
            created_at__lt=cutoff,
        )

        count = stale.count()
        if count == 0:
            self.stdout.write('No stale ride requests found.')
            return

        if dry_run:
            self.stdout.write(f'[DRY RUN] Would expire {count} ride request(s):')
            for r in stale:
                age = timezone.now() - r.created_at
                self.stdout.write(
                    f'  #{r.id} — {r.origin_name} → {r.destination_name} '
                    f'(rider: {r.rider_id}, {int(age.total_seconds() // 60)} min old)'
                )
            return

        updated = stale.update(status=RideRequest.STATUS_EXPIRED)
        self.stdout.write(
            self.style.SUCCESS(f'Expired {updated} stale ride request(s) (older than {minutes} min).')
        )
