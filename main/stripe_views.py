import stripe
import json
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .models import SubscriptionPlan, Subscription, Payment, User

stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def subscription_plans(request):
    """Отображение доступных планов подписки"""
    plans = SubscriptionPlan.objects.filter(is_active=True)
    return render(request, 'subscription_plans.html', {
        'plans': plans,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY
    })

@login_required
def create_checkout_session(request, plan_slug, interval):
    """Создание Stripe Checkout сессии для подписки"""
    plan = get_object_or_404(SubscriptionPlan, slug=plan_slug, is_active=True)
    
    # Выбираем правильный Price ID
    if interval == 'monthly':
        price_id = plan.stripe_price_id_monthly
    elif interval == 'yearly':
        price_id = plan.stripe_price_id_yearly
    else:
        messages.error(request, 'Неверный интервал подписки')
        return redirect('subscription_plans')
    
    if not price_id:
        messages.error(request, 'Этот план временно недоступен')
        return redirect('subscription_plans')
    
    try:
        # Создаем или получаем существующего Stripe customer
        if not request.user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=request.user.email or f"{request.user.phone}@example.com",
                phone=request.user.phone,
                metadata={'user_id': request.user.id}
            )
            request.user.stripe_customer_id = customer.id
            request.user.save()
        else:
            customer_id = request.user.stripe_customer_id
        
        # Создаем Checkout Session
        checkout_session = stripe.checkout.Session.create(
            customer=request.user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.build_absolute_uri(reverse('subscription_success')) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri(reverse('subscription_plans')),
            metadata={
                'user_id': request.user.id,
                'plan_id': plan.id,
                'interval': interval
            }
        )
        
        return redirect(checkout_session.url, code=303)
        
    except Exception as e:
        messages.error(request, f'Ошибка при создании сессии оплаты: {str(e)}')
        return redirect('subscription_plans')

@login_required
def subscription_success(request):
    """Страница успешной подписки"""
    session_id = request.GET.get('session_id')
    
    if not session_id:
        return redirect('subscription_plans')
    
    try:
        # Получаем информацию о сессии из Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        subscription_id = checkout_session.subscription
        
        # Получаем информацию о подписке
        subscription_data = stripe.Subscription.retrieve(subscription_id)
        
        # Получаем план подписки из metadata
        plan_id = checkout_session.metadata.get('plan_id')
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        # Создаем или обновляем подписку в БД
        subscription, created = Subscription.objects.update_or_create(
            stripe_subscription_id=subscription_id,
            defaults={
                'user': request.user,
                'plan': plan,
                'stripe_customer_id': request.user.stripe_customer_id,
                'status': subscription_data.status,
                'current_period_start': datetime.fromtimestamp(subscription_data.current_period_start),
                'current_period_end': datetime.fromtimestamp(subscription_data.current_period_end),
                'trial_start': datetime.fromtimestamp(subscription_data.trial_start) if subscription_data.trial_start else None,
                'trial_end': datetime.fromtimestamp(subscription_data.trial_end) if subscription_data.trial_end else None,
                'cancel_at_period_end': subscription_data.cancel_at_period_end,
            }
        )
        
        return render(request, 'subscription_success.html', {
            'subscription': subscription
        })
        
    except Exception as e:
        messages.error(request, f'Ошибка при обработке подписки: {str(e)}')
        return redirect('subscription_plans')

@login_required
def manage_subscription(request):
    """Управление подпиской"""
    try:
        subscription = Subscription.objects.filter(
            user=request.user, 
            status='active'
        ).first()
        
        if not subscription:
            return redirect('subscription_plans')
        
        # Получаем данные из Stripe
        subscription_data = stripe.Subscription.retrieve(
            subscription.stripe_subscription_id
        )
        
        # Получаем портал управления подпиской
        if request.method == 'POST':
            # Создаем сессию портала
            session = stripe.billing_portal.Session.create(
                customer=request.user.stripe_customer_id,
                return_url=request.build_absolute_uri(reverse('profile'))
            )
            return redirect(session.url)
        
        return render(request, 'manage_subscription.html', {
            'subscription': subscription,
            'subscription_data': subscription_data
        })
        
    except Exception as e:
        messages.error(request, f'Ошибка: {str(e)}')
        return redirect('profile')

@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Webhook для обработки событий от Stripe"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)
    
    # Обработка событий
    if event['type'] == 'invoice.payment_succeeded':
        # Платеж прошел успешно
        handle_payment_succeeded(event['data']['object'])
        
    elif event['type'] == 'invoice.payment_failed':
        # Платеж не прошел
        handle_payment_failed(event['data']['object'])
        
    elif event['type'] == 'customer.subscription.updated':
        # Подписка обновлена
        handle_subscription_updated(event['data']['object'])
        
    elif event['type'] == 'customer.subscription.deleted':
        # Подписка отменена
        handle_subscription_deleted(event['data']['object'])
    
    return HttpResponse(status=200)

def handle_payment_succeeded(invoice):
    """Обработка успешного платежа"""
    subscription_id = invoice.get('subscription')
    customer_id = invoice.get('customer')
    
    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id
        )
        
        # Создаем запись о платеже
        Payment.objects.create(
            user=subscription.user,
            subscription=subscription,
            stripe_payment_intent_id=invoice.get('payment_intent'),
            amount=invoice.get('total') / 100,  # Stripe возвращает в центах
            currency=invoice.get('currency'),
            status='succeeded',
            receipt_url=invoice.get('receipt_url', '')
        )
        
    except Subscription.DoesNotExist:
        pass

def handle_payment_failed(invoice):
    """Обработка неудачного платежа"""
    subscription_id = invoice.get('subscription')
    
    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=subscription_id
        )
        # Обновляем статус подписки
        subscription.status = 'past_due'
        subscription.save()
        
        # Отправляем уведомление пользователю
        # send_payment_failed_notification(subscription.user)
        
    except Subscription.DoesNotExist:
        pass

def handle_subscription_updated(subscription_data):
    """Обработка обновления подписки"""
    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=subscription_data['id']
        )
        
        subscription.status = subscription_data['status']
        subscription.current_period_start = datetime.fromtimestamp(
            subscription_data['current_period_start']
        )
        subscription.current_period_end = datetime.fromtimestamp(
            subscription_data['current_period_end']
        )
        subscription.cancel_at_period_end = subscription_data['cancel_at_period_end']
        subscription.save()
        
    except Subscription.DoesNotExist:
        pass

def handle_subscription_deleted(subscription_data):
    """Обработка удаления подписки"""
    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=subscription_data['id']
        )
        
        subscription.status = 'canceled'
        subscription.ended_at = datetime.fromtimestamp(subscription_data['ended_at'])
        subscription.save()
        
    except Subscription.DoesNotExist:
        pass