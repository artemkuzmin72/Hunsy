from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Post, PostVersion


class UserRegistrationForm(UserCreationForm):
    """Форма регистрации пользователя"""

    phone = forms.CharField(
        label="Номер телефона",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Введите номер телефона"}
        ),
    )
    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Введите пароль"}
        ),
    )
    password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Подтвердите пароль"}
        ),
    )

    class Meta:
        model = User
        fields = ("phone",)

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError(
                "Пользователь с таким номером телефона уже существует"
            )
        return phone


class CustomAuthenticationForm(AuthenticationForm):
    """Форма входа в систему"""

    username = forms.CharField(
        label="Номер телефона",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Введите номер телефона"}
        ),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Введите пароль"}
        ),
    )


class PostCreateForm(forms.Form):
    """Форма для создания нового поста"""

    title = forms.CharField(
        max_length=200,
        min_length=3,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Заголовок поста"}
        ),
    )
    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 10,
                "placeholder": "Содержание поста",
            }
        ),
        min_length=10,
    )
    summary = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Краткое описание",
            }
        ),
    )
    language = forms.ChoiceField(
        choices=PostVersion.LANGUAGE_CHOICES,
        initial="ru",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    featured_image = forms.ImageField(
        required=False, widget=forms.FileInput(attrs={"class": "form-control"})
    )


class PostVersionForm(forms.ModelForm):
    """Форма для создания новой версии"""

    change_summary = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Что изменилось?"}
        ),
    )

    class Meta:
        model = PostVersion
        fields = [
            "title",
            "content",
            "summary",
            "language",
            "featured_image",
            "meta_description",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 10}),
            "summary": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "language": forms.Select(attrs={"class": "form-select"}),
            "featured_image": forms.FileInput(attrs={"class": "form-control"}),
            "meta_description": forms.TextInput(attrs={"class": "form-control"}),
        }


class PostSettingsForm(forms.ModelForm):
    """Форма для настроек поста"""

    class Meta:
        model = Post
        fields = ["is_featured", "allow_comments", "status"]
        widgets = {
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "allow_comments": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class PostAccessForm(forms.ModelForm):
    """Форма для настройки доступа к посту"""

    class Meta:
        model = Post
        fields = ["access_type", "price", "required_subscription"]
        widgets = {
            "access_type": forms.Select(
                attrs={"class": "form-select", "onchange": "toggleAccessFields()"}
            ),
            "price": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "0.00", "step": "0.01"}
            ),
            "required_subscription": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "access_type": "Тип доступа",
            "price": "Цена ($)",
            "required_subscription": "Требуемая подписка",
        }
