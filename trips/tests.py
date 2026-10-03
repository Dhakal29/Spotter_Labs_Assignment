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

    def test_trip_under_500_miles_requires_zero_stops_with_fuel_cost(self):
        """A vehicle with 500-mile range makes 0 en-route stops on a 350-mile trip, but fuel is priced."""
        stations = [
            {
                "id": 1,
                "opis_id": 1,
                "name": "Origin Fuel",
                "address": "123 Main St",
                "city": "Austin",
                "state": "TX",
                "price": 3.00,
                "latitude": 30.26,
                "longitude": -97.74,
                "mile_along_route": 20.0,
            }
        ]
        result = optimize_fuel_stops(total_distance_miles=350.0, stations=stations)
        self.assertEqual(result["total_stops"], 0)
        self.assertEqual(result["fuel_stops"], [])
        self.assertEqual(result["total_gallons_consumed"], 35.0)
        # 35 gallons * $3.00 = $105.00
        self.assertEqual(result["total_fuel_cost_usd"], 105.00)

    def test_exact_optimal_next_cheaper_station(self):
        """
        900-mile trip with:
        - Station A at mile 400 charging $3.00/gal
        - Station B at mile 600 charging $2.00/gal
        Vehicle starts with 50 gallons (500 miles range).
        At mile 400, fuel range left is 100 miles. Station B is at mile 600 (200 miles away).
        Since Station B is cheaper ($2 < $3), vehicle should purchase only 10 gallons (100 miles)
        at Station A to reach Station B.
        At Station B, remaining range is 0. Destination is 300 miles away.
        Vehicle buys 30 gallons at $2.00.
        Total:
        - Start tank: 50 gal * $3.00 = $150.00 (or valued at origin station $3.00)
        - En route: 10 gal * $3.00 ($30) + 30 gal * $2.00 ($60) = $90 en-route.
        """
        stations = [
            {
                "id": 1,
                "opis_id": 101,
                "name": "Station A",
                "address": "Mile 400",
                "city": "Town A",
                "state": "TX",
                "price": 3.00,
                "latitude": 35.0,
                "longitude": -101.0,
                "mile_along_route": 400.0,
            },
            {
                "id": 2,
                "opis_id": 102,
                "name": "Station B",
                "address": "Mile 600",
                "city": "Town B",
                "state": "TX",
                "price": 2.00,
                "latitude": 36.0,
                "longitude": -103.0,
                "mile_along_route": 600.0,
            },
        ]
        result = optimize_fuel_stops(total_distance_miles=900.0, stations=stations)
        self.assertTrue(result["is_feasible"])
        self.assertEqual(result["total_stops"], 2)

        # Stop 1 (Station A) refueled 10.0 gal ($30.00)
        self.assertEqual(result["fuel_stops"][0]["gallons_refueled"], 10.0)
        self.assertEqual(result["fuel_stops"][0]["cost_usd"], 30.0)

        # Stop 2 (Station B) refueled 30.0 gal ($60.00)
        self.assertEqual(result["fuel_stops"][1]["gallons_refueled"], 30.0)
        self.assertEqual(result["fuel_stops"][1]["cost_usd"], 60.0)

        # En-route purchased: 40.0 gallons
        self.assertEqual(result["total_gallons_purchased_en_route"], 40.0)
        # Total consumed: 90.0 gallons
        self.assertEqual(result["total_gallons_consumed"], 90.0)

    def test_infeasible_route_gap_exceeds_500_miles(self):
        """A 1200-mile trip with a 600-mile gap between stations is flagged as infeasible."""
        stations = [
            {
                "id": 1,
                "opis_id": 101,
                "name": "Early Station",
                "address": "Mile 200",
                "city": "Town A",
                "state": "TX",
                "price": 3.00,
                "latitude": 35.0,
                "longitude": -101.0,
                "mile_along_route": 200.0,
            },
            {
                "id": 2,
                "opis_id": 102,
                "name": "Far Station",
                "address": "Mile 850",
                "city": "Town B",
                "state": "TX",
                "price": 3.00,
                "latitude": 36.0,
                "longitude": -103.0,
                "mile_along_route": 850.0,
            },
        ]
        result = optimize_fuel_stops(total_distance_miles=1200.0, stations=stations)
        self.assertFalse(result["is_feasible"])
        self.assertIn("exceeds the maximum vehicle range", result["error"])


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

    def test_same_start_and_finish_returns_400(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Austin, TX", "finish": "Austin, TX"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be the same", response.json()["error"])

    def test_health_check_endpoint(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_map_page_renders_html_200(self):
        """Web UI returns 200 OK with Leaflet map container."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spotter Labs Fuel Route Planner")
        self.assertContains(response, "id=\"map\"")

    def test_short_trip_zero_stops_and_correct_consumption(self):
        """A short 80-mile trip should not crash, requires 0 stops, and consumes exactly 8.0 gallons."""
        result = optimize_fuel_stops(total_distance_miles=80.0, stations=[])
        self.assertTrue(result["is_feasible"])
        self.assertEqual(result["total_stops"], 0)
        self.assertEqual(result["fuel_stops"], [])
        self.assertEqual(result["total_gallons_consumed"], 8.0)
        self.assertEqual(result["total_gallons_purchased_en_route"], 0.0)

    def test_strict_500_mile_feasibility_and_tank_capacity_bounds(self):
        """
        Verify that:
        1. Gallons refueled at any single stop never exceeds 50.0 gallons (tank capacity).
        2. Every leg between consecutive stops is strictly <= 500 miles.
        3. Total gallons consumed matches total distance / 10 MPG.
        """
        trip_distance = 1350.0
        stations = [
            {"id": 1, "name": "Stop 1", "mile_along_route": 400.0, "price": 3.40},
            {"id": 2, "name": "Stop 2", "mile_along_route": 750.0, "price": 3.10},
            {"id": 3, "name": "Stop 3", "mile_along_route": 1100.0, "price": 3.60},
        ]
        result = optimize_fuel_stops(total_distance_miles=trip_distance, stations=stations)
        self.assertTrue(result["is_feasible"])
        self.assertEqual(result["total_gallons_consumed"], 135.0)

        prev_mile = 0.0
        for stop in result["fuel_stops"]:
            stop_mile = stop["mile_along_route"]
            leg_distance = stop_mile - prev_mile
            self.assertLessEqual(leg_distance, 500.0, f"Leg from {prev_mile} to {stop_mile} exceeded 500 miles!")
            self.assertLessEqual(stop["gallons_refueled"], 50.0, f"Gallons refueled at {stop['station_name']} exceeded 50-gallon tank capacity!")
            self.assertGreater(stop["gallons_refueled"], 0.0)
            prev_mile = stop_mile

        # Final leg to destination must also be <= 500 miles
        self.assertLessEqual(trip_distance - prev_mile, 500.0)

