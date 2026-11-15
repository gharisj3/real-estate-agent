"""Load 20 sample Property rows for testing.

Every row is clearly marked as sample data in its title, and every
address (city, area) is invented — never a real listing. Safe to run more
than once: it will not create duplicates.
"""
from django.core.management.base import BaseCommand

from core.models import Property

# Edit this once a real city is chosen for [AGENCY NAME].
SAMPLE_CITY = "[CITY]"

# Invented area names only — not real neighbourhoods.
SAMPLE_AREAS = [
    "Garden Heights",
    "Lakeview Block",
    "Sunset Residency",
    "Hilltop Enclave",
    "Riverside Terrace",
]

PROPERTY_TYPES = [choice[0] for choice in Property.TYPE_CHOICES]
STATUSES = [choice[0] for choice in Property.STATUS_CHOICES]

SAMPLE_COUNT = 20


class Command(BaseCommand):
    help = "Load 20 sample Property rows for testing (invented data only)."

    def handle(self, *args, **options):
        created = 0

        for i in range(SAMPLE_COUNT):
            area = SAMPLE_AREAS[i % len(SAMPLE_AREAS)]
            property_type = PROPERTY_TYPES[i % len(PROPERTY_TYPES)]
            bedrooms = 0 if property_type == Property.PLOT else (i % 5) + 1
            price = 5_000_000 + (i * 350_000)
            currency = "PKR" if i % 2 == 0 else "AED"
            status = STATUSES[i % len(STATUSES)]

            if bedrooms:
                title = f"[SAMPLE DATA] {bedrooms}-Bedroom {property_type.title()} in {area} #{i + 1}"
            else:
                title = f"[SAMPLE DATA] {property_type.title()} in {area} #{i + 1}"

            _, was_created = Property.objects.get_or_create(
                title=title,
                defaults={
                    "city": SAMPLE_CITY,
                    "area": area,
                    "type": property_type,
                    "bedrooms": bedrooms,
                    "price": price,
                    "currency": currency,
                    "status": status,
                    "description": (
                        "This is invented sample data for testing PropDesk. "
                        "It is not a real listing and the address is made up."
                    ),
                },
            )
            if was_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {created} new sample propert{'y' if created == 1 else 'ies'} "
                f"({SAMPLE_COUNT} expected in total once loaded)."
            )
        )
