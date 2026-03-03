# Hunsy - Платформа для публикации и продажи авторских постов

Hunsy - это веб-приложение на Django, которое позволяет пользователям создавать, публиковать и продавать авторские посты. Платформа поддерживает систему версионности постов, различные типы доступа (бесплатный, разовый платёж, по подписке) и интеграцию с платежной системой Stripe.

## Содержание
- [Технологии](#технологии)
- [Структура проекта](#структура-проекта)
- [Установка](#установка)
- [Настройка](#настройка)
- [Запуск](#запуск)
- [Тестирование](#тестирование)
- [API endpoints](#api-endpoints)
- [Модели данных](#модели-данных)
- [Лицензия](#лицензия)

## Технологии

- **Backend**: Python 3.13, Django 5.2
- **База данных**: SQLite (разработка), PostgreSQL (продакшн)
- **Платежи**: Stripe API
- **Фронтенд**: Bootstrap 5, HTML, JavaScript
- **Тестирование**: Django Test Case, Coverage


## Установка

### Предварительные требования
- Python 3.13 или выше
- pip (менеджер пакетов Python)
- virtualenv (рекомендуется)
- Аккаунт Stripe (для платежей)

### Пошаговая установка

1. **Клонируйте репозиторий**
```bash
git clone https://github.com/yourusername/hunsy.git
cd hunsy
```

2. Создайте виртуальное окружение
```bash
python3 -m venv venv
source venv/bin/activate  # для Linux/Mac
# или
venv\Scripts\activate  # для Windows
```

3. Установите зависимости
```bash
pip install -r requirements.txt
```

4. Создайте и настройте файл .env
```bash
cp .env.example .env
```

5. Примените миграции
```bash
python manage.py makemigrations
python manage.py migrate
```

6. Создайте суперпользователя
```bash
python manage.py createsuperuser
```

7. Создайте планы подписки
```bash
python manage.py create_subscription_plans
```

8. Запустите сервер разработки
```bash
python manage.py runserver
```

9. Откройте приложение и перейдите по адресу: http://127.0.0.1:8000/
