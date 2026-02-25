from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from main.views import register

urlpatterns = [
    path('', views.index, name='index'),
    path('main/', views.main, name='main'),
    path("register/", register, name="register"),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]