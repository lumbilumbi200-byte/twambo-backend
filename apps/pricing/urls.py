from django.urls import path
from . import views

urlpatterns = [
    path('calculate/', views.calculate_fare, name='calculate_fare'),
]
