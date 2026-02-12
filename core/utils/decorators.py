from functools import wraps
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import Http404


def _norm_role(value):
    return None if value is None else str(value).strip().lower()


def _flatten_roles(items):
    if len(items) == 1 and isinstance(items[0], (list, tuple, set)):
        return list(items[0])
    return list(items)


def role_required(*allowed_roles):
    allowed_roles = _flatten_roles(allowed_roles)
    allowed = {_norm_role(r) for r in allowed_roles}

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, "user", None)

            if not user or not user.is_authenticated:
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)

            role = _norm_role(getattr(user, "role", None))
            if role not in allowed:
                raise Http404()

            return view_func(request, *args, **kwargs)

        return _wrapped
    return decorator
