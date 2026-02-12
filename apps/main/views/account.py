from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from apps.main.forms import UserUpdateForm


# account page
# ======================================================================================================================
@login_required
def account_view(request):
    user = request.user
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, _('Профиль сәтті жаңартылды'))
            return redirect('customer:account')
    else:
        form = UserUpdateForm(instance=user)

    context = {'form': form}
    return render(request, 'app/main/account/me/page.html', context)


# settings page
# ======================================================================================================================
@login_required
def settings_view(request):
    user = request.user
    password_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        if 'change_password' in request.POST:
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, _('Құпиясөз сәтті өзгертілді'))
                return redirect('customer:settings')
            else:
                messages.error(request, _('Қате! Құпиясөз өзгертілмеді'))

        elif 'delete_account' in request.POST:
            user.delete()
            messages.success(request, _('Аккаунт жойылды'))
            return redirect('customer:login')

    context = {
        'password_form': password_form
    }
    return render(request, 'app/main/account/settings/page.html', context)