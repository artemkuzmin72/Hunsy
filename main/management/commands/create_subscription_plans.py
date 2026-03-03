from django.core.management.base import BaseCommand
from main.models import SubscriptionPlan


class Command(BaseCommand):
    help = "Создание тестовых планов подписки"

    def handle(self, *args, **options):
        plans = [
            {
                "name": "Базовый",
                "slug": "basic",
                "description": "Все необходимое для начала",
                "price_monthly": 9.99,
                "price_yearly": 80.00,
                "stripe_price_id_monthly": "prod_U4onm6A0wAmXys",  
                "stripe_price_id_yearly": "prod_U4onO6x7RKCGYf",  
                "features": [
                    "Доступ к основным функциям",
                    "Поддержка по email",
                ],
                "sort_order": 1,
            },
            {
                "name": "Премиум",
                "slug": "premium",
                "description": "Для профессионалов",
                "price_monthly": 19.99,
                "price_yearly": 150.00,
                "stripe_price_id_monthly": "prod_U4ooDHywuikYo1",  
                "stripe_price_id_yearly": "prod_U4ooskdri9VHby",  
                "features": [
                    "Все функции базового плана",
                    "Приоритетная поддержка",
                    "Неограниченные проекты",
                    "Доступ к платному контенту"
                ],
                "sort_order": 2,
            },
        ]

        for plan_data in plans:
            plan, created = SubscriptionPlan.objects.update_or_create(
                slug=plan_data["slug"], defaults=plan_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'План "{plan.name}" создан'))
            else:
                self.stdout.write(self.style.SUCCESS(f'План "{plan.name}" обновлен'))
