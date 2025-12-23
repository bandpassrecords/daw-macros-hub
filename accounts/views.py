from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from allauth.account.views import LoginView as AllauthLoginView
from .forms import CustomUserCreationForm, UserProfileForm, UserUpdateForm
from .models import UserProfile
from macros.models import Macro, MacroFavorite


class CustomLoginView(AllauthLoginView):
    """Custom login view using allauth but with our template"""
    template_name = 'accounts/login.html'


def register(request):
    """User registration view"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                username = form.cleaned_data.get('username')
                messages.success(request, f'Account created for {username}! You can now log in.')
                
                # Log the user in after successful registration
                user = authenticate(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password1']
                )
                if user:
                    login(request, user)
                    return redirect('core:home')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile(request):
    """User profile view - shows user's macros"""
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get user's favorite macros (as MacroFavorite objects)
    favorite_macros = MacroFavorite.objects.filter(
        user=request.user
    ).select_related('macro__user', 'macro__cubase_version').order_by('-created_at')
    
    # Get ALL user's macros (both public and private for own profile)
    all_macros = Macro.objects.filter(
        user=request.user
    ).select_related('user', 'cubase_version').order_by('-created_at')
    
    # Get user's public macros (is_private=False means public)
    public_macros = all_macros.filter(is_private=False)
    
    # Get user's private macros (is_private=True)
    private_macros = all_macros.filter(is_private=True)
    
    # Paginate results
    all_macros_paginator = Paginator(all_macros, 20)
    all_macros_page = request.GET.get('all_macros_page', 1)
    all_macros = all_macros_paginator.get_page(all_macros_page)
    
    favorites_paginator = Paginator(favorite_macros, 20)
    favorites_page = request.GET.get('favorites_page', 1)
    favorite_macros = favorites_paginator.get_page(favorites_page)
    
    public_macros_paginator = Paginator(public_macros, 20)
    public_macros_page = request.GET.get('public_macros_page', 1)
    public_macros = public_macros_paginator.get_page(public_macros_page)
    
    private_macros_paginator = Paginator(private_macros, 20)
    private_macros_page = request.GET.get('private_macros_page', 1)
    private_macros = private_macros_paginator.get_page(private_macros_page)
    
    # Statistics
    total_macros = Macro.objects.filter(user=request.user).count()
    total_public = public_macros_paginator.count
    total_private = private_macros_paginator.count
    
    context = {
        'profile': user_profile,
        'profile_user': request.user,  # For template consistency
        'all_macros': all_macros,
        'favorite_macros': favorite_macros,
        'public_macros': public_macros,
        'private_macros': private_macros,
        'total_macros': total_macros,
        'total_public': total_public,
        'total_private': total_private,
        'is_own_profile': True,
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
def edit_profile(request):
    """Edit user profile view"""
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            with transaction.atomic():
                user_form.save()
                profile_form.save()
                messages.success(request, 'Your profile has been updated successfully!')
                return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = UserProfileForm(instance=user_profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    
    return render(request, 'accounts/edit_profile.html', context)


def public_profile(request, username):
    """View public profile of a user - shows only public macros"""
    user = get_object_or_404(User, username=username)
    user_profile = get_object_or_404(UserProfile, user=user)
    
    # Get user's public macros (is_private=False means public)
    public_macros = Macro.objects.filter(
        user=user,
        is_private=False
    ).select_related('user', 'cubase_version').order_by('-created_at')
    
    # Paginate results
    macros_paginator = Paginator(public_macros, 20)
    macros_page = request.GET.get('macros_page', 1)
    public_macros = macros_paginator.get_page(macros_page)
    
    # Statistics
    total_public = macros_paginator.count
    
    context = {
        'profile_user': user,
        'profile': user_profile,
        'public_macros': public_macros,
        'total_public': total_public,
        'is_own_profile': request.user == user,
    }
    
    return render(request, 'accounts/public_profile.html', context)


@login_required
def dashboard(request):
    """User dashboard with overview"""
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get recent macros
    recent_macros = Macro.objects.filter(
        user=request.user
    ).select_related('user', 'cubase_version').order_by('-created_at')[:5]
    
    # Get recent favorites
    recent_favorites = MacroFavorite.objects.filter(
        user=request.user
    ).select_related('macro__user', 'macro__cubase_version').order_by('-created_at')[:5]
    
    # Get statistics
    total_macros = Macro.objects.filter(user=request.user).count()
    total_public_macros = Macro.objects.filter(
        user=request.user,
        is_private=False
    ).count()
    total_private_macros = Macro.objects.filter(
        user=request.user,
        is_private=True
    ).count()
    total_favorites = MacroFavorite.objects.filter(user=request.user).count()
    
    # Get popular macros from user (is_private=False means public)
    popular_macros = Macro.objects.filter(
        user=request.user,
        is_private=False
    ).select_related('user', 'cubase_version').order_by('-download_count', '-created_at')[:5]
    
    context = {
        'profile': user_profile,
        'recent_macros': recent_macros,
        'recent_favorites': recent_favorites,
        'total_macros': total_macros,
        'total_public_macros': total_public_macros,
        'total_private_macros': total_private_macros,
        'total_favorites': total_favorites,
        'popular_macros': popular_macros,
    }
    
    return render(request, 'accounts/dashboard.html', context)
