from django.db import models

class Trip(models.Model):
    current_location = models.CharField(max_length=255)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    cycle_hours_used = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Trip from {self.pickup_location} to {self.dropoff_location}"

class ELDLog(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="logs")
    day = models.IntegerField()
    driving_hours = models.FloatField()
    rest_hours = models.FloatField()
    fuel_stops = models.IntegerField()

    def __str__(self):
        return f"ELD Log for Trip ID {self.trip.id} on Day {self.day}"
