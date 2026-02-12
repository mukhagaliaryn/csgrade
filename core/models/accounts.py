from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


# User model
# ======================================================================================================================
class User(AbstractUser):
    class UserRoles(models.TextChoices):
        CUSTOMER = "customer", _("Тапсырушы")
        MANAGER = "manager", _("Менеджер")

    avatar = models.ImageField(_("Аватар"), upload_to="accounts/users/avatars", null=True, blank=True)
    iin = models.CharField(_("ЖСН (ИИН)"), max_length=36, unique=True)
    role = models.CharField(_("Типі"), max_length=16, choices=UserRoles.choices, default=UserRoles.CUSTOMER)

    def __str__(self):
        return self.get_full_name() or self.username

    class Meta:
        verbose_name = _("Қолданушы")
        verbose_name_plural = _("Қолданушылар")
