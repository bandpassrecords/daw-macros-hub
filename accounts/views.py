from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction, OperationalError
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import time
from allauth.account.views import LoginView as AllauthLoginView
from .forms import CustomUserCreationForm, UserProfileForm, UserUpdateForm, DeleteAccountForm
from .models import UserProfile, EmailVerification
from macros.models import Macro, MacroFavorite


class CustomLoginView(AllauthLoginView):
    """Custom login view using allauth but with our template"""
    template_name = 'accounts/login.html'


def signup(request):
    """Signup choice page - choose between Google or email registration"""
    return render(request, 'accounts/signup.html')


def signup_email(request):
    """Email-only signup view with email verification"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Retry logic for SQLite database locks
            max_retries = 3
            retry_delay = 0.1  # Start with 100ms
            
            user = None
            token = None
            email = None
            
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        user = form.save()
                        email = form.cleaned_data.get('email')
                        
                        # Generate verification token
                        token = EmailVerification.generate_token()
                        EmailVerification.objects.create(
                            user=user,
                            token=token
                        )
                    break  # Success, exit retry loop
                except OperationalError as e:
                    if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                        # Wait before retrying with exponential backoff
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    else:
                        # Re-raise if it's not a lock error or we've exhausted retries
                        messages.error(request, 'Database is temporarily busy. Please try again in a moment.')
                        return render(request, 'accounts/signup_email.html', {'form': form})
            
            if not user or not token:
                messages.error(request, 'Failed to create account. Please try again.')
                return render(request, 'accounts/signup_email.html', {'form': form})
            
            # Send verification email (outside retry loop, only if user creation succeeded)
            verification_url = request.build_absolute_uri(
                f'/accounts/verify-email/{token}/'
            )
            
            # Render email template
            html_message = render_to_string('accounts/email_verification.html', {
                'user': user,
                'verification_url': verification_url,
                'expires_in': '10 minutes',
            })
            plain_message = strip_tags(html_message)
            
            try:
                send_mail(
                    subject='Verify your email address - Cubase Macros Shop',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=False,
                )
                messages.success(
                    request,
                    f'Account created! Please check your email ({email}) and click the verification link to activate your account. The link expires in 10 minutes.'
                )
                return redirect('accounts:verification_sent')
            except Exception as e:
                # If email fails, delete the user and show error
                user.delete()
                messages.error(
                    request,
                    f'Failed to send verification email. Please try again. Error: {str(e)}'
                )
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/signup_email.html', {'form': form})


def verify_email(request, token):
    """Verify email address using token"""
    try:
        verification = EmailVerification.objects.get(token=token)
    except EmailVerification.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('accounts:signup')
    
    if verification.verified:
        messages.info(request, 'Your email has already been verified. You can log in.')
        return redirect('accounts:login')
    
    if verification.is_expired():
        # Delete expired verification and user
        user = verification.user
        verification.delete()
        user.delete()
        messages.error(
            request,
            'Verification link has expired. Please sign up again to receive a new verification email.'
        )
        return redirect('accounts:signup')
    
    # Verify the email
    verification.verify()
    
    messages.success(
        request,
        'Email verified successfully! Your account has been activated. You can now log in.'
    )
    return redirect('accounts:login')


def verification_sent(request):
    """Page shown after verification email is sent"""
    return render(request, 'accounts/verification_sent.html')


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
    total_favorites = favorites_paginator.count
    
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
        'total_favorites': total_favorites,
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


def public_profile(request, slug):
    """View public profile of a user - shows only public macros. slug is email"""
    user = get_object_or_404(User, email=slug)
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


@login_required
def delete_account(request):
    """Delete user account view"""
    if request.method == 'POST':
        form = DeleteAccountForm(request.POST)
        if form.is_valid() and form.cleaned_data['confirm_delete']:
            user = request.user
            delete_macros = form.cleaned_data.get('delete_macros', False)
            macro_count = Macro.objects.filter(user=user).count()
            
            with transaction.atomic():
                # Delete macros based on user's choice
                # Note: We must delete macros when deleting user (CASCADE), but we respect user's explicit choice
                if delete_macros:
                    # User explicitly wants to delete macros
                    Macro.objects.filter(user=user).delete()
                    messages.success(request, f'Your account and {macro_count} macro(s) have been permanently deleted.')
                else:
                    # User wants to keep macros, but we can't due to CASCADE
                    # We'll still delete them but inform the user
                    if macro_count > 0:
                        messages.warning(request, f'Your account has been deleted. Note: {macro_count} macro(s) were also removed as they cannot exist without a user account.')
                    else:
                        messages.success(request, 'Your account has been deleted.')
                
                # Logout before deleting user
                logout(request)
                
                # Delete user (this will cascade delete UserProfile, votes, favorites, collections, downloads)
                # If macros weren't deleted above, CASCADE will delete them here
                user.delete()
                
                return redirect('core:home')
        else:
            messages.error(request, 'Please confirm that you understand this action cannot be undone.')
    else:
        form = DeleteAccountForm()
    
    # Get macro count for display
    macro_count = Macro.objects.filter(user=request.user).count()
    
    context = {
        'form': form,
        'macro_count': macro_count,
    }
    
    return render(request, 'accounts/delete_account.html', context)
