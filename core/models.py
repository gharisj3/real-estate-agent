from django.db import models


class Property(models.Model):
    FLAT = "flat"
    HOUSE = "house"
    PLOT = "plot"
    TYPE_CHOICES = [
        (FLAT, "Flat"),
        (HOUSE, "House"),
        (PLOT, "Plot"),
    ]

    AVAILABLE = "available"
    SOLD = "sold"
    RENTED = "rented"
    STATUS_CHOICES = [
        (AVAILABLE, "Available"),
        (SOLD, "Sold"),
        (RENTED, "Rented"),
    ]

    CURRENCY_CHOICES = [
        ("PKR", "PKR"),
        ("AED", "AED"),
    ]

    title = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    area = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    bedrooms = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="PKR")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=AVAILABLE)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title
