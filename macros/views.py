from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Avg, F, Sum
from django.http import HttpResponse, JsonResponse, Http404
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import logging

from .models import (
    KeyCommandsFile, Macro, MacroCategory, MacroVote, MacroFavorite, 
    MacroCollection, MacroDownload, CubaseVersion
)
from .forms import (
    KeyCommandsFileForm, MacroForm, MacroVoteForm, MacroCollectionForm,
    MacroSearchForm, MacroSelectionForm
)
from .utils import KeyCommandsParser, create_keycommands_xml, create_keycommands_xml_with_embedded_macros, get_client_ip

logger = logging.getLogger(__name__)


def macro_list(request):
    """Public macro listing with search and filtering"""
    form = MacroSearchForm(request.GET or None)
    
    # Start with public macros
    macros = Macro.objects.filter(is_public=True).select_related(
        'category', 'keycommands_file__user', 'keycommands_file__cubase_version'
    ).annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes')
    )
    
    # Apply filters
    if form.is_valid():
        query = form.cleaned_data.get('query')
        category = form.cleaned_data.get('category')
        cubase_version = form.cleaned_data.get('cubase_version')
        sort_by = form.cleaned_data.get('sort_by', 'newest')
        has_key_binding = form.cleaned_data.get('has_key_binding')
        
        if query:
            macros = macros.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(category__name__icontains=query)
            )
        
        if category:
            macros = macros.filter(category=category)
        
        if cubase_version:
            macros = macros.filter(keycommands_file__cubase_version=cubase_version)
        
        if has_key_binding:
            macros = macros.exclude(Q(key_binding='') | Q(key_binding__isnull=True))
        
        # Apply sorting
        if sort_by == 'newest':
            macros = macros.order_by('-created_at')
        elif sort_by == 'oldest':
            macros = macros.order_by('created_at')
        elif sort_by == 'most_popular':
            macros = macros.order_by('-view_count', '-created_at')
        elif sort_by == 'highest_rated':
            macros = macros.order_by('-avg_rating', '-vote_count', '-created_at')
        elif sort_by == 'most_downloaded':
            macros = macros.order_by('-download_count', '-created_at')
        elif sort_by == 'alphabetical':
            macros = macros.order_by('name')
    else:
        macros = macros.order_by('-created_at')
    
    # Paginate results
    paginator = Paginator(macros, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get popular categories for sidebar
    popular_categories = MacroCategory.objects.annotate(
        macro_count=Count('macro', filter=Q(macro__is_public=True))
    ).filter(macro_count__gt=0).order_by('-macro_count')[:10]
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'popular_categories': popular_categories,
        'total_count': paginator.count,
    }
    
    return render(request, 'macros/macro_list.html', context)


def macro_detail(request, macro_id):
    """Detailed view of a macro with voting"""
    macro = get_object_or_404(
        Macro.objects.select_related(
            'category', 'keycommands_file__user', 'keycommands_file__cubase_version'
        ).prefetch_related('votes__user'),
        id=macro_id
    )
    
    # Check permissions - allow public macros or private macros owned by the user
    if not macro.is_public and (not request.user.is_authenticated or macro.keycommands_file.user != request.user):
        raise Http404("Macro not found")
    
    # Increment view count
    Macro.objects.filter(id=macro_id).update(view_count=F('view_count') + 1)
    
    # Get user's vote if authenticated
    user_vote = None
    is_favorited = False
    if request.user.is_authenticated:
        user_vote = MacroVote.objects.filter(macro=macro, user=request.user).first()
        is_favorited = MacroFavorite.objects.filter(macro=macro, user=request.user).exists()
    
    # Handle voting
    if request.method == 'POST' and request.user.is_authenticated:
        vote_form = MacroVoteForm(request.POST, instance=user_vote)
        if vote_form.is_valid():
            vote = vote_form.save(commit=False)
            vote.macro = macro
            vote.user = request.user
            vote.save()
            messages.success(request, 'Your rating has been saved!')
            return redirect('macros:macro_detail', macro_id=macro.id)
    else:
        vote_form = MacroVoteForm(instance=user_vote)
    
    # Get recent votes
    recent_votes = macro.votes.select_related('user').order_by('-created_at')[:5]
    
    # Get related macros (same category)
    related_macros = Macro.objects.filter(
        category=macro.category,
        is_public=True
    ).exclude(id=macro.id).annotate(
        avg_rating=Avg('votes__rating')
    ).order_by('-avg_rating', '-view_count')[:5]
    
    context = {
        'macro': macro,
        'vote_form': vote_form,
        'user_vote': user_vote,
        'is_favorited': is_favorited,
        'recent_votes': recent_votes,
        'related_macros': related_macros,
    }
    
    return render(request, 'macros/macro_detail.html', context)


@login_required
def upload_keycommands(request):
    """Upload and parse Key Commands file with improved error handling for new macro format"""
    print(f"\n🔍 DEBUG: upload_keycommands called - Method: {request.method}")
    print(f"🔍 DEBUG: User: {request.user} (authenticated: {request.user.is_authenticated})")
    
    if request.method == 'POST':
        print(f"🔍 DEBUG: POST request received")
        print(f"🔍 DEBUG: POST data keys: {list(request.POST.keys())}")
        print(f"🔍 DEBUG: FILES data keys: {list(request.FILES.keys())}")
        
        form = KeyCommandsFileForm(request.POST, request.FILES)
        print(f"🔍 DEBUG: Form created, checking validity...")
        
        if form.is_valid():
            print(f"🔍 DEBUG: ✅ Form is valid!")
            print(f"🔍 DEBUG: Form cleaned_data: {form.cleaned_data}")
            
            keycommands_file = None
            try:
                with transaction.atomic():
                    print(f"🔍 DEBUG: Starting database transaction...")
                    
                    # Save the file first
                    keycommands_file = form.save(commit=False)
                    keycommands_file.user = request.user
                    keycommands_file.save()
                    
                    print(f"🔍 DEBUG: ✅ File saved to database - ID: {keycommands_file.id}")
                    print(f"🔍 DEBUG: File path: {keycommands_file.file.path}")
                    print(f"🔍 DEBUG: File name: {keycommands_file.file.name}")
                    print(f"🔍 DEBUG: File size: {keycommands_file.file.size} bytes")
                    
                    logger.info(f"Starting to parse Key Commands file: {keycommands_file.file.name}")
                    
                    # Parse the uploaded file
                    file_path = keycommands_file.file.path
                    print(f"🔍 DEBUG: Creating parser for file: {file_path}")
                    
                    parser = KeyCommandsParser(file_path)
                    print(f"🔍 DEBUG: Parser created, starting to parse...")
                    
                    categories_data = parser.parse()
                    print(f"🔍 DEBUG: ✅ Parsing completed!")
                    print(f"🔍 DEBUG: Found {len(categories_data)} categories")
                    for cat_name, macros in categories_data.items():
                        print(f"🔍 DEBUG:   - {cat_name}: {len(macros)} macros")
                    
                    # Validate parsed data
                    if not categories_data:
                        print(f"🔍 DEBUG: ❌ No categories data found!")
                        raise ValueError("No macros found in the uploaded file")
                    
                    total_macros = sum(len(macros) for macros in categories_data.values())
                    print(f"🔍 DEBUG: Total macros to process: {total_macros}")
                    
                    logger.info(f"Found {total_macros} macros in {len(categories_data)} categories")
                    
                    # Create categories and macros
                    created_macros = 0
                    updated_macros = 0
                    skipped_macros = 0
                    
                    print(f"🔍 DEBUG: Starting to create categories and macros...")
                    
                    for category_name, macros in categories_data.items():
                        print(f"🔍 DEBUG: Processing category: {category_name} ({len(macros)} macros)")
                        
                        # Get or create category
                        category, category_created = MacroCategory.objects.get_or_create(
                            name=category_name
                        )
                        
                        if category_created:
                            print(f"🔍 DEBUG: ✅ Created new category: {category_name}")
                            logger.info(f"Created new category: {category_name}")
                        else:
                            print(f"🔍 DEBUG: ♻️ Using existing category: {category_name}")
                        
                        # Create macros
                        for i, macro_data in enumerate(macros):
                            print(f"🔍 DEBUG:   Processing macro {i+1}/{len(macros)}: {macro_data.get('name', 'UNNAMED')}")
                            
                            try:
                                # Validate macro data
                                if not macro_data.get('name'):
                                    print(f"🔍 DEBUG:   ❌ Skipping macro with no name")
                                    logger.warning(f"Skipping macro with no name in category {category_name}")
                                    skipped_macros += 1
                                    continue
                                
                                # Prepare key binding string
                                key_bindings = macro_data.get('key_bindings', [])
                                key_binding = ', '.join(key_bindings) if key_bindings else ''
                                
                                # Prepare commands data
                                commands = macro_data.get('commands', [])
                                description = macro_data.get('description', '')
                                
                                print(f"🔍 DEBUG:   Macro details:")
                                print(f"🔍 DEBUG:     - Name: {macro_data['name']}")
                                print(f"🔍 DEBUG:     - Description: {description}")
                                print(f"🔍 DEBUG:     - Key bindings: {key_bindings}")
                                print(f"🔍 DEBUG:     - Commands count: {len(commands)}")
                                
                                # If no description provided, generate one from commands
                                if not description and commands:
                                    command_names = [cmd.get('name', '') for cmd in commands if cmd.get('name')]
                                    if command_names:
                                        if len(command_names) <= 3:
                                            description = f"Executes: {', '.join(command_names)}"
                                        else:
                                            description = f"Executes: {', '.join(command_names[:3])} and {len(command_names) - 3} more commands"
                                    print(f"🔍 DEBUG:     - Generated description: {description}")
                                
                                # Create or update macro
                                print(f"🔍 DEBUG:   Creating/updating macro in database...")
                                macro, created = Macro.objects.update_or_create(
                                    keycommands_file=keycommands_file,
                                    name=macro_data['name'],
                                    defaults={
                                        'category': category,
                                        'description': description,
                                        'key_binding': key_binding,
                                        'commands_json': commands,
                                        'xml_snippet': macro_data.get('xml_snippet', ''),
                                        'is_public': keycommands_file.is_public,
                                    }
                                )
                                
                                if created:
                                    created_macros += 1
                                    print(f"🔍 DEBUG:   ✅ Created macro: {macro_data['name']}")
                                    logger.debug(f"Created macro: {macro_data['name']}")
                                else:
                                    updated_macros += 1
                                    print(f"🔍 DEBUG:   ♻️ Updated macro: {macro_data['name']}")
                                    logger.debug(f"Updated macro: {macro_data['name']}")
                                
                            except Exception as macro_error:
                                print(f"🔍 DEBUG:   ❌ Error processing macro: {macro_error}")
                                logger.warning(f"Error processing macro '{macro_data.get('name', 'unknown')}': {macro_error}")
                                skipped_macros += 1
                                continue
                    
                    print(f"🔍 DEBUG: Macro processing complete!")
                    print(f"🔍 DEBUG: Created: {created_macros}, Updated: {updated_macros}, Skipped: {skipped_macros}")
                    
                    # Update user profile stats
                    try:
                        print(f"🔍 DEBUG: Updating user profile stats...")
                        profile = request.user.profile
                        profile.total_uploads = F('total_uploads') + 1
                        profile.save(update_fields=['total_uploads'])
                        print(f"🔍 DEBUG: ✅ User profile updated")
                    except Exception as profile_error:
                        print(f"🔍 DEBUG: ⚠️ Error updating user profile: {profile_error}")
                        logger.warning(f"Error updating user profile: {profile_error}")
                    
                    # Create success message with details
                    success_parts = []
                    if created_macros > 0:
                        success_parts.append(f"{created_macros} new macros")
                    if updated_macros > 0:
                        success_parts.append(f"{updated_macros} updated macros")
                    
                    success_message = f"Successfully uploaded Key Commands file"
                    if success_parts:
                        success_message += f" with {' and '.join(success_parts)}"
                    if skipped_macros > 0:
                        success_message += f" ({skipped_macros} macros skipped due to errors)"
                    
                    print(f"🔍 DEBUG: ✅ Success message: {success_message}")
                    messages.success(request, success_message)
                    logger.info(f"Upload completed: {created_macros} created, {updated_macros} updated, {skipped_macros} skipped")
                    
                    print(f"🔍 DEBUG: Redirecting to keycommands_detail page...")
                    return redirect('macros:keycommands_detail', file_id=keycommands_file.id)
            
            except Exception as e:
                print(f"🔍 DEBUG: ❌ EXCEPTION during upload processing: {e}")
                print(f"🔍 DEBUG: Exception type: {type(e)}")
                import traceback
                print(f"🔍 DEBUG: Traceback:\n{traceback.format_exc()}")
                
                logger.error(f"Error processing Key Commands file: {e}", exc_info=True)
                
                # Clean up the file if parsing failed
                if keycommands_file:
                    try:
                        print(f"🔍 DEBUG: Cleaning up failed upload file...")
                        keycommands_file.delete()
                        logger.info("Cleaned up failed upload file")
                        print(f"🔍 DEBUG: ✅ File cleanup completed")
                    except Exception as cleanup_error:
                        print(f"🔍 DEBUG: ❌ Error during cleanup: {cleanup_error}")
                        logger.error(f"Error cleaning up file: {cleanup_error}")
                
                # Show user-friendly error message
                if "No macros found" in str(e):
                    error_msg = "The uploaded file doesn't contain any valid macros. Please check that your file was exported correctly from Cubase and contains a 'Macros' section."
                    print(f"🔍 DEBUG: User error message: {error_msg}")
                    messages.error(request, error_msg)
                elif "Invalid XML" in str(e) or "XML parsing error" in str(e):
                    error_msg = "The uploaded file is not a valid XML file. Please ensure you're uploading a Key Commands file exported from Cubase."
                    print(f"🔍 DEBUG: User error message: {error_msg}")
                    messages.error(request, error_msg)
                else:
                    error_msg = f"Error processing your file: {str(e)}. Please check that your file is a valid Cubase Key Commands export."
                    print(f"🔍 DEBUG: User error message: {error_msg}")
                    messages.error(request, error_msg)
        else:
            print(f"🔍 DEBUG: ❌ Form is NOT valid!")
            print(f"🔍 DEBUG: Form errors: {form.errors}")
            print(f"🔍 DEBUG: Form non_field_errors: {form.non_field_errors()}")
            
            # Show form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        print(f"🔍 DEBUG: Form error (general): {error}")
                        messages.error(request, f"Form error: {error}")
                    else:
                        field_label = form.fields[field].label or field.replace('_', ' ').title()
                        print(f"🔍 DEBUG: Form error ({field_label}): {error}")
                        messages.error(request, f"{field_label}: {error}")
    else:
        print(f"🔍 DEBUG: GET request - displaying upload form")
        form = KeyCommandsFileForm()
    
    print(f"🔍 DEBUG: Rendering upload template")
    return render(request, 'macros/upload_keycommands.html', {'form': form})


def keycommands_detail(request, file_id):
    """View details of a Key Commands file and its macros"""
    keycommands_file = get_object_or_404(
        KeyCommandsFile.objects.select_related('user', 'cubase_version'),
        id=file_id
    )
    
    # Check permissions
    if not keycommands_file.is_public and keycommands_file.user != request.user:
        raise Http404("Key Commands file not found")
    
    # Get macros from this file with pagination
    macros_list = keycommands_file.macros.select_related('category').annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes')
    ).order_by('category__name', 'name')
    
    # Filter by category if requested
    category_filter = request.GET.get('category')
    if category_filter:
        try:
            category_id = int(category_filter)
            macros_list = macros_list.filter(category_id=category_id)
        except (ValueError, TypeError):
            pass
    
    # Filter by visibility if requested
    visibility_filter = request.GET.get('visibility')
    if visibility_filter == 'public':
        macros_list = macros_list.filter(is_public=True)
    elif visibility_filter == 'private':
        macros_list = macros_list.filter(is_public=False)
    
    # Group macros by category for display
    macros_by_category = {}
    for macro in macros_list:
        category_name = macro.category.name if macro.category else 'Uncategorized'
        if category_name not in macros_by_category:
            macros_by_category[category_name] = []
        macros_by_category[category_name].append(macro)
    
    # Pagination
    paginator = Paginator(macros_list, 20)  # 20 macros per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all categories for filter dropdown
    categories = MacroCategory.objects.filter(
        macro__keycommands_file=keycommands_file
    ).distinct().order_by('name')
    
    # Count public macros
    public_macros_count = keycommands_file.macros.filter(is_public=True).count()
    
    # Calculate total views (sum of all macro view counts)
    total_views = keycommands_file.macros.aggregate(
        total=Sum('view_count')
    )['total'] or 0
    
    # Handle POST requests for file management
    if request.method == 'POST' and request.user == keycommands_file.user:
        action = request.POST.get('action')
        
        if action == 'edit_file':
            # Update file details
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            is_public = request.POST.get('is_public') == 'on'
            
            if name:
                keycommands_file.name = name
                keycommands_file.description = description
                keycommands_file.is_public = is_public
                keycommands_file.save()
                
                # Update macro visibility to match file visibility
                keycommands_file.macros.update(is_public=is_public)
                
                messages.success(request, 'File details updated successfully!')
            else:
                messages.error(request, 'File name is required.')
                
        elif action == 'delete_file':
            # Delete the entire file
            file_name = keycommands_file.name
            keycommands_file.delete()
            messages.success(request, f'File "{file_name}" has been deleted.')
            return redirect('macros:my_keycommands')
            
        elif action == 'toggle_macro_visibility':
            # Toggle individual macro visibility
            macro_id = request.POST.get('macro_id')
            try:
                macro = keycommands_file.macros.get(id=macro_id)
                macro.is_public = not macro.is_public
                macro.save()
                status = "public" if macro.is_public else "private"
                messages.success(request, f'Macro "{macro.name}" is now {status}.')
            except Macro.DoesNotExist:
                messages.error(request, 'Macro not found.')
        
        return redirect('macros:keycommands_detail', file_id=file_id)
    
    context = {
        'keycommands_file': keycommands_file,
        'page_obj': page_obj,
        'macros_by_category': macros_by_category,
        'categories': categories,
        'total_macros': macros_list.count(),
        'public_macros_count': public_macros_count,
        'total_views': total_views,
        'is_owner': request.user == keycommands_file.user,
        'category_filter': category_filter,
        'visibility_filter': visibility_filter,
    }
    
    return render(request, 'macros/keycommands_detail.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_favorite(request, macro_id):
    """Toggle favorite status for a macro (AJAX)"""
    macro = get_object_or_404(Macro, id=macro_id, is_public=True)
    
    favorite, created = MacroFavorite.objects.get_or_create(
        user=request.user,
        macro=macro
    )
    
    if not created:
        favorite.delete()
        is_favorited = False
    else:
        is_favorited = True
    
    return JsonResponse({
        'is_favorited': is_favorited,
        'favorite_count': macro.favorited_by.count()
    })


@login_required
def download_keycommands(request, file_id):
    """Download original Key Commands file"""
    keycommands_file = get_object_or_404(KeyCommandsFile, id=file_id)
    
    # Check permissions
    if not keycommands_file.is_public and keycommands_file.user != request.user:
        raise Http404("Key Commands file not found")
    
    # Increment download count
    KeyCommandsFile.objects.filter(id=file_id).update(download_count=F('download_count') + 1)
    
    # Note: MacroDownload is only for individual macros, not entire files
    # File download tracking is handled by the download_count field above
    
    # Serve file
    response = HttpResponse(
        keycommands_file.file.read(),
        content_type='application/xml'
    )
    response['Content-Disposition'] = f'attachment; filename="{keycommands_file.name}.xml"'
    
    return response


@login_required
def download_selected_macros(request, file_id):
    """Download Key Commands file with selected macros only"""
    keycommands_file = get_object_or_404(KeyCommandsFile, id=file_id)
    
    # Check permissions
    if not keycommands_file.is_public and keycommands_file.user != request.user:
        raise Http404("Key Commands file not found")
    
    if request.method == 'POST':
        selected_macro_ids = request.POST.getlist('selected_macros')
        
        if not selected_macro_ids:
            messages.error(request, 'Please select at least one macro.')
            return redirect('macros:keycommands_detail', file_id=file_id)
        
        # Get selected macros
        selected_macros = Macro.objects.filter(
            id__in=selected_macro_ids,
            keycommands_file=keycommands_file
        ).select_related('category')
        
        # Convert to format needed for XML generation
        macros_data = []
        for macro in selected_macros:
            key_bindings = macro.key_binding.split(', ') if macro.key_binding else []
            macros_data.append({
                'name': macro.name,
                'category': macro.category.name if macro.category else 'Uncategorized',
                'key_bindings': key_bindings,
                'description': macro.description,
                'commands': macro.commands  # Include the actual commands from the macro
            })
        
        # Generate XML
        try:
            xml_content = create_keycommands_xml(macros_data)
            
            # Create download records
            for macro in selected_macros:
                MacroDownload.objects.create(
                    macro=macro,
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=get_client_ip(request)
                )
                # Increment macro download count
                Macro.objects.filter(id=macro.id).update(download_count=F('download_count') + 1)
            
            # Create response
            response = HttpResponse(xml_content, content_type='application/xml')
            filename = f"{keycommands_file.name}_selected_macros.xml"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating XML: {e}")
            messages.error(request, 'Error generating download file.')
            return redirect('macros:keycommands_detail', file_id=file_id)
    
    # GET request - show selection form
    macros = keycommands_file.macros.select_related('category').order_by('category__name', 'name')
    
    context = {
        'keycommands_file': keycommands_file,
        'macros': macros,
    }
    
    return render(request, 'macros/select_macros.html', context)


@login_required
def my_keycommands(request):
    """User's uploaded Key Commands files"""
    keycommands_files = KeyCommandsFile.objects.filter(
        user=request.user
    ).select_related('cubase_version').order_by('-created_at')
    
    paginator = Paginator(keycommands_files, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'macros/my_keycommands.html', context)


@login_required
def edit_macro(request, macro_id):
    """Edit a macro"""
    macro = get_object_or_404(
        Macro,
        id=macro_id,
        keycommands_file__user=request.user
    )
    
    if request.method == 'POST':
        form = MacroForm(request.POST, instance=macro)
        if form.is_valid():
            form.save()
            messages.success(request, 'Macro updated successfully!')
            return redirect('macros:macro_detail', macro_id=macro.id)
    else:
        form = MacroForm(instance=macro)
    
    context = {
        'form': form,
        'macro': macro,
    }
    
    return render(request, 'macros/edit_macro.html', context)


def popular_macros(request):
    """Show most popular macros"""
    macros = Macro.objects.filter(is_public=True).select_related(
        'category', 'keycommands_file__user'
    ).annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes')
    ).order_by('-view_count', '-download_count', '-avg_rating')[:50]
    
    context = {
        'macros': macros,
        'title': 'Most Popular Macros',
    }
    
    return render(request, 'macros/popular_macros.html', context)


def categories(request):
    """List all macro categories"""
    categories = MacroCategory.objects.annotate(
        macro_count=Count('macro', filter=Q(macro__is_public=True))
    ).filter(macro_count__gt=0).order_by('name')
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'macros/categories.html', context)


def category_detail(request, category_id):
    """Show macros in a specific category"""
    category = get_object_or_404(MacroCategory, id=category_id)
    
    macros = Macro.objects.filter(
        category=category,
        is_public=True
    ).select_related(
        'keycommands_file__user', 'keycommands_file__cubase_version'
    ).annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes')
    ).order_by('-created_at')
    
    paginator = Paginator(macros, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
    }
    
    return render(request, 'macros/category_detail.html', context)


@login_required
def select_macros_for_file(request, file_id):
    """Select macros to embed into a user's Key Commands file"""
    # Get the user's Key Commands file
    keycommands_file = get_object_or_404(
        KeyCommandsFile,
        id=file_id,
        user=request.user
    )
    
    if request.method == 'POST':
        # Get selected macro IDs
        selected_macro_ids = request.POST.getlist('selected_macros')
        
        if selected_macro_ids:
            # Get selected macros
            selected_macros = Macro.objects.filter(
                id__in=selected_macro_ids,
                is_public=True
            ).select_related('category', 'keycommands_file__user')
            
            # Generate XML with embedded macros
            try:
                xml_content = create_keycommands_xml_with_embedded_macros(
                    keycommands_file, selected_macros
                )
                
                # Create download response
                response = HttpResponse(xml_content, content_type='application/xml')
                response['Content-Disposition'] = f'attachment; filename="{keycommands_file.name}_with_macros.xml"'
                
                # Track downloads
                for macro in selected_macros:
                    macro.download_count = F('download_count') + 1
                    macro.save(update_fields=['download_count'])
                    
                    # Create download record
                    MacroDownload.objects.create(
                        macro=macro,
                        user=request.user,
                        ip_address=get_client_ip(request)
                    )
                
                messages.success(
                    request, 
                    f'Downloaded {keycommands_file.name} with {len(selected_macros)} embedded macro{"s" if len(selected_macros) != 1 else ""}!'
                )
                
                return response
                
            except Exception as e:
                logger.error(f"Error generating XML with embedded macros: {e}")
                messages.error(request, f"Error generating file: {str(e)}")
        else:
            messages.warning(request, 'Please select at least one macro to embed.')
    
    # Get available macros (public macros not from this user's file)
    available_macros = Macro.objects.filter(
        is_public=True
    ).exclude(
        keycommands_file=keycommands_file
    ).select_related(
        'category', 'keycommands_file__user'
    ).annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes')
    ).order_by('-download_count', '-view_count')
    
    # Get categories for filtering
    categories = MacroCategory.objects.filter(
        macro__is_public=True
    ).annotate(
        macro_count=Count('macro', filter=Q(macro__is_public=True))
    ).filter(macro_count__gt=0).order_by('name')
    
    # Filter by category if requested
    category_filter = request.GET.get('category')
    if category_filter:
        try:
            category_id = int(category_filter)
            available_macros = available_macros.filter(category_id=category_id)
        except (ValueError, TypeError):
            pass
    
    # Search filter
    search_query = request.GET.get('search')
    if search_query:
        available_macros = available_macros.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(available_macros, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'keycommands_file': keycommands_file,
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category_filter,
        'search_query': search_query,
    }
    
    return render(request, 'macros/select_macros_for_file.html', context)
