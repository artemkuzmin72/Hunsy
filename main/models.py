from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.conf import settings

# Create your models here.

class User(models.Model):
    phone = models.IntegerField(unique=True, verbose_name="8...")
    full_name = models.CharField(max_length=255, verbose_name="Ф. И. О.")
    author = models.ForeignKey(
            on_delete=models.CASCADE,
            null=True,
            related_name='users'
        )
    
    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

class Post(models.Model):
    subject = models.CharField(max_length=255, verbose_name="Тема письма")
    body = models.TextField(verbose_name="Тело письма")
    author = models.ForeignKey(
        on_delete=models.CASCADE,
        null=True,
        related_name='messages'
    )

    def __str__(self):
        return self.subject

    class Meta:
        verbose_name = "Пост"
        verbose_name_plural = "Посты"