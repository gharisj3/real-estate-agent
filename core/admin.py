from django.contrib import admin

from core.models import Property


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("title", "city", "area", "type", "bedrooms", "price", "currency", "status")
    list_filter = ("city", "type", "status", "currency")
    search_fields = ("title", "city", "area")
