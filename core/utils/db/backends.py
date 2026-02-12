from django.contrib.auth.backends import ModelBackend
from core.models import User
from django.db.models import Q


class EmailOrIINBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            return None

        try:
            user = User.objects.get(
                Q(username=username) |
                Q(email=username) |
                Q(iin=username)
            )
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
