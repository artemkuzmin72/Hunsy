import stripe
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from .models import Post
from .forms import RegisterForm

stripe.api_key = settings.STRIPE_SECRET_KEY


def post_list(request):
    posts = Post.objects.all()
    return render(request, "post_list.html", {"posts": posts})


def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)

    if post.is_paid:
        if not request.user.is_authenticated:
            return redirect("post_list")
        if not request.user.is_subscribed:
            return redirect("subscribe")

    return render(request, "post_detail.html", {"post": post})


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("login")
    else:
        form = RegisterForm()

    return render(request, "register.html", {"form": form})


@login_required
def subscribe(request):
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "One-time subscription",
                },
                "unit_amount": 1000,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=request.build_absolute_uri("/success/"),
        cancel_url=request.build_absolute_uri("/"),
    )

    return redirect(checkout_session.url)


@login_required
def payment_success(request):
    request.user.is_subscribed = True
    request.user.save()
    return redirect("post_list")