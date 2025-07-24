from django.shortcuts import render
from django.db.models import Count, Avg, Q
from macros.models import Macro, MacroCategory, KeyCommandsFile, CubaseVersion
from accounts.models import UserProfile


def home(request):
    """Homepage with featured content"""
    
    # Get featured/popular macros
    featured_macros = Macro.objects.filter(is_public=True).select_related(
        'category', 'keycommands_file__user'
    ).annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes')
    ).order_by('-view_count', '-download_count')[:8]
    
    # Get recently uploaded macros
    recent_macros = Macro.objects.filter(is_public=True).select_related(
        'category', 'keycommands_file__user'
    ).order_by('-created_at')[:6]
    
    # Get popular categories
    popular_categories = MacroCategory.objects.annotate(
        macro_count=Count('macro', filter=Q(macro__is_public=True))
    ).filter(macro_count__gt=0).order_by('-macro_count')[:6]
    
    # Get some statistics
    stats = {
        'total_macros': Macro.objects.filter(is_public=True).count(),
        'total_users': UserProfile.objects.count(),
        'total_files': KeyCommandsFile.objects.filter(is_public=True).count(),
        'total_categories': MacroCategory.objects.annotate(
            macro_count=Count('macro', filter=Q(macro__is_public=True))
        ).filter(macro_count__gt=0).count(),
    }
    
    # Get available Cubase versions
    cubase_versions = CubaseVersion.objects.annotate(
        file_count=Count('keycommandsfile', filter=Q(keycommandsfile__is_public=True))
    ).filter(file_count__gt=0).order_by('-major_version', '-minor_version')[:5]
    
    context = {
        'featured_macros': featured_macros,
        'recent_macros': recent_macros,
        'popular_categories': popular_categories,
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
