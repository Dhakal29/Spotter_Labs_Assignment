from django.urls import path

from .views import plan_route

urlpatterns = [
    path("route/", plan_route, name="plan-route"),
]
