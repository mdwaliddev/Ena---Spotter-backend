import math

AVG_SPEED = 55
MAX_DAILY_HOURS = 11
FUEL_INTERVAL = 1000

def generate_eld_logs(total_miles, cycle_used):
    remaining_miles = total_miles
    remaining_cycle = 70 - cycle_used
    logs = []
    day = 1

    while remaining_miles > 0 and remaining_cycle > 0:
        max_miles_today = min(
            remaining_miles,
            MAX_DAILY_HOURS * AVG_SPEED,
            remaining_cycle * AVG_SPEED
        )

        driving_hours = round(max_miles_today / AVG_SPEED, 2)

        logs.append({
            "day": day,
            "driving_hours": driving_hours,
            "fuel_stops": math.floor(max_miles_today / FUEL_INTERVAL),
        })

        remaining_miles -= max_miles_today
        remaining_cycle -= driving_hours
        day += 1

    return logs
