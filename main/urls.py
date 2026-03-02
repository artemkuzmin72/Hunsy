from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", views.post_list, name="post_list"),
    path("post/<int:pk>/", views.post_detail, name="post_detail"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(
        template_name="login.html"
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(
        next_page="post_list"
    ), name="logout"),
    path("subscribe/", views.subscribe, name="subscribe"),
    path("success/", views.payment_success, name="success"),
]