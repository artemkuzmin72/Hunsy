from django.core.management.base import BaseCommand
from main.models import SubscriptionPlan

class Command(BaseCommand):
    help = 'Создание тестовых планов подписки'
    
    def handle(self, *args, **options):
        plans = [
            {
                'name': 'Базовый',
                'slug': 'basic',
                'description': 'Все необходимое для начала',
                'price_monthly': 9.99,
                'price_yearly': 99.99,
                'stripe_price_id_monthly': 'price_basic_monthly',  # Замените на реальные ID
                'stripe_price_id_yearly': 'price_basic_yearly',    # из Stripe Dashboard
                'features': [
                    'Доступ к основным функциям',
                    'Поддержка по email',
                    '10 проектов',
                    '1 ГБ хранилища'
                ],
                'sort_order': 1
            },
            {
                'name': 'Премиум',
                'slug': 'premium',
                'description': 'Для профессионалов',
                'price_monthly': 19.99,
                'price_yearly': 199.99,
                'stripe_price_id_monthly': 'price_premium_monthly',  # Замените на реальные ID
                'stripe_price_id_yearly': 'price_premium_yearly',    # из Stripe Dashboard
                'features': [
                    'Все функции базового плана',
                    'Приоритетная поддержка',
                    'Неограниченные проекты',
                    '10 ГБ хранилища',
                    'API доступ'
                ],
                'sort_order': 2
            }
        ]
        
        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.update_or_create(
                slug=plan_data['slug'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'План "{plan.name}" создан'))
            else:
                self.stdout.write(self.style.SUCCESS(f'План "{plan.name}" обновлен'))