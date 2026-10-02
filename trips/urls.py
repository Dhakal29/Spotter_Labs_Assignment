from django.urls import path
from .views import plan_route, health_check

urlpatterns = [
    path("route/", plan_route, name="plan-route"),
    path("health/", health_check, name="health-check"),
]
