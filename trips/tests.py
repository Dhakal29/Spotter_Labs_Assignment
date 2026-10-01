import json
from decimal import Decimal
from django.test import TestCase, Client
from trips.models import FuelStation
from trips.services.optimizer import optimize_fuel_stops
from trips.services.geocoding import is_within_contiguous_bounds


class FuelOptimizerTests(TestCase):
    def test_within_contiguous_us_bounds(self):
        # Inside US
        self.assertTrue(is_within_contiguous_bounds(32.7767, -96.7970))  # Dallas, TX
        self.assertTrue(is_within_contiguous_bounds(40.7128, -74.0060))  # New York, NY
        # Outside US
        self.assertFalse(is_within_contiguous_bounds(27.7172, 85.3240))  # Kathmandu
        self.assertFalse(is_within_contiguous_bounds(48.8566, 2.3522))   # Paris, France

    def test_trip_under_500_miles_requires_zero_stops(self):
        """A vehicle with 500-mile range shouldn't stop if trip is 350 miles."""
        result = optimize_fuel_stops(total_distance_miles=350.0, stations=[])
        self.assertEqual(result["total_stops"], 0)
        self.assertEqual(result["fuel_stops"], [])
        self.assertEqual(result["total_fuel_cost_usd"], 0.0)

    def test_trip_over_500_miles_requires_stops(self):
        """A 900-mile trip must stop before running out of 500-mile range."""
        stations = [
            {
                "id": 1,
                "opis_id": 101,
                "name": "Midway Station A",
                "address": "I-40 Exit 10",
                "city": "Amarillo",
                "state": "TX",
                "price": 3.00,
                "latitude": 35.2,
                "longitude": -101.8,
                "mile_along_route": 400.0,
            },
            {
                "id": 2,
                "opis_id": 102,
                "name": "Midway Station B",
                "address": "I-40 Exit 50",
                "city": "Tucumcari",
                "state": "NM",
                "price": 2.80,
                "latitude": 35.1,
                "longitude": -103.7,
                "mile_along_route": 480.0,
            }
        ]
        result = optimize_fuel_stops(total_distance_miles=900.0, stations=stations)
        self.assertGreaterEqual(result["total_stops"], 1)
        self.assertGreater(result["total_fuel_cost_usd"], 0.0)


class APIRouteEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_missing_body_returns_400(self):
        response = self.client.post("/api/route/", data="", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_missing_start_or_finish_returns_400(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Austin, TX"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
