from django.db import models


class MarketingSlide(models.Model):
    ICON_CHOICES = [
        ('car',        'Car (Hire a Car)'),
        ('seat',       'Seat (Book a Seat)'),
        ('phone',      'Phone (Easy Booking)'),
        ('driver',     'Driver (Know Your Driver)'),
        ('city',       'City (About TWMB)'),
        ('shield',     'Shield (Safe Rides)'),
        ('savings',    'Piggy Bank (Save Money)'),
        ('star',       'Star (Top Rated)'),
        ('route',      'Route (Plan Your Trip)'),
        ('group',      'Group (Shared Rides)'),
    ]

    label    = models.CharField(max_length=40, help_text='Small label at top, e.g. HIRE A CAR')
    tagline  = models.CharField(max_length=80, help_text='Two-line headline. Use \\n for line break.')
    icon_key = models.CharField(max_length=20, choices=ICON_CHOICES, default='car')
    bg_color      = models.CharField(max_length=7, default='#FFC300', help_text='Hex colour, e.g. #FFC300')
    text_color    = models.CharField(max_length=7, default='#1A1A1A')
    accent_color  = models.CharField(max_length=7, default='#E6A800')
    is_active = models.BooleanField(default=True)
    order     = models.PositiveSmallIntegerField(default=0, help_text='Lower = shown first')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketing_slides'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'[{self.order}] {self.label} — {self.tagline[:30]}'
