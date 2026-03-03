from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal
import uuid
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from .models import (
    User, Post, PostVersion, PostPurchase,
    SubscriptionPlan, Subscription, Payment, PostMedia
)
from .forms import (
    UserRegistrationForm, CustomAuthenticationForm,
    PostCreateForm, PostVersionForm, PostSettingsForm,
    PostAccessForm
)

User = get_user_model()

# ============= ТЕСТЫ МОДЕЛЕЙ =============

class UserModelTest(TestCase):
    """Тесты для модели пользователя"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone='+79374515429',
            password='testpass123'
        )
    
    def test_create_user(self):
        """Тест создания обычного пользователя"""
        self.assertEqual(self.user.phone, '+79374515429')
        self.assertTrue(self.user.check_password('testpass123'))
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
    
    def test_create_superuser(self):
        """Тест создания суперпользователя"""
        admin = User.objects.create_superuser(
            phone='+79999999999',
            password='admin123'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
    
    def test_user_str(self):
        """Тест строкового представления"""
        self.assertEqual(str(self.user), '+79374515429')
    
    def test_user_fields_defaults(self):
        """Тест значений по умолчанию"""
        self.assertEqual(self.user.balance, 0)
        self.assertEqual(self.user.total_purchases, 0)
        self.assertIsNone(self.user.stripe_customer_id)


class PostModelTest(TestCase):
    """Тесты для модели поста"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone='+79374515429',
            password='testpass123'
        )
        self.post = Post.objects.create(
            author=self.user,
            status='draft'
        )
    
    def test_create_post(self):
        """Тест создания поста"""
        self.assertEqual(self.post.author, self.user)
        self.assertEqual(self.post.status, 'draft')
        self.assertEqual(self.post.access_type, 'free')
        self.assertIsNone(self.post.price)
        self.assertEqual(self.post.view_count, 0)
    
    def test_create_version(self):
        """Тест создания версии поста"""
        version = self.post.create_version(
            title='Тестовый пост',
            content='Содержание тестового поста',
            summary='Краткое описание'
        )
        
        self.assertEqual(version.post, self.post)
        self.assertEqual(version.title, 'Тестовый пост')
        self.assertEqual(version.content, 'Содержание тестового поста')
        self.assertEqual(version.version_number, 1)
        self.assertEqual(self.post.current_version, version)
    
    def test_create_multiple_versions(self):
        """Тест создания нескольких версий"""
        v1 = self.post.create_version(title='Версия 1', content='Содержание 1')
        v2 = self.post.create_version(title='Версия 2', content='Содержание 2')
        
        self.assertEqual(v1.version_number, 1)
        self.assertEqual(v2.version_number, 2)
        self.assertEqual(self.post.versions.count(), 2)
    
    def test_publish_post(self):
        """Тест публикации поста"""
        self.post.publish()
        self.assertEqual(self.post.status, 'published')
        self.assertIsNotNone(self.post.published_at)
    
    def test_can_access_free_post(self):
        """Тест доступа к бесплатному посту"""
        self.post.access_type = 'free'
        self.post.save()
        
        # Бесплатный пост доступен всем
        self.assertTrue(self.post.can_access(self.user))
        self.assertTrue(self.post.can_access(None))
    
    def test_can_access_paid_post(self):
        """Тест доступа к платному посту"""
        self.post.access_type = 'paid_once'
        self.post.price = Decimal('9.99')
        self.post.save()
        
        # Без покупки нет доступа
        self.assertFalse(self.post.can_access(self.user))
        
        # После покупки есть доступ
        PostPurchase.objects.create(
            user=self.user,
            post=self.post,
            amount=self.post.price,
            stripe_payment_intent_id='pi_test123'
        )
        self.assertTrue(self.post.can_access(self.user))
    
    def test_can_access_subscription_post(self):
        """Тест доступа к посту по подписке"""
        plan = SubscriptionPlan.objects.create(
            name='Премиум',
            slug='premium',
            price_monthly=19.99,
            price_yearly=199.99
        )
        
        self.post.access_type = 'subscription'
        self.post.required_subscription = plan
        self.post.save()
        
        # Без подписки нет доступа
        self.assertFalse(self.post.can_access(self.user))
        
        # Создаем активную подписку
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            stripe_subscription_id='sub_test123',
            stripe_customer_id='cus_test123',
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30)
        )
        
        self.assertTrue(self.post.can_access(self.user))
    
    def test_price_display(self):
        """Тест отображения цены"""
        self.post.access_type = 'free'
        self.assertEqual(self.post.get_price_display(), "Бесплатно")
        
        self.post.access_type = 'paid_once'
        self.post.price = Decimal('9.99')
        self.assertEqual(self.post.get_price_display(), "$9.99 (разовый платёж)")
    
    def test_post_uuid_unique(self):
        """Тест уникальности UUID"""
        post2 = Post.objects.create(author=self.user)
        self.assertNotEqual(self.post.uuid, post2.uuid)


class SubscriptionPlanModelTest(TestCase):
    """Тесты для модели планов подписки"""
    
    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            name='Базовый',
            slug='basic',
            description='Базовый план',
            price_monthly=9.99,
            price_yearly=99.99,
            features=['Функция 1', 'Функция 2']
        )
    
    def test_create_plan(self):
        """Тест создания плана"""
        self.assertEqual(self.plan.name, 'Базовый')
        self.assertEqual(self.plan.price_monthly, 9.99)
        self.assertEqual(self.plan.price_yearly, 99.99)
        self.assertTrue(self.plan.is_active)
    
    def test_price_display(self):
        """Тест отображения цен"""
        self.assertEqual(self.plan.get_monthly_price_display(), "$9.99/месяц")
        self.assertEqual(self.plan.get_yearly_price_display(), "$99.99/год")
    
    def test_str(self):
        """Тест строкового представления"""
        self.assertEqual(str(self.plan), 'Базовый')


# ============= ТЕСТЫ ФОРМ =============

class UserRegistrationFormTest(TestCase):
    """Тесты формы регистрации"""
    
    def test_valid_form(self):
        """Тест валидной формы"""
        form_data = {
            'phone': '+79374515429',
            'password1': 'testpass123',
            'password2': 'testpass123'
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_invalid_form_password_mismatch(self):
        """Тест несовпадающих паролей"""
        form_data = {
            'phone': '+79374515429',
            'password1': 'testpass123',
            'password2': 'different123'
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
    
    def test_duplicate_phone(self):
        """Тест на существующий номер"""
        User.objects.create_user(phone='+79374515429', password='pass123')
        
        form_data = {
            'phone': '+79374515429',
            'password1': 'testpass123',
            'password2': 'testpass123'
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)


class PostCreateFormTest(TestCase):
    """Тесты формы создания поста"""
    
    def test_valid_form(self):
        """Тест валидной формы"""
        form_data = {
            'title': 'Тестовый пост',
            'content': 'Содержание тестового поста' * 10,
            'summary': 'Краткое описание',
            'language': 'ru'
        }
        form = PostCreateForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_invalid_form_short_title(self):
        """Тест слишком короткого заголовка"""
        form_data = {
            'title': 'Те',
            'content': 'Содержание тестового поста' * 10,
            'language': 'ru'
        }
        form = PostCreateForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_invalid_form_short_content(self):
        """Тест слишком короткого содержания"""
        form_data = {
            'title': 'Тестовый пост',
            'content': 'Короткий',
            'language': 'ru'
        }
        form = PostCreateForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('content', form.errors)


# ============= ТЕСТЫ VIEW =============

class AuthViewsTest(TestCase):
    """Тесты для аутентификации"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone='+79374515429',
            password='testpass123'
        )
    
    def test_register_view_get(self):
        """Тест GET запроса на регистрацию"""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'register.html')
    
    def test_register_view_post_valid(self):
        """Тест POST запроса с валидными данными"""
        response = self.client.post(reverse('register'), {
            'phone': '+79999999999',
            'password1': 'testpass123',
            'password2': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertTrue(User.objects.filter(phone='+79999999999').exists())
    
    def test_login_view_get(self):
        """Тест GET запроса на вход"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')
    
    def test_login_view_post_valid(self):
        """Тест POST запроса с правильными данными"""
        response = self.client.post(reverse('login'), {
            'username': '+79374515429',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_logout_view(self):
        """Тест выхода из системы"""
        self.client.login(username='+79374515429', password='testpass123')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)


class PostViewsTest(TestCase):
    """Тесты для постов"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone='+79374515429',
            password='testpass123'
        )
        self.post = Post.objects.create(author=self.user)
        self.version = self.post.create_version(
            title='Тестовый пост',
            content='Содержание тестового поста'
        )
        self.post.publish()
    
    def test_post_list_view_authenticated(self):
        """Тест списка постов для авторизованного пользователя"""
        self.client.login(username='+79374515429', password='testpass123')
        response = self.client.get(reverse('post_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'post_list.html')
    
    def test_post_list_view_unauthenticated(self):
        """Тест списка постов для неавторизованного пользователя"""
        response = self.client.get(reverse('post_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_post_detail_view_free(self):
        """Тест просмотра бесплатного поста"""
        response = self.client.get(reverse('post_detail', args=[self.post.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый пост')
    
    def test_post_create_view_get(self):
        """Тест GET запроса на создание поста"""
        self.client.login(username='+79374515429', password='testpass123')
        response = self.client.get(reverse('post_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'post_create.html')
    
    def test_post_create_view_post(self):
        """Тест создания поста"""
        self.client.login(username='+79374515429', password='testpass123')
        response = self.client.post(reverse('post_create'), {
            'title': 'Новый пост',
            'content': 'Содержание нового поста' * 10,
            'language': 'ru'
        })
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertTrue(Post.objects.filter(author=self.user).count() > 1)
    
    @patch('stripe.PaymentIntent.create')
    def test_post_purchase_view(self, mock_stripe):
        """Тест покупки поста"""
        self.client.login(username='+79374515429', password='testpass123')
        
        self.post.access_type = 'paid_once'
        self.post.price = 9.99
        self.post.save()
        
        mock_stripe.return_value = MagicMock(
            client_secret='test_secret_123'
        )
        
        response = self.client.post(reverse('post_purchase', args=[self.post.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'post_payment.html')
    
    def test_post_settings_view(self):
        """Тест настроек поста"""
        self.client.login(username='+79374515429', password='testpass123')
        response = self.client.get(reverse('post_settings', args=[self.post.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'post_settings.html')
    
    def test_post_versions_view(self):
        """Тест управления версиями"""
        self.client.login(username='+79374515429', password='testpass123')
        response = self.client.get(reverse('post_versions', args=[self.post.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'post_versions.html')
    
    def test_post_delete_view(self):
        """Тест удаления поста"""
        self.client.login(username='+79374515429', password='testpass123')
        response = self.client.post(reverse('post_delete', args=[self.post.uuid]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Post.objects.filter(id=self.post.id).exists())


class SubscriptionViewsTest(TestCase):
    """Тесты для подписок"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone='+79374515429',
            password='testpass123'
        )
        self.plan = SubscriptionPlan.objects.create(
            name='Премиум',
            slug='premium',
            price_monthly=19.99,
            price_yearly=199.99,
            stripe_price_id_monthly='price_monthly_123',
            stripe_price_id_yearly='price_yearly_123'
        )
    
    def test_subscription_plans_view_unauthenticated(self):
        """Тест просмотра планов подписки без авторизации"""
        response = self.client.get(reverse('subscription_plans'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_subscription_plans_view_authenticated(self):
        """Тест просмотра планов подписки с авторизацией"""
        self.client.login(username='+79374515429', password='testpass123')
        response = self.client.get(reverse('subscription_plans'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'subscription_plans.html')
    
    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session(self, mock_stripe):
        """Тест создания сессии checkout"""
        self.client.login(username='+79374515429', password='testpass123')
        
        mock_stripe.return_value = MagicMock(url='https://checkout.stripe.com/test')
        
        response = self.client.get(
            reverse('create_checkout_session', args=['premium', 'monthly'])
        )
        self.assertEqual(response.status_code, 302)  # Redirect to Stripe


class APITests(TestCase):
    """Тесты для API endpoints"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone='+79374515429',
            password='testpass123'
        )
        self.post = Post.objects.create(author=self.user)
        self.version = self.post.create_version(
            title='Тестовый пост',
            content='Содержание'
        )
    
    def test_post_access_check_free(self):
        """Тест API проверки доступа к бесплатному посту"""
        response = self.client.get(
            reverse('post_access_check', args=[self.post.uuid])
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['can_access'])
        self.assertEqual(data['access_type'], 'free')
    
    def test_post_access_check_paid_no_auth(self):
        """Тест API проверки доступа к платному посту без авторизации"""
        self.post.access_type = 'paid_once'
        self.post.price = 9.99
        self.post.save()
        
        response = self.client.get(
            reverse('post_access_check', args=[self.post.uuid])
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertFalse(data['can_access'])
        self.assertTrue(data['requires_auth'])

    def test_post_access_check_paid_with_auth(self):
        """Проверка доступа к платному посту для авторизованного"""
        self.post.access_type = 'paid_once'
        self.post.price = 9.99
        self.post.save()
        PostPurchase.objects.create(user=self.user, post=self.post, amount=self.post.price, stripe_payment_intent_id='pi')
        self.client.login(username=self.user.phone, password='testpass123')
        resp = self.client.get(reverse('post_access_check', args=[self.post.uuid]))
        data = json.loads(resp.content)
        self.assertTrue(data['can_access'])

    def test_post_access_check_subscription_with_auth(self):
        """Проверка доступа к посту по подписке для авторизованного"""
        plan = SubscriptionPlan.objects.create(name='S', slug='s', price_monthly=1, price_yearly=10)
        self.post.access_type = 'subscription'
        self.post.required_subscription = plan
        self.post.save()
        Subscription.objects.create(user=self.user, plan=plan, stripe_subscription_id='sid', stripe_customer_id='cid', status='active', current_period_start=timezone.now(), current_period_end=timezone.now()+timedelta(days=1))
        self.client.login(username=self.user.phone, password='testpass123')
        resp = self.client.get(reverse('post_access_check', args=[self.post.uuid]))
        data = json.loads(resp.content)
        self.assertTrue(data['can_access'])


# ============= ТЕСТЫ КОМАНД =============

from django.core.management import call_command
from io import StringIO

class ManagementCommandsTest(TestCase):
    """Тесты management команд"""
    
    def test_create_subscription_plans_command(self):
        """Тест команды создания планов подписки"""
        out = StringIO()
        call_command('create_subscription_plans', stdout=out)
        
        self.assertIn('создан', out.getvalue())
        self.assertTrue(SubscriptionPlan.objects.filter(slug='basic').exists())
        self.assertTrue(SubscriptionPlan.objects.filter(slug='premium').exists())

    def test_create_superuser_command(self):
        """Тест команды создания суперпользователя"""
        out = StringIO()
        # Django's default create_superuser may prompt; pass interactive=False
        call_command('create_superuser', stdout=out, interactive=False, phone='+79123456789', password='pw123')
        self.assertTrue(User.objects.filter(phone='+79123456789').exists())


# ============= ТЕСТЫ БЕЗОПАСНОСТИ =============

class SecurityTests(TestCase):
    """Тесты безопасности"""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            phone='+79374515429',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            phone='+79999999999',
            password='testpass123'
        )
        self.post = Post.objects.create(author=self.user1)
        self.version = self.post.create_version(
            title='Личный пост',
            content='Только для автора'
        )
    
    def test_user_cannot_edit_others_post(self):
        """Тест: пользователь не может редактировать чужой пост"""
        self.client.login(username='+79999999999', password='testpass123')
        response = self.client.get(reverse('post_edit', args=[self.post.uuid]))
        self.assertEqual(response.status_code, 404)  # Should be 404 or 403
    
    def test_user_cannot_delete_others_post(self):
        """Тест: пользователь не может удалить чужой пост"""
        self.client.login(username='+79999999999', password='testpass123')
        response = self.client.post(reverse('post_delete', args=[self.post.uuid]))
        self.assertEqual(response.status_code, 404)
    
# ============= ТЕСТЫ ПРОИЗВОДИТЕЛЬНОСТИ =============

class PerformanceTests(TestCase):
    """Тесты производительности"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            phone='+79374515429',
            password='testpass123'
        )
        
        # Создаем 10 постов
        for i in range(10):
            post = Post.objects.create(author=self.user)
            post.create_version(
                title=f'Пост {i}',
                content=f'Содержание поста {i}'
            )

    def test_bulk_posts_created(self):
        """Проверяем, что при setup созданы 10 постов"""
        self.assertEqual(Post.objects.filter(author=self.user).count(), 10)
        for post in Post.objects.filter(author=self.user):
            self.assertIsNotNone(post.current_version)


# ===== дополнительные тесты моделей =====

class AdditionalModelTests(TestCase):
    def test_create_user_without_phone_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(phone='', password='pw')

    def test_post_archive_and_versions_methods(self):
        user = User.objects.create_user(phone='+70000000000', password='pw')
        post = Post.objects.create(author=user)
        post.publish()
        self.assertEqual(post.status, 'published')
        post.archive()
        self.assertEqual(post.status, 'archived')
        v1 = post.create_version(title='t', content='content12345')
        v2 = post.create_version(title='t2', content='content67890')
        self.assertEqual(post.get_version(v1.id), v1)
        self.assertEqual(post.get_version(), post.current_version)
        self.assertEqual(list(post.get_all_versions()), [v2, v1])
        post.set_current_version(v1)
        self.assertEqual(post.current_version, v1)
        other_user = User.objects.create_user(phone='+71111111111', password='pw')
        other_post = Post.objects.create(author=other_user)
        other_v = other_post.create_version(title='x', content='contentfoo')
        with self.assertRaises(ValueError):
            post.set_current_version(other_v)
        post.access_type = 'subscription'
        post.required_subscription = None
        self.assertIn('Не указана', post.get_price_display())

    def test_postmedia_and_postpurchase_str(self):
        user = User.objects.create_user(phone='+72222222222', password='pw')
        post = Post.objects.create(author=user)
        post.create_version(title='t', content='content12345')
        media = PostMedia.objects.create(post=post, uploaded_by=user, file='file.jpg', media_type='image')
        self.assertIn('image for', str(media))
        purchase = PostPurchase.objects.create(user=user, post=post, amount=Decimal('5.00'), stripe_payment_intent_id='pi1')
        self.assertIn(user.phone, str(purchase))

    def test_subscription_is_active_and_payment_str(self):
        user = User.objects.create_user(phone='+73333333333', password='pw')
        plan = SubscriptionPlan.objects.create(name='P', slug='p', description='', price_monthly=1, price_yearly=10)
        sub = Subscription.objects.create(user=user, plan=plan, stripe_subscription_id='sub1', stripe_customer_id='cus', status='active', current_period_start=timezone.now()-timedelta(days=1), current_period_end=timezone.now()+timedelta(days=1))
        self.assertTrue(sub.is_active())
        sub.status = 'canceled'
        sub.save()
        self.assertFalse(sub.is_active())
        payment = Payment.objects.create(user=user, subscription=sub, stripe_payment_intent_id='pi2', amount=Decimal('2.00'), currency='usd', status='succeeded')
        self.assertIn('usd', str(payment))

class FormExtraTests(TestCase):
    def test_custom_authentication_form(self):
        user = User.objects.create_user(phone='+74444444444', password='pw123')
        data = {'username': '+74444444444', 'password': 'pw123'}
        form = CustomAuthenticationForm(request=None, data=data)
        self.assertTrue(form.is_valid())
        data_wrong = {'username': '+74444444444', 'password': 'wrong'}
        form2 = CustomAuthenticationForm(request=None, data=data_wrong)
        self.assertFalse(form2.is_valid())

    def test_post_version_form_valid(self):
        user = User.objects.create_user(phone='+75555555555', password='pw123')
        post = Post.objects.create(author=user)
        form_data = {'title': 'abc', 'content': 'abcdefghijk', 'language': 'ru'}
        form = PostVersionForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_settings_and_access_forms(self):
        form = PostSettingsForm(data={'is_featured': True, 'allow_comments': False, 'status': 'draft'})
        self.assertTrue(form.is_valid())
        plan = SubscriptionPlan.objects.create(name='X', slug='x', description='', price_monthly=1, price_yearly=10)
        form2 = PostAccessForm(data={'access_type': 'subscription', 'price': '', 'required_subscription': plan.id})
        self.assertTrue(form2.is_valid())

class StripeViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(phone='+76666666666', password='pw123')
        self.plan = SubscriptionPlan.objects.create(name='Test', slug='t', price_monthly=5, price_yearly=50)

    def test_create_checkout_session_invalid_interval(self):
        self.client.login(username=self.user.phone, password='pw123')
        response = self.client.get(reverse('create_checkout_session', args=['t', 'weekly']))
        self.assertEqual(response.status_code, 302)

    def test_create_checkout_no_price_id(self):
        self.client.login(username=self.user.phone, password='pw123')
        response = self.client.get(reverse('create_checkout_session', args=['t', 'monthly']))
        self.assertEqual(response.status_code, 302)

    @patch('main.stripe_views.stripe.checkout.Session.create')
    def test_create_checkout_exception(self, mock_session):
        self.client.login(username=self.user.phone, password='pw123')
        self.plan.stripe_price_id_monthly = 'price1'
        self.plan.save()
        mock_session.side_effect = Exception('fail')
        response = self.client.get(reverse('create_checkout_session', args=['t', 'monthly']))
        self.assertEqual(response.status_code, 302)

    def test_subscription_success_no_session(self):
        self.client.login(username=self.user.phone, password='pw123')
        response = self.client.get(reverse('subscription_success'))
        self.assertEqual(response.status_code, 302)

    @patch('main.stripe_views.stripe.checkout.Session.retrieve')
    @patch('main.stripe_views.stripe.Subscription.retrieve')
    def test_subscription_success_process(self, mock_sub, mock_sess):
        self.client.login(username=self.user.phone, password='pw123')
        mock_sess.return_value = MagicMock(subscription='sub123', metadata={'plan_id': self.plan.id})
        mock_sub.return_value = MagicMock(status='active', current_period_start=1, current_period_end=2, trial_start=None, trial_end=None, cancel_at_period_end=False)
        self.user.stripe_customer_id = 'cus'
        self.user.save()
        response = self.client.get(reverse('subscription_success') + '?session_id=abc')
        self.assertEqual(response.status_code, 200)

    def test_manage_subscription_no_active(self):
        self.client.login(username=self.user.phone, password='pw123')
        response = self.client.get(reverse('manage_subscription'))
        self.assertEqual(response.status_code, 302)

    @patch('main.stripe_views.stripe.Subscription.retrieve')
    def test_manage_subscription_get(self, mock_sub):
        self.client.login(username=self.user.phone, password='pw123')
        sub = Subscription.objects.create(user=self.user, plan=self.plan, stripe_subscription_id='sub1', stripe_customer_id='cus', status='active', current_period_start=timezone.now(), current_period_end=timezone.now())
        mock_sub.return_value = {'id': 'sub1'}
        response = self.client.get(reverse('manage_subscription'))
        self.assertEqual(response.status_code, 200)

    @patch('main.stripe_views.stripe.billing_portal.Session.create')
    @patch('main.stripe_views.stripe.Subscription.retrieve')
    def test_manage_subscription_post(self, mock_sub, mock_portal):
        self.client.login(username=self.user.phone, password='pw123')
        sub = Subscription.objects.create(user=self.user, plan=self.plan, stripe_subscription_id='sub1', stripe_customer_id='cus', status='active', current_period_start=timezone.now(), current_period_end=timezone.now())
        mock_sub.return_value = {'id': 'sub1'}
        mock_portal.return_value = MagicMock(url='https://portal')
        response = self.client.post(reverse('manage_subscription'))
        self.assertEqual(response.status_code, 302)

    @patch('main.stripe_views.stripe.Subscription.retrieve')
    def test_manage_subscription_exception(self, mock_sub):
        self.client.login(username=self.user.phone, password='pw123')
        sub = Subscription.objects.create(user=self.user, plan=self.plan, stripe_subscription_id='sub1', stripe_customer_id='cus', status='active', current_period_start=timezone.now(), current_period_end=timezone.now())
        mock_sub.side_effect = Exception('err')
        response = self.client.get(reverse('manage_subscription'))
        self.assertEqual(response.status_code, 302)

class StripeWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('stripe_webhook')

    def _post_event(self, event):
        body = json.dumps(event).encode()
        return self.client.post(self.url, body, content_type='application/json', HTTP_STRIPE_SIGNATURE='sig')

    @patch('main.stripe_views.stripe.Webhook.construct_event')
    def test_invalid_payload(self, mock_construct):
        mock_construct.side_effect = ValueError()
        res = self._post_event({'type': 'whatever'})
        self.assertEqual(res.status_code, 400)

    @patch('main.stripe_views.stripe.Webhook.construct_event')
    def test_invalid_signature(self, mock_construct):
        from stripe.error import SignatureVerificationError
        mock_construct.side_effect = SignatureVerificationError('', '')
        res = self._post_event({'type': 'whatever'})
        self.assertEqual(res.status_code, 400)

    @patch('main.stripe_views.stripe.Webhook.construct_event')
    def test_invoice_payment_succeeded(self, mock_construct):
        user = User.objects.create_user(phone='+77777777777', password='pw')
        plan = SubscriptionPlan.objects.create(name='Y', slug='y', description='', price_monthly=1, price_yearly=10)
        sub = Subscription.objects.create(user=user, plan=plan, stripe_subscription_id='sub', stripe_customer_id='cus', status='active', current_period_start=timezone.now(), current_period_end=timezone.now())
        event = {'type': 'invoice.payment_succeeded', 'data': {'object': {'subscription': 'sub', 'customer': 'cus', 'payment_intent': 'pi', 'total': 200, 'currency': 'usd', 'receipt_url': 'url'}}}
        mock_construct.return_value = event
        res = self._post_event(event)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Payment.objects.filter(subscription=sub).exists())

    @patch('main.stripe_views.stripe.Webhook.construct_event')
    def test_invoice_payment_failed(self, mock_construct):
        plan = SubscriptionPlan.objects.create(name='Y2', slug='y2', description='', price_monthly=1, price_yearly=10)
        sub = Subscription.objects.create(user=User.objects.create_user(phone='+78888888888', password='pw'), plan=plan, stripe_subscription_id='sub2', stripe_customer_id='cus', status='active', current_period_start=timezone.now(), current_period_end=timezone.now())
        event = {'type': 'invoice.payment_failed', 'data': {'object': {'subscription': 'sub2'}}}
        mock_construct.return_value = event
        res = self._post_event(event)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'past_due')

    @patch('main.stripe_views.stripe.Webhook.construct_event')
    def test_subscription_updated(self, mock_construct):
        plan = SubscriptionPlan.objects.create(name='Z', slug='z', description='', price_monthly=1, price_yearly=10)
        sub = Subscription.objects.create(user=User.objects.create_user(phone='+79999999998', password='pw'), plan=plan, stripe_subscription_id='sub3', stripe_customer_id='cus', status='active', current_period_start=timezone.now(), current_period_end=timezone.now())
        event = {'type': 'customer.subscription.updated', 'data': {'object': {'id': 'sub3', 'status': 'past_due', 'current_period_start': 1, 'current_period_end': 2, 'cancel_at_period_end': False}}}
        mock_construct.return_value = event
        res = self._post_event(event)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'past_due')

    @patch('main.stripe_views.stripe.Webhook.construct_event')
    def test_subscription_deleted(self, mock_construct):
        plan = SubscriptionPlan.objects.create(name='Z2', slug='z2', description='', price_monthly=1, price_yearly=10)
        sub = Subscription.objects.create(user=User.objects.create_user(phone='+79999999997', password='pw'), plan=plan, stripe_subscription_id='sub4', stripe_customer_id='cus', status='active', current_period_start=timezone.now(), current_period_end=timezone.now())
        event = {'type': 'customer.subscription.deleted', 'data': {'object': {'id': 'sub4', 'ended_at': 1}}}
        mock_construct.return_value = event
        res = self._post_event(event)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'canceled')
