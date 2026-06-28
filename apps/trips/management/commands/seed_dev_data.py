from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta


class Command(BaseCommand):
    help = 'Seed development database with test users, vehicles, and trips'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing seed trips before creating new ones')

    def handle(self, *args, **options):
        from apps.accounts.models import User, Vehicle, DriverProfile, RiderProfile
        from apps.trips.models import Trip

        self.stdout.write('Seeding dev data...')

        # ── Test driver ──────────────────────────────────────────────────────
        driver, created = User.objects.get_or_create(
            phone_number='+260971000001',
            defaults={'full_name': 'Chanda Mutale', 'role': 'driver', 'is_verified': True},
        )
        driver.set_password('driver1234')
        driver.save()
        self.stdout.write(f'  {"Created" if created else "Updated"} driver: +260971000001 / driver1234')

        vehicle, _ = Vehicle.objects.get_or_create(
            driver=driver,
            defaults={
                'vehicle_type': 'sedan', 'make': 'Toyota', 'model': 'Corolla',
                'color': 'White', 'plate_number': 'ABZ 1234', 'total_seats': 4, 'year': 2019,
            }
        )
        DriverProfile.objects.get_or_create(
            user=driver,
            defaults={
                'national_id': 'dev_placeholder.jpg',
                'drivers_license': 'dev_placeholder.jpg',
                'vehicle_registration': 'dev_placeholder.jpg',
                'verification_status': 'approved',
            }
        )

        # ── Second driver (minibus) ────────────────────────────────────────
        driver2, created2 = User.objects.get_or_create(
            phone_number='+260971000003',
            defaults={'full_name': 'Bwalya Kasonde', 'role': 'driver', 'is_verified': True},
        )
        driver2.set_password('driver1234')
        driver2.save()
        self.stdout.write(f'  {"Created" if created2 else "Updated"} driver2: +260971000003 / driver1234')

        vehicle2, _ = Vehicle.objects.get_or_create(
            driver=driver2,
            defaults={
                'vehicle_type': 'minibus', 'make': 'Toyota', 'model': 'Hiace',
                'color': 'White', 'plate_number': 'ACD 9012', 'total_seats': 11, 'year': 2018,
            }
        )
        DriverProfile.objects.get_or_create(
            user=driver2,
            defaults={
                'national_id': 'dev_placeholder.jpg',
                'drivers_license': 'dev_placeholder.jpg',
                'vehicle_registration': 'dev_placeholder.jpg',
                'verification_status': 'approved',
            }
        )

        # ── Test rider ───────────────────────────────────────────────────────
        rider, created = User.objects.get_or_create(
            phone_number='+260971000002',
            defaults={'full_name': 'Mwila Banda', 'role': 'rider', 'is_verified': True},
        )
        rider.set_password('rider1234')
        rider.save()
        self.stdout.write(f'  {"Created" if created else "Updated"} rider: +260971000002 / rider1234')

        RiderProfile.objects.get_or_create(user=rider)

        # ── Delete existing seed trips if requested ───────────────────────
        if options['reset']:
            Trip.objects.filter(driver__in=[driver, driver2]).delete()
            self.stdout.write('  Deleted existing seed trips')

        now = timezone.now()

        def mins(n):
            return now + timedelta(minutes=n)

        # route_fare = K9/km total road cost; current_shared_fare = route_fare / seats_taken
        # K50 example: route_fare=150 (3 seats taken, 50/seat), K36: route_fare=108, K27: route_fare=81
        trips_data = [
            # ── Scheduled (departing soon) ────────────────────────────────
            dict(driver=driver, vehicle=vehicle,
                 origin_name='Parklands', origin_lat=-12.7986, origin_lng=28.2045,
                 destination_name='Kitwe CBD', destination_lat=-12.8024, destination_lng=28.2132,
                 departure_time=mins(12), mode='shared', total_seats=4, available_seats=3,
                 route_fare=Decimal('27.00'), private_fare=Decimal('27.00'), minimum_riders=1),
            dict(driver=driver, vehicle=vehicle,
                 origin_name='Mindolo', origin_lat=-12.7720, origin_lng=28.1980,
                 destination_name='Nkana East', destination_lat=-12.8100, destination_lng=28.2250,
                 departure_time=mins(20), mode='shared', total_seats=4, available_seats=2,
                 route_fare=Decimal('90.00'), private_fare=Decimal('45.00'), minimum_riders=2),
            dict(driver=driver2, vehicle=vehicle2,
                 origin_name='Chamboli', origin_lat=-12.8330, origin_lng=28.2100,
                 destination_name='Kitwe CBD', destination_lat=-12.8024, destination_lng=28.2132,
                 departure_time=mins(8), mode='shared', total_seats=11, available_seats=7,
                 route_fare=Decimal('45.00'), private_fare=Decimal('36.00'), minimum_riders=3),
            dict(driver=driver, vehicle=vehicle,
                 origin_name='Riverside', origin_lat=-12.7875, origin_lng=28.2194,
                 destination_name='Wusakile', destination_lat=-12.8175, destination_lng=28.2450,
                 departure_time=mins(25), mode='shared', total_seats=4, available_seats=2,
                 route_fare=Decimal('54.00'), private_fare=Decimal('54.00'), minimum_riders=1),
            dict(driver=driver, vehicle=vehicle,
                 origin_name='Garneton', origin_lat=-12.8260, origin_lng=28.2275,
                 destination_name='Kitwe CBD', destination_lat=-12.8024, destination_lng=28.2132,
                 departure_time=mins(30), mode='private', total_seats=4, available_seats=4,
                 route_fare=Decimal('36.00'), private_fare=Decimal('36.00'), minimum_riders=1),
            dict(driver=driver, vehicle=vehicle,
                 origin_name='Nkana West', origin_lat=-12.8048, origin_lng=28.1848,
                 destination_name='Kitwe CBD', destination_lat=-12.8024, destination_lng=28.2132,
                 departure_time=mins(45), mode='dynamic', total_seats=4, available_seats=4,
                 route_fare=Decimal('27.00'), private_fare=Decimal('27.00'), minimum_riders=1),
            # ── Active / en-route (joinable right now) ───────────────────
            dict(driver=driver, vehicle=vehicle,
                 origin_name='Copperbelt University', origin_lat=-12.7868, origin_lng=28.2288,
                 destination_name='Kitwe CBD', destination_lat=-12.8024, destination_lng=28.2132,
                 departure_time=now - timedelta(minutes=5), mode='dynamic', total_seats=4,
                 available_seats=2, route_fare=Decimal('60.00'), private_fare=Decimal('36.00'),
                 minimum_riders=1, status='active', started_at=now - timedelta(minutes=5)),
            dict(driver=driver2, vehicle=vehicle2,
                 origin_name='Nkana West', origin_lat=-12.8048, origin_lng=28.1848,
                 destination_name='Twatasha', destination_lat=-12.8400, destination_lng=28.1650,
                 departure_time=now - timedelta(minutes=8), mode='dynamic', total_seats=4,
                 available_seats=1, route_fare=Decimal('150.00'), private_fare=Decimal('99.00'),
                 minimum_riders=1, status='active', started_at=now - timedelta(minutes=8)),
        ]

        created_count = 0
        for data in trips_data:
            stat = data.pop('status', Trip.STATUS_SCHEDULED)
            started = data.pop('started_at', None)
            dep = data['departure_time']
            Trip.objects.create(
                status=stat, started_at=started,
                booking_window_open=(stat == Trip.STATUS_SCHEDULED),
                booking_window_closes_at=dep - timedelta(minutes=7),
                **data,
            )
            created_count += 1

        self.stdout.write(f'  Created {created_count} trips')
        self.stdout.write(self.style.SUCCESS('\nDev seed complete.'))
        self.stdout.write('\n  Driver:  +260971000001 / driver1234')
        self.stdout.write('  Driver2: +260971000003 / driver1234')
        self.stdout.write('  Rider:   +260971000002 / rider1234')
