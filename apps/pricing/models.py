from django.db import models


class Zone(models.Model):
    ZONE_LOCAL = 'local'
    ZONE_CITY = 'city'
    ZONE_INTERCITY = 'intercity'
    ZONE_LONGHAUL = 'longhaul'
    ZONE_CHOICES = [
        (ZONE_LOCAL, 'Local Township (0-5km)'),
        (ZONE_CITY, 'City-wide (5-15km)'),
        (ZONE_INTERCITY, 'Inter-city (15-50km)'),
        (ZONE_LONGHAUL, 'Long Haul (50km+)'),
    ]

    name = models.CharField(max_length=100)
    zone_type = models.CharField(max_length=15, choices=ZONE_CHOICES)
    rate_per_km = models.DecimalField(max_digits=6, decimal_places=2)
    is_active = models.BooleanField(default=True)
    city = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pricing_zones'

    def __str__(self):
        return f'{self.name} ({self.zone_type}) — K{self.rate_per_km}/km'
