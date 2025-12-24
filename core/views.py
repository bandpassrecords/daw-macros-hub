from django.shortcuts import render
from django.db.models import Count, Avg, Q
from macros.models import Macro, CubaseVersion
from accounts.models import UserProfile


def home(request):
    """Homepage with featured content"""
    
    # Get featured/popular macros (is_private=False means public)
    featured_macros = Macro.objects.filter(is_private=False).select_related(
        'user', 'cubase_version'
    ).annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes')
    ).order_by('-download_count', '-created_at')[:8]
    
    # Get recently uploaded macros (is_private=False means public)
    recent_macros = Macro.objects.filter(is_private=False).select_related(
        'user', 'cubase_version'
    ).order_by('-created_at')[:6]
    
    
    # Get some statistics
    stats = {
        'total_macros': Macro.objects.filter(is_private=False).count(),
        'total_users': UserProfile.objects.count(),
    }
    
    # Get available Cubase versions
    cubase_versions = CubaseVersion.objects.annotate(
        macro_count=Count('macro', filter=Q(macro__is_private=False))  # is_private=False means public
    ).filter(macro_count__gt=0).order_by('-major_version')[:5]
    
    context = {
        'featured_macros': featured_macros,
        'recent_macros': recent_macros,
        'stats': stats,
        'cubase_versions': cubase_versions,
    }
    
    return render(request, 'core/home.html', context)


def about(request):
    """About page"""
    return render(request, 'core/about.html')


def contact(request):
    """Contact page"""
    return render(request, 'core/contact.html')


def help_page(request):
    """Help/FAQ page"""
    return render(request, 'core/help.html')


def privacy_policy(request):
    """Privacy policy page"""
    return render(request, 'core/privacy_policy.html')


def terms_of_service(request):
    """Terms of service page"""
    return render(request, 'core/terms_of_service.html')
