from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from .forms import CustomUserCreationForm, UserProfileForm, UserUpdateForm
from .models import UserProfile
from macros.models import KeyCommandsFile, Macro, MacroFavorite


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
    """User profile view"""
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get user's uploaded files
    keycommands_files = KeyCommandsFile.objects.filter(user=request.user).order_by('-created_at')
    
    # Get user's favorite macros
    favorite_macros = Macro.objects.filter(
        favorited_by__user=request.user
    ).select_related('category', 'keycommands_file__user').order_by('-favorited_by__created_at')
    
    # Get user's public macros
    public_macros = Macro.objects.filter(
        keycommands_file__user=request.user,
        is_public=True
    ).select_related('category').order_by('-created_at')
    
    # Paginate results
    files_paginator = Paginator(keycommands_files, 10)
    files_page = request.GET.get('files_page', 1)
    keycommands_files = files_paginator.get_page(files_page)
    
    favorites_paginator = Paginator(favorite_macros, 10)
    favorites_page = request.GET.get('favorites_page', 1)
    favorite_macros = favorites_paginator.get_page(favorites_page)
    
    macros_paginator = Paginator(public_macros, 10)
    macros_page = request.GET.get('macros_page', 1)
    public_macros = macros_paginator.get_page(macros_page)
    
    context = {
        'profile': user_profile,
        'keycommands_files': keycommands_files,
        'favorite_macros': favorite_macros,
        'public_macros': public_macros,
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
    """View public profile of a user"""
    user = get_object_or_404(User, username=username)
    user_profile = get_object_or_404(UserProfile, user=user)
    
    # Get user's public key commands files
    public_keycommands = KeyCommandsFile.objects.filter(
        user=user, 
        is_public=True
    ).order_by('-created_at')
    
    # Get user's public macros
    public_macros = Macro.objects.filter(
        keycommands_file__user=user,
        is_public=True
    ).select_related('category', 'keycommands_file').order_by('-created_at')
    
    # Paginate results
    files_paginator = Paginator(public_keycommands, 10)
    files_page = request.GET.get('files_page', 1)
    public_keycommands = files_paginator.get_page(files_page)
    
    macros_paginator = Paginator(public_macros, 10)
    macros_page = request.GET.get('macros_page', 1)
    public_macros = macros_paginator.get_page(macros_page)
    
    context = {
        'profile_user': user,
        'profile': user_profile,
        'public_keycommands': public_keycommands,
        'public_macros': public_macros,
        'is_own_profile': request.user == user,
    }
    
    return render(request, 'accounts/public_profile.html', context)


@login_required
def dashboard(request):
    """User dashboard with overview"""
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get recent uploads
    recent_uploads = KeyCommandsFile.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    # Get recent favorites
    recent_favorites = MacroFavorite.objects.filter(
        user=request.user
    ).select_related('macro__category', 'macro__keycommands_file__user').order_by('-created_at')[:5]
    
    # Get statistics
    total_uploads = KeyCommandsFile.objects.filter(user=request.user).count()
    total_public_macros = Macro.objects.filter(
        keycommands_file__user=request.user,
        is_public=True
    ).count()
    total_favorites = MacroFavorite.objects.filter(user=request.user).count()
    
    # Get popular macros from user
    popular_macros = Macro.objects.filter(
        keycommands_file__user=request.user,
        is_public=True
    ).order_by('-view_count', '-download_count')[:5]
    
    context = {
        'profile': user_profile,
        'recent_uploads': recent_uploads,
        'recent_favorites': recent_favorites,
        'total_uploads': total_uploads,
        'total_public_macros': total_public_macros,
        'total_favorites': total_favorites,
        'popular_macros': popular_macros,
    }
    
    return render(request, 'accounts/dashboard.html', context)
