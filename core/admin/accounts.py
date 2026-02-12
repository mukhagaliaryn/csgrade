from django.contrib import admin
from django.contrib.admin import register
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.admin import UserAdmin as UserModelAdmin
from django.contrib.auth.models import Group
from core.models import User


# UserAdmin
# ----------------------------------------------------------------------------------------------------------------------
@register(User)
class UserAdmin(UserModelAdmin):
    model = User
    list_display = ('username', 'email', 'iin', 'role', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username', 'email', 'first_name', 'last_name')

    fieldsets = (
        (
            None,
            {
                'fields': ('avatar', 'username', 'email', 'iin', 'first_name', 'last_name', 'role', 'password'),
            },
        ),
        (
            _('Рұқсаттар'),
            {
                'fields': ('is_staff', 'is_active', 'is_superuser', )
            },
        ),
        (
            _('Бақылау'),
            {
                'fields': ('last_login', )
            }
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide', ),
                'fields': ('username', 'email', 'iin', 'first_name', 'last_name', 'role', 'password1', 'password2'),
            },
        ),
    )


admin.site.unregister(Group)
