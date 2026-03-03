FROM python:3.13-slim

# Установка системных зависимостей для PostgreSQL и Pillow
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Установка переменных окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Копирование файла с зависимостями
COPY requirements.txt .

# Обновление pip и установка зависимостей
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn psycopg2-binary

# Копирование проекта
COPY . .

# Команда для запуска приложения
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "Hunsy.wsgi:application"]