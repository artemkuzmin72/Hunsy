from django.urls import path
from django.contrib import admin
from . import views, stripe_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # Основные страницы
    path("", views.index, name="index"),
    path('admin/', admin.site.urls),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile, name="profile"),
    # Посты и версии
    path("posts/", views.post_list, name="post_list"),
    path("post/create/", views.post_create, name="post_create"),
    path("post/<uuid:uuid>/", views.post_detail, name="post_detail"),
    path("post/<uuid:uuid>/edit/", views.post_edit, name="post_edit"),
    path("post/<uuid:uuid>/settings/", views.post_settings, name="post_settings"),
    path("post/<uuid:uuid>/versions/", views.post_versions, name="post_versions"),
    path("post/<uuid:uuid>/delete/", views.post_delete, name="post_delete"),
    path("post/<uuid:uuid>/media/", views.post_media_upload, name="post_media"),
    # Stripe подписки
    path("subscriptions/", stripe_views.subscription_plans, name="subscription_plans"),
    path(
        "subscriptions/create/<slug:plan_slug>/<str:interval>/",
        stripe_views.create_checkout_session,
        name="create_checkout_session",
    ),
    path(
        "subscriptions/success/",
        stripe_views.subscription_success,
        name="subscription_success",
    ),
    path(
        "subscriptions/manage/",
        stripe_views.manage_subscription,
        name="manage_subscription",
    ),
    path("stripe/webhook/", stripe_views.stripe_webhook, name="stripe_webhook"),
    path("post/<uuid:uuid>/purchase/", views.post_purchase, name="post_purchase"),
    path(
        "post/<uuid:uuid>/purchase/confirm/",
        views.post_purchase_confirm,
        name="post_purchase_confirm",
    ),
    path(
        "post/<uuid:uuid>/purchase/balance/",
        views.post_purchase_from_balance,
        name="post_purchase_balance",
    ),
    path(
        "post/<uuid:uuid>/access-check/",
        views.post_access_check,
        name="post_access_check",
    ),
    path("my-purchases/", views.my_purchases, name="my_purchases"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
