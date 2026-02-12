from django.contrib.auth.forms import UserCreationForm
from django import forms
from core.models import User


class UserRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('iin', 'username', 'email', 'first_name', 'last_name', )


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'avatar', )
