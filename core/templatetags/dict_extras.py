from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    if d is None:
        return None
    return d.get(key)

@register.filter
def in_set(value, container):
    if container is None:
        return False
    try:
        return value in container
    except TypeError:
        return False

@register.filter
def bool_and(a, b):
    return bool(a) and bool(b)