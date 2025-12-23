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
import xml.etree.ElementTree as ET

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
    
    # Start with public macros (is_private=False means public)
    macros = Macro.objects.filter(is_private=False).select_related(
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
            macros = macros.order_by('-avg_rating', '-total_votes', '-created_at')
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
        macro_count=Count('macro', filter=Q(macro__is_private=False))
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
    
    # Check permissions - allow public macros (is_private=False) or private macros owned by the user
    if macro.is_private and (not request.user.is_authenticated or macro.keycommands_file.user != request.user):
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
        is_private=False
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
    """Upload and parse Macros file (KeyCommands.xml) in memory - show selection page instead of saving file"""
    if request.method == 'POST':
        form = KeyCommandsFileForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Get file from form but don't save it
                uploaded_file = form.cleaned_data['file']
                
                # Read file content into memory
                uploaded_file.seek(0)
                file_content = uploaded_file.read().decode('utf-8')
                
                logger.info(f"Parsing Macros file (KeyCommands.xml) in memory: {uploaded_file.name}")
                
                # Parse the file content directly (not from disk)
                parser = KeyCommandsParser(file_content)
                categories_data = parser.parse()
                
                # Validate parsed data
                if not categories_data:
                    raise ValueError("No macros found in the uploaded file")
                
                # Flatten all macros for selection
                all_macros = []
                for category_name, macros in categories_data.items():
                    for macro_data in macros:
                        if macro_data.get('name'):  # Only include macros with names
                            all_macros.append({
                                'name': macro_data.get('name', ''),
                                'category': category_name,
                                'description': macro_data.get('description', ''),
                                'key_bindings': macro_data.get('key_bindings', []),
                                'commands': macro_data.get('commands', []),
                                'xml_snippet': macro_data.get('xml_snippet', ''),
                                'reference_snippet': macro_data.get('reference_snippet', ''),
                            })
                
                if not all_macros:
                    raise ValueError("No valid macros found in the uploaded file")
                
                # Get cubase version (default to "Unspecified" if not selected)
                cubase_version = form.cleaned_data.get('cubase_version')
                if not cubase_version:
                    try:
                        cubase_version = CubaseVersion.objects.get(version='Unspecified')
                    except CubaseVersion.DoesNotExist:
                        cubase_version = None
                
                # Store parsed data in session for the selection step
                request.session['upload_data'] = {
                    'name': form.cleaned_data['name'],
                    'description': form.cleaned_data['description'],
                    'cubase_version_id': cubase_version.id if cubase_version else None,
                    'macros': all_macros,
                    'file_name': uploaded_file.name,
                }
                
                logger.info(f"Found {len(all_macros)} macros for selection")
                messages.success(request, f'Found {len(all_macros)} macros in your file. Please select which ones to save.')
                
                # Redirect to selection page
                return redirect('macros:select_macros_upload')
                
            except Exception as e:
                logger.error(f"Error parsing Macros file (KeyCommands.xml): {e}", exc_info=True)
                
                if "No macros found" in str(e) or "No valid macros" in str(e):
                    messages.error(request, "The uploaded file doesn't contain any valid macros. Please check that your file was exported correctly from Cubase.")
                elif "Invalid XML" in str(e) or "XML parsing error" in str(e):
                    messages.error(request, "The uploaded file is not a valid XML file. Please ensure you're uploading a Macros file (KeyCommands.xml) from Cubase.")
                else:
                    messages.error(request, f"Error processing your file: {str(e)}")
        else:
            # Show form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"Form error: {error}")
                    else:
                        field_label = form.fields[field].label or field.replace('_', ' ').title()
                        messages.error(request, f"{field_label}: {error}")
    else:
        form = KeyCommandsFileForm()
    
    return render(request, 'macros/upload_keycommands.html', {'form': form})


@login_required
def select_macros_upload(request):
    """Show macro selection page after upload"""
    # Get parsed data from session
    upload_data = request.session.get('upload_data')
    
    if not upload_data:
        messages.error(request, 'Upload session expired. Please upload your file again.')
        return redirect('macros:upload_keycommands')
    
    # Add index to each macro for tracking
    macros_with_index = []
    for idx, macro in enumerate(upload_data['macros']):
        macro_copy = macro.copy()
        macro_copy['index'] = idx
        macros_with_index.append(macro_copy)
    
    # Group macros by category for better display
    macros_by_category = {}
    for macro in macros_with_index:
        category = macro['category'] or 'Uncategorized'
        if category not in macros_by_category:
            macros_by_category[category] = []
        macros_by_category[category].append(macro)
    
    if request.method == 'POST':
        # Get selected macro indices
        selected_indices = request.POST.getlist('selected_macros')
        
        if not selected_indices:
            messages.warning(request, 'Please select at least one macro to save.')
            return render(request, 'macros/select_macros_upload.html', {
                'upload_data': upload_data,
                'macros_by_category': macros_by_category,
                'total_macros': len(upload_data['macros']),
            })
        
        # Get privacy settings for each selected macro
        private_macro_indices = set(request.POST.getlist('private_macros'))
        
        # Store selected indices and privacy settings in session for the save step
        request.session['selected_macro_indices'] = [int(idx) for idx in selected_indices]
        request.session['private_macro_indices'] = [int(idx) for idx in private_macro_indices if idx in selected_indices]
        
        # Redirect to save view
        return redirect('macros:save_selected_macros')
    
    context = {
        'upload_data': upload_data,
        'macros_by_category': macros_by_category,
        'total_macros': len(upload_data['macros']),
    }
    
    return render(request, 'macros/select_macros_upload.html', context)


@login_required
def save_selected_macros(request):
    """Save only the selected macros to database (no file storage)"""
    # Get data from session
    upload_data = request.session.get('upload_data')
    selected_indices = request.session.get('selected_macro_indices')
    private_macro_indices = request.session.get('private_macro_indices', [])
    
    if not upload_data or not selected_indices:
        messages.error(request, 'Session expired. Please upload your file again.')
        return redirect('macros:upload_keycommands')
    
    try:
        with transaction.atomic():
            # Get cubase version (default to "Unspecified" if not provided)
            cubase_version_id = upload_data.get('cubase_version_id')
            if not cubase_version_id:
                try:
                    unspecified_version = CubaseVersion.objects.get(version='Unspecified')
                    cubase_version_id = unspecified_version.id
                except CubaseVersion.DoesNotExist:
                    cubase_version_id = None
            
            # Create KeyCommandsFile without saving the file (default to public)
            keycommands_file = KeyCommandsFile(
                user=request.user,
                name=upload_data['name'],
                description=upload_data['description'],
                cubase_version_id=cubase_version_id,
                is_private=False,  # File is always public, privacy is set per macro
                file=None  # No file stored
            )
            keycommands_file.save()
            
            logger.info(f"Created KeyCommandsFile {keycommands_file.id} without file storage")
            
            # Convert private_macro_indices to set for fast lookup
            private_indices_set = set(int(idx) for idx in private_macro_indices)
            
            # Get selected macros with their indices
            selected_macros_with_indices = []
            for idx in selected_indices:
                idx_int = int(idx)
                if 0 <= idx_int < len(upload_data['macros']):
                    selected_macros_with_indices.append((idx_int, upload_data['macros'][idx_int]))
            
            created_macros = 0
            skipped_macros = 0
            
            # Process each selected macro
            for idx_int, macro_data in selected_macros_with_indices:
                try:
                    if not macro_data.get('name'):
                        skipped_macros += 1
                        continue
                    
                    # Get or create category
                    category, _ = MacroCategory.objects.get_or_create(
                        name=macro_data.get('category', 'Uncategorized')
                    )
                    
                    # Prepare key binding string
                    key_bindings = macro_data.get('key_bindings', [])
                    key_binding = ', '.join(key_bindings) if key_bindings else ''
                    
                    # Prepare commands and description
                    commands = macro_data.get('commands', [])
                    description = macro_data.get('description', '')
                    
                    # Generate description if not provided
                    if not description and commands:
                        command_names = [cmd.get('name', '') for cmd in commands if cmd.get('name')]
                        if command_names:
                            if len(command_names) <= 3:
                                description = f"Executes: {', '.join(command_names)}"
                            else:
                                description = f"Executes: {', '.join(command_names[:3])} and {len(command_names) - 3} more commands"
                    
                    # Determine if this macro should be private
                    macro_is_private = idx_int in private_indices_set
                    
                    # Create macro with both XML snippets
                    macro, created = Macro.objects.update_or_create(
                        keycommands_file=keycommands_file,
                        name=macro_data['name'],
                        category=category,
                        defaults={
                            'description': description,
                            'key_binding': key_binding,
                            'commands_json': commands,
                            'xml_snippet': macro_data.get('xml_snippet', ''),
                            'reference_snippet': macro_data.get('reference_snippet', ''),
                            'is_private': macro_is_private,  # Use individual macro privacy setting
                        }
                    )
                    
                    if created:
                        created_macros += 1
                        logger.debug(f"Created macro: {macro_data['name']}")
                    
                except Exception as macro_error:
                    logger.warning(f"Error processing macro '{macro_data.get('name', 'unknown')}': {macro_error}")
                    skipped_macros += 1
                    continue
            
            # Update user profile stats
            try:
                profile = request.user.profile
                profile.total_uploads = F('total_uploads') + 1
                profile.save(update_fields=['total_uploads'])
            except Exception:
                pass
            
            # Clear session data
            request.session.pop('upload_data', None)
            request.session.pop('selected_macro_indices', None)
            request.session.pop('private_macro_indices', None)
            
            # Success message
            success_message = f"Successfully saved {created_macros} macro{'s' if created_macros != 1 else ''}"
            if skipped_macros > 0:
                success_message += f" ({skipped_macros} skipped)"
            
            messages.success(request, success_message)
            logger.info(f"Saved {created_macros} macros for file {keycommands_file.id}")
            
            return redirect('macros:keycommands_detail', file_id=keycommands_file.id)
            
    except Exception as e:
        logger.error(f"Error saving selected macros: {e}", exc_info=True)
        messages.error(request, f"Error saving macros: {str(e)}")
        return redirect('macros:upload_keycommands')


def keycommands_detail(request, file_id):
    """View details of a Macros file and its macros"""
    keycommands_file = get_object_or_404(
        KeyCommandsFile.objects.select_related('user', 'cubase_version'),
        id=file_id
    )
    
    # Check permissions
    if keycommands_file.is_private and keycommands_file.user != request.user:
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
        macros_list = macros_list.filter(is_private=False)
    elif visibility_filter == 'private':
        macros_list = macros_list.filter(is_private=True)
    
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
    
    # Count public macros (is_private=False means public)
    public_macros_count = keycommands_file.macros.filter(is_private=False).count()
    
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
            is_private = request.POST.get('is_private') == 'on'
            
            if name:
                keycommands_file.name = name
                keycommands_file.description = description
                keycommands_file.is_private = is_private
                keycommands_file.save()
                
                # Update macro visibility to match file visibility
                keycommands_file.macros.update(is_private=is_private)
                
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
                macro.is_private = not macro.is_private
                macro.save()
                status = "private" if macro.is_private else "public"
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
    macro = get_object_or_404(Macro, id=macro_id, is_private=False)
    
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
    """Download Key Commands file - always generate from stored macro snippets (files are never stored)"""
    keycommands_file = get_object_or_404(KeyCommandsFile, id=file_id)
    
    # Check permissions
    if keycommands_file.is_private and keycommands_file.user != request.user:
        raise Http404("Key Commands file not found")
    
    # Increment download count
    KeyCommandsFile.objects.filter(id=file_id).update(download_count=F('download_count') + 1)
    
    # Always generate XML from stored macro snippets (files are never stored)
    macros = keycommands_file.macros.all()
    if not macros:
        messages.error(request, 'No macros found in this file.')
        return redirect('macros:keycommands_detail', file_id=file_id)
    
    # Convert macros to format needed for XML generation
    macros_data = []
    for macro in macros:
        key_bindings = macro.key_binding.split(', ') if macro.key_binding else []
        macros_data.append({
            'name': macro.name,
            'category': macro.category.name if macro.category else 'Uncategorized',
            'key_bindings': key_bindings,
            'description': macro.description,
            'commands': macro.commands
        })
    
    # Generate XML
    try:
        xml_content = create_keycommands_xml(macros_data)
        response = HttpResponse(xml_content, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="{keycommands_file.name}.xml"'
        return response
    except Exception as e:
        logger.error(f"Error generating XML: {e}")
        messages.error(request, 'Error generating download file.')
        return redirect('macros:keycommands_detail', file_id=file_id)


@login_required
def download_selected_macros(request, file_id):
    """Download Key Commands file with selected macros embedded into user's file"""
    keycommands_file = get_object_or_404(KeyCommandsFile, id=file_id)
    
    # Check permissions
    if keycommands_file.is_private and keycommands_file.user != request.user:
        raise Http404("Key Commands file not found")
    
    if request.method == 'POST':
        # Step 1: Store selected macros in session and redirect to file upload
        selected_macro_ids = request.POST.getlist('selected_macros')
        
        if not selected_macro_ids:
            messages.error(request, 'Please select at least one macro.')
            return redirect('macros:download_selected_macros', file_id=file_id)
        
        # Store selected macro IDs in session
        request.session['download_selected_macros'] = {
            'file_id': str(file_id),
            'macro_ids': selected_macro_ids,
        }
        
        return redirect('macros:upload_user_file_for_download', file_id=file_id)
    
    # GET request - show selection form
    macros = keycommands_file.macros.select_related('category').order_by('category__name', 'name')
    
    context = {
        'keycommands_file': keycommands_file,
        'macros': macros,
    }
    
    return render(request, 'macros/select_macros.html', context)


@login_required
def upload_user_file_for_download(request, file_id):
    """Step 2: User uploads their KeyCommands.xml file to embed selected macros"""
    keycommands_file = get_object_or_404(KeyCommandsFile, id=file_id)
    
    # Check permissions
    if keycommands_file.is_private and keycommands_file.user != request.user:
        raise Http404("Key Commands file not found")
    
    # Check if we have selected macros in session
    selected_macro_data = request.session.get('download_selected_macros')
    if not selected_macro_data or str(file_id) != selected_macro_data.get('file_id'):
        messages.error(request, 'Please select macros first.')
        return redirect('macros:download_selected_macros', file_id=file_id)
    
    # Get selected macros info for display
    selected_macro_ids = selected_macro_data.get('macro_ids', [])
    selected_macros = Macro.objects.filter(
        id__in=selected_macro_ids,
        keycommands_file=keycommands_file
    ).select_related('category')
    
    if request.method == 'POST':
        if 'user_file' not in request.FILES:
            messages.error(request, 'Please upload your KeyCommands.xml file.')
            return redirect('macros:upload_user_file_for_download', file_id=file_id)
        
        user_file = request.FILES['user_file']
        
        # Validate file
        if not user_file.name.lower().endswith('.xml'):
            messages.error(request, 'Please upload a valid XML file.')
            return redirect('macros:upload_user_file_for_download', file_id=file_id)
        
        # Read and validate XML
        try:
            user_file_content = user_file.read().decode('utf-8')
            user_root = ET.fromstring(user_file_content)
        except UnicodeDecodeError:
            messages.error(request, 'Invalid file encoding. Please ensure the file is UTF-8 encoded.')
            return redirect('macros:upload_user_file_for_download', file_id=file_id)
        except ET.ParseError as e:
            messages.error(request, f'Invalid XML file: {str(e)}')
            return redirect('macros:upload_user_file_for_download', file_id=file_id)
        
        # Embed macros
        try:
            # Add macro definitions to Macros list
            macros_list = user_root.find('list[@name="Macros"]')
            if macros_list is None:
                macros_list = ET.SubElement(user_root, "list")
                macros_list.set("name", "Macros")
                macros_list.set("type", "list")
            
            # Add macro references to Commands list
            categories_list = user_root.find('list[@name="Categories"]')
            commands_list = None
            
            if categories_list is not None:
                # Find or create Macro category
                macro_category_item = None
                for item in categories_list.findall('item'):
                    name_string = item.find('string[@name="Name"]')
                    if name_string is not None and name_string.attrib.get('value') == "Macro":
                        macro_category_item = item
                        break
                
                if macro_category_item is None:
                    macro_category_item = ET.SubElement(categories_list, "item")
                    ET.SubElement(macro_category_item, "string", name="Name", value="Macro")
                
                commands_list = macro_category_item.find('list[@name="Commands"]')
                if commands_list is None:
                    commands_list = ET.SubElement(macro_category_item, "list")
                    commands_list.set("name", "Commands")
                    commands_list.set("type", "list")
            
            # Add each selected macro
            for macro in selected_macros:
                # Add macro definition
                if macro.xml_snippet:
                    try:
                        macro_element = ET.fromstring(macro.xml_snippet)
                        macros_list.append(macro_element)
                    except ET.ParseError:
                        logger.warning(f"Failed to parse XML snippet for macro {macro.name}")
                
                # Add macro reference to Commands list
                if commands_list is not None:
                    if macro.reference_snippet:
                        try:
                            ref_element = ET.fromstring(macro.reference_snippet)
                            commands_list.append(ref_element)
                        except ET.ParseError:
                            # Fallback: create simple reference
                            macro_ref_item = ET.SubElement(commands_list, 'item')
                            ET.SubElement(macro_ref_item, 'string', name='Name', value=macro.name)
                    else:
                        # Fallback: create simple reference
                        macro_ref_item = ET.SubElement(commands_list, 'item')
                        ET.SubElement(macro_ref_item, 'string', name='Name', value=macro.name)
            
            # Generate XML string
            xml_str = ET.tostring(user_root, encoding='unicode', method='xml')
            xml_content = '<?xml version="1.0" encoding="utf-8"?>\n' + xml_str
            
            # Create download records
            for macro in selected_macros:
                MacroDownload.objects.create(
                    macro=macro,
                    user=request.user,
                    ip_address=get_client_ip(request)
                )
                Macro.objects.filter(id=macro.id).update(download_count=F('download_count') + 1)
            
            # Clear session
            del request.session['download_selected_macros']
            
            # Create response
            response = HttpResponse(xml_content, content_type='application/xml')
            filename = f"KeyCommands_with_macros.xml"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            messages.success(request, f'Successfully embedded {selected_macros.count()} macro(s) into your file!')
            return response
            
        except Exception as e:
            logger.error(f"Error embedding macros: {e}", exc_info=True)
            messages.error(request, f'Error embedding macros into your file: {str(e)}')
            return redirect('macros:upload_user_file_for_download', file_id=file_id)
    
    # GET request - show file upload form
    context = {
        'keycommands_file': keycommands_file,
        'selected_macros': selected_macros,
        'selected_count': selected_macros.count(),
    }
    
    return render(request, 'macros/upload_user_file_for_download.html', context)


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
@require_http_methods(["POST"])
def delete_keycommands_file(request, file_id):
    """Delete a Key Commands file"""
    keycommands_file = get_object_or_404(KeyCommandsFile, id=file_id)
    
    # Check permissions - only the owner can delete
    if keycommands_file.user != request.user:
        messages.error(request, 'You do not have permission to delete this file.')
        return redirect('macros:my_keycommands')
    
    # Delete the file (this will cascade delete all associated macros)
    file_name = keycommands_file.name
    keycommands_file.delete()
    
    messages.success(request, f'File "{file_name}" has been deleted successfully.')
    return redirect('macros:my_keycommands')


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
    macros = Macro.objects.filter(is_private=False).select_related(
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
        macro_count=Count('macro', filter=Q(macro__is_private=False))
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
        is_private=False
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
                is_private=False
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
        is_private=False
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
        macro__is_private=False
    ).annotate(
        macro_count=Count('macro', filter=Q(macro__is_private=False))
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
