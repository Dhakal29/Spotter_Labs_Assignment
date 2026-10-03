from django.urls import path
from .views import plan_route, health_check, map_view

urlpatterns = [
    path("", map_view, name="map-home"),
    path("map/", map_view, name="map-view"),
    path("route/", plan_route, name="plan-route"),
    path("health/", health_check, name="health-check"),
]

