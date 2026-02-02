from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Trip, ELDLog
from .serializers import TripSerializer, ELDLogSerializer

import requests
import math


class TripView(APIView):
    def post(self, request):
        data = request.data
        trip = Trip.objects.create(
            current_location=data['current_location'],
            pickup_location=data['pickup_location'],
            dropoff_location=data['dropoff_location'],
            cycle_hours_used=float(data.get('cycle_hours_used', 0))
        )

        # Build route from current -> pickup -> dropoff using OSRM (no API key required)
        route_info = self.get_route(data['current_location'], data['pickup_location'], data['dropoff_location'])

        # Create ELD logs based on route duration and assumptions
        logs = self.create_eld_logs(trip, route_info)

        serializer = TripSerializer(trip)
        response_data = serializer.data
        response_data['route'] = route_info.get('route_coords', [])
        response_data['stops'] = route_info.get('stops', [])
        response_data['distance_meters'] = route_info.get('distance_meters', 0)
        response_data['duration_seconds'] = route_info.get('duration_seconds', 0)

        return Response(response_data, status=status.HTTP_201_CREATED)

    def geocode(self, address):
        """Use Nominatim to geocode an address to (lon, lat). Returns tuple or None."""
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {'q': address, 'format': 'json', 'limit': 1}
            headers = {'User-Agent': 'EnaSpotter/1.0'}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            if not data:
                return None
            item = data[0]
            return (float(item['lon']), float(item['lat']))
        except Exception:
            return None

    def get_route(self, current_addr, pickup_addr, dropoff_addr):
        # Geocode addresses
        current = self.geocode(current_addr)
        pickup = self.geocode(pickup_addr)
        dropoff = self.geocode(dropoff_addr)
        if not (current and pickup and dropoff):
            return {}

        # OSRM expects lon,lat pairs
        coords = f"{current[0]},{current[1]};{pickup[0]},{pickup[1]};{dropoff[0]},{dropoff[1]}"
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"
        try:
            r = requests.get(osrm_url, timeout=10)
            r.raise_for_status()
            data = r.json()
            routes = data.get('routes') or []
            if not routes:
                return {}
            route = routes[0]
            geometry = route.get('geometry', {})
            # geometry['coordinates'] is list of [lon, lat]; convert to [lat, lon]
            coords_latlng = [[c[1], c[0]] for c in geometry.get('coordinates', [])]

            stops = [[current[1], current[0]], [pickup[1], pickup[0]], [dropoff[1], dropoff[0]]]

            return {
                'route_coords': coords_latlng,
                'stops': stops,
                'distance_meters': route.get('distance', 0),
                'duration_seconds': route.get('duration', 0)
            }
        except Exception:
            return {}

    def create_eld_logs(self, trip, route_info):
        # Assumptions
        MAX_DRIVING_PER_DAY = 11  # hrs per day (typical)
        CYCLE_LIMIT = 70  # hours per cycle

        duration_seconds = route_info.get('duration_seconds', 0)
        distance_meters = route_info.get('distance_meters', 0)
        total_driving_hours = duration_seconds / 3600.0

        # add 1 hour each for pickup and dropoff (on-duty but not driving)
        total_on_duty_extra = 2.0

        remaining_driving = total_driving_hours
        remaining_cycle = max(0.0, CYCLE_LIMIT - float(trip.cycle_hours_used))

        # compute fuel stops (at least once every 1000 miles)
        distance_miles = distance_meters / 1609.344
        total_fuel_stops = math.ceil(distance_miles / 1000) if distance_miles > 0 else 0

        logs = []
        day = 1
        fuel_assigned = 0
        while remaining_driving > 0 or (day == 1 and total_fuel_stops > 0):
            allowed = min(MAX_DRIVING_PER_DAY, remaining_driving, remaining_cycle)
            driving_hours = round(allowed, 2)
            remaining_driving = max(0.0, remaining_driving - driving_hours)
            remaining_cycle = max(0.0, remaining_cycle - driving_hours)

            # assign fuel stop to this day if needed
            fuel_stops = 0
            if fuel_assigned < total_fuel_stops:
                fuel_stops = 1
                fuel_assigned += 1

            rest_hours = round(max(0.0, 24 - driving_hours - total_on_duty_extra), 2)

            log = ELDLog.objects.create(trip=trip, day=day, driving_hours=driving_hours, rest_hours=rest_hours, fuel_stops=fuel_stops)
            logs.append(log)
            day += 1
            # safety: stop after 14 days to avoid infinite loops
            if day > 14:
                break

        return logs
