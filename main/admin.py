from django.contrib import admin
from .models import User, Post, Subscription, SubscriptionPlan


class SubscriptionInline(admin.TabularInline):
    model = Subscription
    extra = 0
    fields = (
        "plan",
        "status",
        "current_period_start",
        "current_period_end",
        "cancel_at_period_end",
    )
    readonly_fields = ("stripe_subscription_id", "stripe_customer_id", "created_at", "updated_at")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "phone", "is_active", "is_staff")
    search_fields = ("phone",)
    inlines = [SubscriptionInline]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "uuid", "author", "status", "access_type", "required_subscription")
    list_filter = ("status", "access_type", "required_subscription")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
