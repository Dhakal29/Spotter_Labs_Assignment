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
    Exact Next-Cheaper-Station Fuel Optimizer:
    - Vehicle starts at mile 0 with a full tank (500 miles range = 50 gallons).
    - Achieves 10 MPG (consumes 1 gallon every 10 miles).
    - Initial fuel consumed from the starting tank is priced at the cheapest reachable
      station near origin.
    - Optimal Refueling Algorithm:
      We model the journey as directed progress from origin (mile 0) to destination:
      1. If the destination is directly reachable with current fuel, journey is complete.
      2. Look ahead within a full tank capacity (500 miles) for any station CHEAPER
         than the current fuel price:
         - If a cheaper station exists ahead within full tank reach:
           If current fuel is insufficient to reach it, purchase ONLY enough fuel at
           the current stop to reach that next cheaper station. Then drive to it.
         - If NO cheaper station exists ahead within full tank reach:
           The current stop is the cheapest available option in 500 miles (local minimum).
           If destination is within full tank reach, buy just enough to reach destination.
           Otherwise, fill the tank to maximum capacity (50 gallons / 500 miles).
           Then advance to the cheapest station reachable with the new fuel level.
      3. If any gap between consecutive reachable stations exceeds 500 miles, return
         an explicit infeasible route error.
    """
    total_distance_miles = float(total_distance_miles)
    gallons_consumed_trip = round(total_distance_miles / MILES_PER_GALLON, 2)
    origin_price = _determine_origin_price(stations)

    # 1. Trips under 500 miles: Completed on initial full tank with zero stops.
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

    # Cluster closely-spaced stations (within 5 miles) keeping the cheapest option
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

    # Build sequence of nodes: Origin -> Stations -> Destination
    nodes: List[Dict[str, Any]] = [
        {"mile": 0.0, "price": origin_price, "name": "ORIGIN"}
    ]
    for s in filtered_stations:
        nodes.append({
            "id": s["id"],
            "opis_id": s["opis_id"],
            "name": s["name"],
            "address": s["address"],
            "city": s["city"],
            "state": s["state"],
            "mile": s["mile_along_route"],
            "price": float(s["price"]),
            "latitude": s["latitude"],
            "longitude": s["longitude"],
        })
    dest_idx = len(nodes)
    nodes.append({"mile": total_distance_miles, "price": 0.0, "name": "DESTINATION"})

    curr_idx = 0
    fuel_miles = MAX_RANGE_MILES
    chosen_stops = []
    en_route_gallons_bought = 0.0
    en_route_cost = 0.0

    while curr_idx < dest_idx:
        curr_node = nodes[curr_idx]
        dist_to_dest = total_distance_miles - curr_node["mile"]

        # If current fuel is already sufficient to reach destination, we arrive safely!
        if fuel_miles + 0.01 >= dist_to_dest:
            break

        # Stations reachable within a full tank from curr_node
        reachable_with_full = [
            i for i in range(curr_idx + 1, len(nodes))
            if nodes[i]["mile"] - curr_node["mile"] <= MAX_RANGE_MILES
        ]

        if not reachable_with_full:
            return {
                "is_feasible": False,
                "error": (
                    f"Route is infeasible: Distance from mile {round(curr_node['mile'], 1)} "
                    f"to next station exceeds the maximum vehicle range of {int(MAX_RANGE_MILES)} miles."
                ),
                "fuel_stops": [],
                "total_stops": 0,
                "total_gallons_consumed": gallons_consumed_trip,
                "total_gallons_purchased_en_route": 0.0,
                "total_fuel_cost_usd": 0.0,
            }

        # Check if there is a cheaper station reachable within a full tank
        cheaper_nodes = [
            i for i in reachable_with_full
            if nodes[i]["price"] < curr_node["price"]
        ]

        if cheaper_nodes:
            # Advance to the first cheaper station
            next_idx = cheaper_nodes[0]
            next_node = nodes[next_idx]
            dist_leg = next_node["mile"] - curr_node["mile"]

            if fuel_miles < dist_leg:
                needed_range = dist_leg - fuel_miles
                gallons_to_buy = round(needed_range / MILES_PER_GALLON, 2)
                # Ensure rounding doesn't leave us 0.01 gal short
                if gallons_to_buy * MILES_PER_GALLON < needed_range:
                    gallons_to_buy = round(gallons_to_buy + 0.01, 2)

                cost_at_stop = round(gallons_to_buy * curr_node["price"], 2)
                fuel_miles += gallons_to_buy * MILES_PER_GALLON

                if gallons_to_buy > 0 and curr_idx > 0:
                    en_route_gallons_bought += gallons_to_buy
                    en_route_cost += cost_at_stop
                    chosen_stops.append({
                        "stop_number": len(chosen_stops) + 1,
                        "station_name": curr_node["name"],
                        "address": curr_node.get("address", ""),
                        "city": curr_node.get("city", ""),
                        "state": curr_node.get("state", ""),
                        "price_per_gallon": curr_node["price"],
                        "mile_along_route": round(curr_node["mile"], 1),
                        "gallons_refueled": gallons_to_buy,
                        "cost_usd": cost_at_stop,
                        "coordinates": {
                            "latitude": curr_node.get("latitude", 0.0),
                            "longitude": curr_node.get("longitude", 0.0),
                        },
                    })

            fuel_miles -= dist_leg
            curr_idx = next_idx
        else:
            # No cheaper station within full tank reach: curr_node is a local price minimum!
            if dist_to_dest <= MAX_RANGE_MILES:
                needed_range = max(0.0, dist_to_dest - fuel_miles)
            else:
                needed_range = max(0.0, MAX_RANGE_MILES - fuel_miles)

            gallons_to_buy = round(needed_range / MILES_PER_GALLON, 2)
            if gallons_to_buy * MILES_PER_GALLON < needed_range:
                gallons_to_buy = round(gallons_to_buy + 0.01, 2)

            cost_at_stop = round(gallons_to_buy * curr_node["price"], 2)
            fuel_miles += gallons_to_buy * MILES_PER_GALLON

            if gallons_to_buy > 0 and curr_idx > 0:
                en_route_gallons_bought += gallons_to_buy
                en_route_cost += cost_at_stop
                chosen_stops.append({
                    "stop_number": len(chosen_stops) + 1,
                    "station_name": curr_node["name"],
                    "address": curr_node.get("address", ""),
                    "city": curr_node.get("city", ""),
                    "state": curr_node.get("state", ""),
                    "price_per_gallon": curr_node["price"],
                    "mile_along_route": round(curr_node["mile"], 1),
                    "gallons_refueled": gallons_to_buy,
                    "cost_usd": cost_at_stop,
                    "coordinates": {
                        "latitude": curr_node.get("latitude", 0.0),
                        "longitude": curr_node.get("longitude", 0.0),
                    },
                })

            if fuel_miles + 0.01 >= dist_to_dest:
                break

            # Advance to the cheapest station reachable with newly purchased fuel
            reachable_now = [
                i for i in range(curr_idx + 1, len(nodes))
                if nodes[i]["mile"] - curr_node["mile"] <= fuel_miles
            ]
            if not reachable_now:
                return {
                    "is_feasible": False,
                    "error": f"No reachable station found ahead of mile {round(curr_node['mile'], 1)}.",
                    "fuel_stops": [],
                    "total_stops": 0,
                    "total_gallons_consumed": gallons_consumed_trip,
                    "total_gallons_purchased_en_route": 0.0,
                    "total_fuel_cost_usd": 0.0,
                }

            next_idx = min(reachable_now, key=lambda i: nodes[i]["price"])
            fuel_miles -= (nodes[next_idx]["mile"] - curr_node["mile"])
            curr_idx = next_idx

    # Account for starting tank fuel cost
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
