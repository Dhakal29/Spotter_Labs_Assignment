from django.db import models


class FuelStation(models.Model):
    """
    Represents a fuel station with pricing and geographic coordinates.
    Spatial indexing on latitude and longitude allows near-instant corridor searches.
    """
    opis_id = models.IntegerField(db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120, db_index=True)
    state = models.CharField(max_length=10, db_index=True)
    price = models.DecimalField(max_digits=6, decimal_places=3)
    latitude = models.FloatField(db_index=True)
    longitude = models.FloatField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state} (${self.price}/gal)"
