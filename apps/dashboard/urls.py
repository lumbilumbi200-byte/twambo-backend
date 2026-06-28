from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('',              views.home,          name='home'),
    path('login/',        views.dash_login,    name='login'),
    path('logout/',       views.dash_logout,   name='logout'),

    path('riders/',                   views.riders,        name='riders'),
    path('riders/<int:pk>/',          views.rider_detail,  name='rider_detail'),

    path('drivers/',                  views.drivers,       name='drivers'),
    path('drivers/<int:pk>/',         views.driver_detail, name='driver_detail'),
    path('drivers/<int:pk>/approve/',        views.driver_approve,          name='driver_approve'),
    path('drivers/<int:pk>/reject/',         views.driver_reject,           name='driver_reject'),
    path('drivers/<int:pk>/toggle-approval/',views.driver_toggle_approval,  name='driver_toggle_approval'),

    path('users/<int:pk>/strike/',    views.give_strike,   name='give_strike'),
    path('users/<int:pk>/ban/',       views.ban_user,      name='ban_user'),
    path('users/<int:pk>/unban/',     views.unban_user,    name='unban_user'),
    path('users/<int:pk>/delete/',    views.delete_user,   name='delete_user'),
    path('strikes/<int:strike_pk>/remove/', views.remove_strike, name='remove_strike'),

    path('strikes/',   views.strikes_log, name='strikes'),
    path('trips/',     views.trips,       name='trips'),

    path('earnings/',    views.earnings,    name='earnings'),
    path('float-codes/', views.float_codes, name='float_codes'),

    path('slides/',               views.slides,       name='slides'),
    path('slides/new/',           views.slide_new,    name='slide_new'),
    path('slides/<int:pk>/edit/', views.slide_edit,   name='slide_edit'),
    path('slides/<int:pk>/delete/', views.slide_delete, name='slide_delete'),
    path('slides/<int:pk>/toggle/', views.slide_toggle, name='slide_toggle'),
]
