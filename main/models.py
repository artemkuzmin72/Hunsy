from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        """
        Creates and saves a User with the given phone and password.
        """
        if not phone:
            raise ValueError('Users must have a phone number')
        
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        """
        Creates and saves a superuser with the given phone and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(phone, password, **extra_fields)

class User(AbstractUser):
    username = None
    phone = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_subscribed = models.BooleanField(default=False)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Баланс пользователя
    total_purchases = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Всего покупок

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone
    
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinLengthValidator
import uuid

User = get_user_model()

class Post(models.Model):
    """Основная модель поста (обертка для версий)"""
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('published', 'Опубликован'),
        ('archived', 'В архиве'),
    ]

    ACCESS_TYPES = [
        ('free', 'Бесплатный'),
        ('paid_once', 'Разовый платёж'),
        ('subscription', 'По подписке'),
    ]
    
    # Основная информация
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES, default='free')
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                help_text="Цена для разового доступа")
    required_subscription = models.ForeignKey('SubscriptionPlan', on_delete=models.SET_NULL, 
                                             null=True, blank=True, 
                                             help_text="Требуемый план подписки")
    
    # Кто купил доступ
    purchased_by = models.ManyToManyField(User, through='PostPurchase', 
                                         related_name='purchased_posts')
    
    # Текущая активная версия
    current_version = models.ForeignKey(
        'PostVersion', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='+'
    )
    
    # Статус
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Настройки
    is_featured = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['author', 'status']),
            models.Index(fields=['-published_at']),
        ]
    
    def __str__(self):
        return f"{self.author.phone} - {self.current_version.title if self.current_version else 'Без названия'}"
    
    def publish(self):
        """Публикация поста"""
        self.status = 'published'
        self.published_at = timezone.now()
        self.save()
    
    def archive(self):
        """Архивация поста"""
        self.status = 'archived'
        self.save()
    
    def get_version(self, version_id=None):
        """Получить конкретную версию или текущую"""
        if version_id:
            return self.versions.filter(id=version_id).first()
        return self.current_version
    
    def get_all_versions(self):
        """Получить все версии поста"""
        return self.versions.all().order_by('-created_at')
    
    def create_version(self, title, content, summary='', meta_description='', language='ru'):
        """Создать новую версию поста"""
        version = PostVersion.objects.create(
            post=self,
            title=title,
            content=content,
            summary=summary,
            meta_description=meta_description,
            language=language,
            version_number=self.versions.count() + 1,
            created_by=self.author
        )
        
        # Если это первая версия, делаем её текущей
        if self.versions.count() == 1:
            self.current_version = version
            self.save()
        
        return version
    
    def set_current_version(self, version):
        """Установить активную версию"""
        if version.post != self:
            raise ValueError("Версия не принадлежит этому посту")
        self.current_version = version
        self.save()

    def can_access(self, user):
        """Проверка, имеет ли пользователь доступ к посту"""
        # Бесплатные посты доступны всем
        if self.access_type == 'free':
            return True
        
        # Для остальных типов доступа нужен авторизованный пользователь
        if not user or not user.is_authenticated:
            return False
        
        if self.access_type == 'paid_once':
            return self.purchased_by.filter(id=user.id).exists()
        
        if self.access_type == 'subscription' and self.required_subscription:
            return user.subscriptions.filter(
                plan=self.required_subscription,
                status='active',
                current_period_end__gt=timezone.now()
            ).exists()
        
        return False
    
    def get_price_display(self):
        """Отображение цены"""
        if self.access_type == 'free':
            return "Бесплатно"
        elif self.access_type == 'paid_once':
            return f"${self.price} (разовый платёж)"
        elif self.access_type == 'subscription':
            return f"Требуется подписка: {self.required_subscription.name if self.required_subscription else 'Не указана'}"
        return ""

class PostVersion(models.Model):
    """Модель версии поста"""
    LANGUAGE_CHOICES = [
        ('ru', 'Русский'),
        ('en', 'Английский'),
        ('kk', 'Казахский'),
    ]
    
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='versions')
    
    # Контент версии
    title = models.CharField(max_length=200, validators=[MinLengthValidator(3)])
    content = models.TextField(validators=[MinLengthValidator(10)])
    summary = models.CharField(max_length=500, blank=True, help_text="Краткое описание")
    featured_image = models.ImageField(upload_to='posts/', null=True, blank=True)
    
    # Метаданные
    meta_description = models.CharField(max_length=160, blank=True)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='ru')
    
    # Версионирование
    version_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Изменения (для отслеживания правок)
    change_summary = models.CharField(max_length=200, blank=True, 
                                      help_text="Краткое описание изменений")
    
    class Meta:
        ordering = ['-version_number']
        unique_together = ['post', 'version_number']
        indexes = [
            models.Index(fields=['post', 'language']),
        ]
    
    def __str__(self):
        return f"v{self.version_number}: {self.title}"
    
    def get_absolute_url(self):
        return f"/post/{self.post.uuid}/version/{self.id}/"
    
    def get_previous_version(self):
        """Получить предыдущую версию"""
        return self.post.versions.filter(
            version_number__lt=self.version_number
        ).order_by('-version_number').first()
    
    def get_next_version(self):
        """Получить следующую версию"""
        return self.post.versions.filter(
            version_number__gt=self.version_number
        ).order_by('version_number').first()

class PostMedia(models.Model):
    """Медиафайлы для постов"""
    MEDIA_TYPES = [
        ('image', 'Изображение'),
        ('video', 'Видео'),
        ('audio', 'Аудио'),
        ('file', 'Файл'),
    ]
    
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='media')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    file = models.FileField(upload_to='post_media/')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    caption = models.CharField(max_length=200, blank=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'uploaded_at']
    
    def __str__(self):
        return f"{self.media_type} for {self.post.uuid}"
    
class PostPurchase(models.Model):
    """Модель для отслеживания покупок постов"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_purchases')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='purchases')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payment_intent_id = models.CharField(max_length=100, unique=True)
    purchased_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'post']  # Пользователь может купить пост только раз
    
    def __str__(self):
        return f"{self.user.phone} - {self.post.current_version.title} - ${self.amount}"
    
class SubscriptionPlan(models.Model):
    """Модель для планов подписки"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stripe_price_id_monthly = models.CharField(max_length=100, blank=True)
    stripe_price_id_yearly = models.CharField(max_length=100, blank=True)
    features = models.JSONField(default=list)  
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    accessible_posts = models.ManyToManyField(Post, blank=True, related_name='subscription_plans')
    
    def get_monthly_price_display(self):
        return f"${self.price_monthly}/месяц"
    
    def get_yearly_price_display(self):
        return f"${self.price_yearly}/год"
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['sort_order']

class Subscription(models.Model):
    """Модель для подписок пользователей"""
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('canceled', 'Отменена'),
        ('past_due', 'Просрочена'),
        ('trialing', 'Пробный период'),
        ('incomplete', 'Неполная'),
        ('incomplete_expired', 'Истекла'),
    ]
    
    user = models.ForeignKey('main.User', on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    stripe_subscription_id = models.CharField(max_length=100, unique=True)
    stripe_customer_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='incomplete')
    
    start_date = models.DateTimeField(default=timezone.now)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.phone} - {self.plan.name}"
    
    def is_active(self):
        return self.status == 'active' and self.current_period_end > timezone.now()

class Payment(models.Model):
    """Модель для отслеживания платежей"""
    user = models.ForeignKey('main.User', on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, related_name='payments')
    stripe_payment_intent_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='usd')
    status = models.CharField(max_length=20) 
    payment_method = models.CharField(max_length=50, blank=True)
    receipt_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.phone} - {self.amount} {self.currency}"