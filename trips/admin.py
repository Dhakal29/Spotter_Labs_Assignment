from django.contrib import admin
from .models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = ("opis_id", "name", "city", "state", "price", "latitude", "longitude")
    search_fields = ("name", "city", "state", "opis_id")
    list_filter = ("state",)
    ordering = ("state", "city")
