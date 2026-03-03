from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from getpass import getpass
import sys

User = get_user_model()


class Command(BaseCommand):
    help = "Создание суперпользователя с номером телефона"

    def add_arguments(self, parser):
        parser.add_argument("--phone", type=str, help="Номер телефона")
        parser.add_argument("--password", type=str, help="Пароль")

    def handle(self, *args, **options):
        phone = options.get("phone")
        password = options.get("password")

        # Запрашиваем номер телефона, если не указан
        if not phone:
            phone = input("Phone: ")

        # Запрашиваем пароль, если не указан
        if not password:
            password = getpass("Password: ")
            password2 = getpass("Password (again): ")

            if password != password2:
                self.stderr.write(self.style.ERROR("Пароли не совпадают"))
                sys.exit(1)

        # Проверяем минимальную длину пароля (опционально)
        if len(password) < 8:
            self.stderr.write(
                self.style.ERROR("Пароль должен быть не менее 8 символов")
            )
            sys.exit(1)

        try:
            # Проверяем, существует ли уже пользователь
            if User.objects.filter(phone=phone).exists():
                self.stderr.write(
                    self.style.ERROR(f"Пользователь с номером {phone} уже существует")
                )
                sys.exit(1)

            # Создаем суперпользователя
            User.objects.create_superuser(phone=phone, password=password)
            self.stdout.write(
                self.style.SUCCESS(f"Суперпользователь {phone} успешно создан")
            )

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Ошибка при создании суперпользователя: {e}")
            )
            sys.exit(1)
