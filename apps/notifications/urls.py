from django.urls import path
from . import views

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification-list'),
    path('read-all/', views.mark_all_read, name='mark-all-read'),
    path('<int:pk>/read/', views.mark_read, name='mark-read'),
]
