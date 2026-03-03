from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from .models import User, Post, PostVersion, PostMedia, SubscriptionPlan, Subscription, Payment, PostPurchase, Subscription
from .forms import (
    UserRegistrationForm, CustomAuthenticationForm, 
    PostCreateForm, PostVersionForm, PostSettingsForm
)
import stripe
from django.conf import settings
from datetime import datetime
from django.views.decorators.http import require_POST


def register(request):
    """Регистрация пользователя"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('index')
    else:
        form = UserRegistrationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    """Вход в систему"""
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, 'Вы успешно вошли в систему!')
                return redirect('index')
        messages.error(request, 'Неверный номер телефона или пароль')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    """Выход из системы"""
    logout(request)
    messages.success(request, 'Вы вышли из системы')
    return redirect('index')

def index(request):
    """Главная страница"""
    # Показываем все опубликованные посты (бесплатные и платные)
    # Но для платных показываем только превью
    recent_posts = Post.objects.filter(status='published').select_related('current_version')[:6]
    
    # Добавляем информацию о типе доступа для каждого поста
    for post in recent_posts:
        post.access_display = post.get_price_display()
    
    return render(request, 'index.html', {
        'recent_posts': recent_posts
    })

@login_required
def profile(request):
    """Профиль пользователя"""
    user_posts = Post.objects.filter(author=request.user).count()
    active_subscription = Subscription.objects.filter(
        user=request.user, 
        status='active'
    ).first()
    
    return render(request, 'profile.html', {
        'user': request.user,
        'user_posts': user_posts,
        'active_subscription': active_subscription
    })


@login_required
def post_list(request):
    """Список постов пользователя"""
    posts = Post.objects.filter(author=request.user).select_related('current_version')
    return render(request, 'post_list.html', {'posts': posts})

@login_required
def post_create(request):
    """Создание нового поста"""
    if request.method == 'POST':
        form = PostCreateForm(request.POST, request.FILES)
        if form.is_valid():
            # Создаем пост
            post = Post.objects.create(author=request.user)
            
            # Создаем первую версию
            version = post.create_version(
                title=form.cleaned_data['title'],
                content=form.cleaned_data['content'],
                summary=form.cleaned_data.get('summary', ''),
                language=form.cleaned_data['language']
            )
            
            # Добавляем изображение если есть
            if form.cleaned_data.get('featured_image'):
                version.featured_image = form.cleaned_data['featured_image']
                version.save()
            
            messages.success(request, 'Пост успешно создан!')
            return redirect('post_detail', uuid=post.uuid)
    else:
        form = PostCreateForm()
    
    return render(request, 'post_create.html', {'form': form})

def post_detail(request, uuid):
    """Просмотр поста с проверкой доступа"""
    post = get_object_or_404(Post, uuid=uuid)
    
    # Проверяем доступ
    can_access = post.can_access(request.user)
    
    # Если пост платный и нет доступа
    if not can_access:
        if post.access_type == 'paid_once':
            if not request.user.is_authenticated:
                messages.warning(request, 'Для покупки этого поста необходимо войти в систему')
                return redirect(f'{reverse("login")}?next={request.path}')
            return render(request, 'post_locked.html', {'post': post})
        elif post.access_type == 'subscription':
            return render(request, 'post_subscription_required.html', {
                'post': post,
                'required_plan': post.required_subscription
            })
        # Для бесплатных постов всегда показываем содержимое
        # Этот блок не должен выполняться для free постов
    
    # Если доступ есть, показываем пост
    if post.status == 'published':
        post.view_count += 1
        post.save(update_fields=['view_count'])
    
    # Получаем версию для отображения
    version_id = request.GET.get('version')
    if version_id and request.user == post.author:
        version = post.get_version(version_id)
    else:
        version = post.current_version
    
    versions = None
    if request.user == post.author:
        versions = post.get_all_versions()
    
    return render(request, 'post_detail.html', {
        'post': post,
        'version': version,
        'versions': versions,
        'can_access': can_access,
        'is_purchased': request.user.is_authenticated and post.purchased_by.filter(id=request.user.id).exists()
    })

@login_required
def post_edit(request, uuid):
    """Редактирование поста (создание новой версии)"""
    post = get_object_or_404(Post, uuid=uuid, author=request.user)
    
    if request.method == 'POST':
        form = PostVersionForm(request.POST, request.FILES)
        if form.is_valid():
            # Создаем новую версию
            version = post.create_version(
                title=form.cleaned_data['title'],
                content=form.cleaned_data['content'],
                summary=form.cleaned_data.get('summary', ''),
                language=form.cleaned_data['language']
            )
            
            # Добавляем изображение если есть
            if form.cleaned_data.get('featured_image'):
                version.featured_image = form.cleaned_data['featured_image']
                version.save()
            
            # Сохраняем описание изменений
            if form.cleaned_data.get('change_summary'):
                version.change_summary = form.cleaned_data['change_summary']
                version.save()
            
            messages.success(request, f'Версия {version.version_number} успешно создана!')
            
            # Спрашиваем, сделать ли эту версию текущей
            if request.POST.get('make_current'):
                post.set_current_version(version)
                messages.info(request, 'Новая версия установлена как текущая')
            
            return redirect('post_detail', uuid=post.uuid)
    else:
        # Предзаполняем форму данными из текущей версии
        current = post.current_version
        initial = {
            'title': current.title if current else '',
            'content': current.content if current else '',
            'summary': current.summary if current else '',
            'language': current.language if current else 'ru',
        }
        form = PostVersionForm(initial=initial)
    
    return render(request, 'post_edit.html', {
        'form': form,
        'post': post
    })

@login_required
def post_settings(request, uuid):
    """Настройки поста"""
    post = get_object_or_404(Post, uuid=uuid, author=request.user)
    
    # Создаем формы
    from .forms import PostSettingsForm, PostAccessForm
    
    if request.method == 'POST':
        # Определяем, какая форма была отправлена
        if 'basic_settings' in request.POST:
            basic_form = PostSettingsForm(request.POST, instance=post)
            access_form = PostAccessForm(instance=post)  # Пустая форма для рендера
            if basic_form.is_valid():
                post = basic_form.save()
                if post.status == 'published' and not post.published_at:
                    post.publish()
                messages.success(request, 'Основные настройки сохранены')
                return redirect('post_settings', uuid=post.uuid)
        
        elif 'access_settings' in request.POST:
            access_form = PostAccessForm(request.POST, instance=post)
            basic_form = PostSettingsForm(instance=post)  # Пустая форма для рендера
            if access_form.is_valid():
                access_form.save()
                messages.success(request, 'Настройки доступа сохранены')
                return redirect('post_settings', uuid=post.uuid)
    
    else:
        # GET запрос - создаем обе формы
        basic_form = PostSettingsForm(instance=post)
        access_form = PostAccessForm(instance=post)
    
    return render(request, 'post_settings.html', {
        'post': post,
        'basic_form': basic_form,
        'access_form': access_form,
    })

@login_required
def post_versions(request, uuid):
    """Управление версиями поста"""
    post = get_object_or_404(Post, uuid=uuid, author=request.user)
    versions = post.get_all_versions()
    
    if request.method == 'POST':
        version_id = request.POST.get('version_id')
        action = request.POST.get('action')
        
        version = get_object_or_404(PostVersion, id=version_id, post=post)
        
        if action == 'set_current':
            post.set_current_version(version)
            messages.success(request, f'Версия {version.version_number} установлена как текущая')
        elif action == 'delete':
            if post.versions.count() > 1:
                version.delete()
                messages.success(request, f'Версия {version.version_number} удалена')
            else:
                messages.error(request, 'Нельзя удалить единственную версию поста')
        
        return redirect('post_versions', uuid=post.uuid)
    
    return render(request, 'post_versions.html', {
        'post': post,
        'versions': versions
    })

@login_required
def post_delete(request, uuid):
    """Удаление поста"""
    post = get_object_or_404(Post, uuid=uuid, author=request.user)
    
    if request.method == 'POST':
        post.delete()
        messages.success(request, 'Пост успешно удален')
        return redirect('post_list')
    
    return render(request, 'post_delete.html', {'post': post})

@login_required
def post_media_upload(request, uuid):
    """Загрузка медиафайлов для поста"""
    post = get_object_or_404(Post, uuid=uuid, author=request.user)
    
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        
        # Определяем тип медиа
        file_type = 'file'
        if file.content_type.startswith('image/'):
            file_type = 'image'
        elif file.content_type.startswith('video/'):
            file_type = 'video'
        elif file.content_type.startswith('audio/'):
            file_type = 'audio'
        
        media = PostMedia.objects.create(
            post=post,
            uploaded_by=request.user,
            file=file,
            media_type=file_type,
            caption=request.POST.get('caption', '')
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'media_id': media.id,
                'url': media.file.url,
                'type': media.media_type
            })
        
        messages.success(request, 'Файл успешно загружен')
    
    return redirect('post_detail', uuid=post.uuid)

stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def post_purchase(request, uuid):
    """Покупка доступа к посту"""
    post = get_object_or_404(Post, uuid=uuid, access_type='paid_once')
    
    # Проверяем, не купил ли уже пользователь этот пост
    if post.purchased_by.filter(id=request.user.id).exists():
        messages.info(request, 'У вас уже есть доступ к этому посту')
        return redirect('post_detail', uuid=post.uuid)
    
    if request.method == 'POST':
        try:
            # Создаем PaymentIntent в Stripe
            intent = stripe.PaymentIntent.create(
                amount=int(post.price * 100),  # Stripe работает в центах
                currency='usd',
                customer=request.user.stripe_customer_id if hasattr(request.user, 'stripe_customer_id') else None,
                metadata={
                    'user_id': request.user.id,
                    'post_uuid': str(post.uuid),
                    'post_title': post.current_version.title if post.current_version else 'Post'
                }
            )
            
            return render(request, 'post_payment.html', {
                'post': post,
                'client_secret': intent.client_secret,
                'stripe_public_key': settings.STRIPE_PUBLIC_KEY
            })
            
        except Exception as e:
            messages.error(request, f'Ошибка при создании платежа: {str(e)}')
            return redirect('post_detail', uuid=post.uuid)
    
    return render(request, 'post_checkout.html', {'post': post})

@require_POST
@login_required
def post_purchase_confirm(request, uuid):
    """Подтверждение успешной покупки"""
    post = get_object_or_404(Post, uuid=uuid)
    payment_intent_id = request.POST.get('payment_intent_id')
    amount = request.POST.get('amount')
    
    try:
        # Создаем запись о покупке
        purchase = PostPurchase.objects.create(
            user=request.user,
            post=post,
            amount=amount,
            stripe_payment_intent_id=payment_intent_id
        )
        
        # Обновляем баланс пользователя (опционально)
        request.user.balance -= float(amount)
        request.user.total_purchases += float(amount)
        request.user.save()
        
        messages.success(request, f'Доступ к посту "{post.current_version.title}" успешно получен!')
        
    except Exception as e:
        messages.error(request, f'Ошибка при подтверждении покупки: {str(e)}')
    
    return redirect('post_detail', uuid=post.uuid)

def post_access_check(request, uuid):
    """API для проверки доступа (для AJAX запросов)"""
    post = get_object_or_404(Post, uuid=uuid)
    
    can_access = post.can_access(request.user)
    
    return JsonResponse({
        'can_access': can_access,
        'access_type': post.access_type,
        'price': str(post.price) if post.price else None,
        'requires_auth': not request.user.is_authenticated and post.access_type != 'free'
    })

@login_required
def my_purchases(request):
    """Список купленных постов"""
    purchases = PostPurchase.objects.filter(user=request.user).select_related('post', 'post__current_version')
    return render(request, 'my_purchases.html', {'purchases': purchases})