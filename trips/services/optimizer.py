import math
from typing import List, Dict, Any, Optional

MAX_RANGE_MILES = 500.0
MILES_PER_GALLON = 10.0
TANK_CAPACITY_GALLONS = MAX_RANGE_MILES / MILES_PER_GALLON  # 50.0 gallons
DEFAULT_FALLBACK_PRICE_PER_GALLON = 3.25


def _determine_origin_price(stations: List[Dict[str, Any]]) -> float:
    """
    Returns the price of the cheapest fuel station reachable from the start of the trip
    (within MAX_RANGE_MILES). If no station exists along the route, falls back to the
    first station's price or a standard national average default.
    """
    reachable_from_origin = [
        s for s in stations if 0.0 <= s["mile_along_route"] <= MAX_RANGE_MILES
    ]
    if reachable_from_origin:
        return min(s["price"] for s in reachable_from_origin)
    if stations:
        return stations[0]["price"]
    return DEFAULT_FALLBACK_PRICE_PER_GALLON


def optimize_fuel_stops(
    total_distance_miles: float,
    stations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Fuel Stop Optimizer (Next Cheaper Station Greedy Strategy):
    - Vehicle leaves the origin with a full tank (500-mile range = 50 gallons).
    - Consumption is strictly 1 gallon per 10 miles (10 MPG).
    - Fuel burned from the initial tank is priced using the cheapest reachable
      station near origin.
    - At any point / station:
        1. If the destination is within reachable range, buy only enough fuel to reach
           the finish (or 0 if current remaining fuel is already sufficient).
        2. Otherwise, look ahead within reach (next 500 miles) for any station with a
           LOWER price than the current station.
           - If a cheaper station exists within reach, buy ONLY enough fuel to reach
             that next cheaper station.
           - If NO cheaper station exists within reach, this station is a local minimum:
             fill up completely (50 gallons / 500 miles) to maximize miles driven on
             cheap fuel.
    - If there is a gap > 500 miles with no fuel station, the route is physically
      infeasible for a 500-mile vehicle, and an error status is returned.
    """
    total_distance_miles = float(total_distance_miles)
    gallons_consumed_trip = round(total_distance_miles / MILES_PER_GALLON, 2)
    origin_price = _determine_origin_price(stations)

    # 1. Trips under or equal to 500 miles: No stops required on the road.
    if total_distance_miles <= MAX_RANGE_MILES:
        initial_fuel_cost = round((total_distance_miles / MILES_PER_GALLON) * origin_price, 2)
        return {
            "is_feasible": True,
            "fuel_stops": [],
            "total_stops": 0,
            "total_gallons_consumed": gallons_consumed_trip,
            "total_gallons_purchased_en_route": 0.0,
            "total_fuel_cost_usd": initial_fuel_cost,
            "origin_fuel_price_usd": round(origin_price, 3),
            "message": "Trip completed within initial 500-mile tank range. Zero en-route stops required.",
        }

    # Filter out stations before origin or beyond destination, sort ascending by mile
    valid_stations = [
        st for st in stations
        if 0.0 < st["mile_along_route"] < total_distance_miles
    ]
    valid_stations.sort(key=lambda s: s["mile_along_route"])

    # Cluster closely-spaced stations (within 5 miles) to keep the cheapest choice
    filtered_stations: List[Dict[str, Any]] = []
    for st in valid_stations:
        if not filtered_stations:
            filtered_stations.append(st)
        else:
            prev = filtered_stations[-1]
            if st["mile_along_route"] - prev["mile_along_route"] < 5.0:
                if st["price"] < prev["price"]:
                    filtered_stations[-1] = st
            else:
                filtered_stations.append(st)

    # Check for impossible gaps (where vehicle would run dry)
    checkpoints = [0.0] + [s["mile_along_route"] for s in filtered_stations] + [total_distance_miles]
    for idx in range(len(checkpoints) - 1):
        gap = checkpoints[idx + 1] - checkpoints[idx]
        if gap > MAX_RANGE_MILES:
            return {
                "is_feasible": False,
                "error": (
                    f"Route is infeasible: Distance between mile {round(checkpoints[idx], 1)} "
                    f"and mile {round(checkpoints[idx + 1], 1)} is {round(gap, 1)} miles, "
                    f"which exceeds the maximum vehicle range of {int(MAX_RANGE_MILES)} miles."
                ),
                "fuel_stops": [],
                "total_stops": 0,
                "total_gallons_consumed": gallons_consumed_trip,
                "total_gallons_purchased_en_route": 0.0,
                "total_fuel_cost_usd": 0.0,
            }

    # Vehicle state
    current_mile = 0.0
    current_fuel_range = MAX_RANGE_MILES  # Starts full (500 miles range)
    chosen_stops = []
    en_route_gallons_bought = 0.0
    en_route_cost = 0.0

    # We iterate until the vehicle can reach the destination
    while current_mile + current_fuel_range < total_distance_miles:
        # All stations strictly ahead and within current remaining fuel range
        reachable_ahead = [
            st for st in filtered_stations
            if current_mile < st["mile_along_route"] <= current_mile + current_fuel_range
        ]

        if not reachable_ahead:
            # Cannot reach any station ahead with current fuel
            return {
                "is_feasible": False,
                "error": f"No reachable fuel station found ahead of mile {round(current_mile, 1)} within remaining range of {round(current_fuel_range, 1)} miles.",
                "fuel_stops": [],
                "total_stops": 0,
                "total_gallons_consumed": gallons_consumed_trip,
                "total_gallons_purchased_en_route": 0.0,
                "total_fuel_cost_usd": 0.0,
            }

        # Check if there's any cheaper station reachable right now
        # If we are at origin (mile 0), we want to reach the cheapest reachable station
        if current_mile == 0.0:
            # Pick station that either offers the lowest price or allows reaching an even cheaper one
            # Find the best station within range
            best_next = min(reachable_ahead, key=lambda s: s["price"])
        else:
            # Find candidate with minimal price
            best_next = min(reachable_ahead, key=lambda s: s["price"])

        # Drive to chosen station
        leg_distance = best_next["mile_along_route"] - current_mile
        current_fuel_range -= leg_distance
        current_mile = best_next["mile_along_route"]

        # Now decide how much fuel to buy at best_next
        # Look ahead from best_next within full tank capacity (500 miles)
        dist_to_finish = total_distance_miles - current_mile
        stations_in_tank_reach = [
            st for st in filtered_stations
            if current_mile < st["mile_along_route"] <= current_mile + MAX_RANGE_MILES
        ]

        # Is there any station ahead within full range with a CHEAPER price than this one?
        cheaper_ahead = [
            st for st in stations_in_tank_reach
            if st["price"] < best_next["price"]
        ]

        if dist_to_finish <= MAX_RANGE_MILES and not cheaper_ahead:
            # Destination is reachable within full tank and no cheaper station ahead:
            # Buy just enough to reach finish
            needed_range = max(0.0, dist_to_finish - current_fuel_range)
        elif cheaper_ahead:
            # There is a cheaper station ahead within reach.
            # Buy only enough to reach the first cheaper station!
            first_cheaper = cheaper_ahead[0]
            dist_to_cheaper = first_cheaper["mile_along_route"] - current_mile
            needed_range = max(0.0, dist_to_cheaper - current_fuel_range)
        else:
            # No cheaper station within reach: this station is the cheapest in 500 miles.
            # Fill the tank to max capacity (500 miles).
            needed_range = max(0.0, MAX_RANGE_MILES - current_fuel_range)

        # Cap purchase to remaining tank volume
        needed_range = min(needed_range, MAX_RANGE_MILES - current_fuel_range)
        gallons_to_buy = round(needed_range / MILES_PER_GALLON, 2)
        cost_at_stop = round(gallons_to_buy * best_next["price"], 2)

        if gallons_to_buy > 0.0:
            current_fuel_range += gallons_to_buy * MILES_PER_GALLON
            en_route_gallons_bought += gallons_to_buy
            en_route_cost += cost_at_stop

            chosen_stops.append({
                "stop_number": len(chosen_stops) + 1,
                "station_name": best_next["name"],
                "address": best_next["address"],
                "city": best_next["city"],
                "state": best_next["state"],
                "price_per_gallon": best_next["price"],
                "mile_along_route": round(best_next["mile_along_route"], 1),
                "gallons_refueled": gallons_to_buy,
                "cost_usd": cost_at_stop,
                "coordinates": {
                    "latitude": best_next["latitude"],
                    "longitude": best_next["longitude"],
                },
            })

    # Account for starting tank fuel cost
    # The starting tank of 50 gallons is charged for the 50 gallons burned from it,
    # or if trip consumed less than 50, exactly gallons_consumed_trip.
    initial_gallons_burned = min(TANK_CAPACITY_GALLONS, gallons_consumed_trip)
    initial_fuel_cost = round(initial_gallons_burned * origin_price, 2)
    total_cost = round(en_route_cost + initial_fuel_cost, 2)

    return {
        "is_feasible": True,
        "fuel_stops": chosen_stops,
        "total_stops": len(chosen_stops),
        "total_gallons_consumed": gallons_consumed_trip,
        "total_gallons_purchased_en_route": round(en_route_gallons_bought, 2),
        "total_fuel_cost_usd": total_cost,
        "origin_fuel_price_usd": round(origin_price, 3),
    }
