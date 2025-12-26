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
    Macro, MacroVote, MacroFavorite, 
    MacroCollection, MacroDownload, CubaseVersion
)
from .forms import (
    MacroUploadForm, MacroForm, MacroVoteForm, MacroCollectionForm,
    MacroSearchForm, MacroSelectionForm
)
from .utils import KeyCommandsParser, create_keycommands_xml, create_keycommands_xml_with_embedded_macros, get_client_ip

logger = logging.getLogger(__name__)


def macro_list(request):
    """Public macro listing with search and filtering"""
    form = MacroSearchForm(request.GET or None)
    
    # Start with public macros (is_private=False means public)
    macros = Macro.objects.filter(is_private=False).select_related(
        'user', 'cubase_version'
    ).annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes')
    )
    
    # Apply filters
    if form.is_valid():
        query = form.cleaned_data.get('query')
        cubase_version = form.cleaned_data.get('cubase_version')
        sort_by = form.cleaned_data.get('sort_by', 'newest')
        has_key_binding = form.cleaned_data.get('has_key_binding')
        
        if query:
            macros = macros.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )
        
        if cubase_version:
            macros = macros.filter(cubase_version=cubase_version)
        
        if has_key_binding:
            macros = macros.exclude(Q(key_binding='') | Q(key_binding__isnull=True))
        
        # Apply sorting
        if sort_by == 'newest':
            macros = macros.order_by('-created_at')
        elif sort_by == 'oldest':
            macros = macros.order_by('created_at')
        elif sort_by == 'most_popular':
            macros = macros.order_by('-download_count', '-created_at')
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
    
    # Get favorited macro IDs for the current user (for all macros on current page)
    favorited_macro_ids = set()
    if request.user.is_authenticated and page_obj:
        macro_ids = [macro.id for macro in page_obj]
        favorited_macro_ids = set(
            MacroFavorite.objects.filter(
                user=request.user,
                macro_id__in=macro_ids
            ).values_list('macro_id', flat=True)
        )
    
    # Add is_favorited attribute to each macro
    for macro in page_obj:
        macro.is_favorited = macro.id in favorited_macro_ids
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'total_count': paginator.count,
    }
    
    return render(request, 'macros/macro_list.html', context)


def macro_detail_by_secret(request, secret_token):
    """View a private macro using a secret token"""
    macro = get_object_or_404(
        Macro.objects.select_related(
            'user', 'cubase_version'
        ).prefetch_related('votes__user'),
        secret_token=secret_token
    )
    
    # Only allow access to private macros via secret token
    if not macro.is_private:
        messages.warning(request, 'This macro is public. Use the regular link to access it.')
        return redirect('macros:macro_detail', macro_id=macro.id)
    
    # Store the secret token in session to allow adding to cart
    if 'secret_accessible_macros' not in request.session:
        request.session['secret_accessible_macros'] = []
    if str(macro.id) not in request.session['secret_accessible_macros']:
        request.session['secret_accessible_macros'].append(str(macro.id))
        request.session.modified = True
    
    # Use the same context as macro_detail
    return _render_macro_detail(request, macro, is_secret_link=True)


def macro_detail(request, macro_id):
    """Detailed view of a macro with voting"""
    macro = get_object_or_404(
        Macro.objects.select_related(
            'user', 'cubase_version'
        ).prefetch_related('votes__user'),
        id=macro_id
    )
    
    # Check permissions - allow public macros (is_private=False) or private macros owned by the user
    if macro.is_private and (not request.user.is_authenticated or macro.user != request.user):
        raise Http404("Macro not found")
    
    return _render_macro_detail(request, macro, is_secret_link=False)


def _render_macro_detail(request, macro, is_secret_link=False):
    """Helper function to render macro detail page"""
    
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
    
    # Get related macros
    related_macros = Macro.objects.filter(
        is_private=False
    ).exclude(id=macro.id).select_related('user').annotate(
        avg_rating=Avg('votes__rating')
    ).order_by('-avg_rating', '-download_count')[:5]
    
    context = {
        'macro': macro,
        'vote_form': vote_form,
        'user_vote': user_vote,
        'is_favorited': is_favorited,
        'recent_votes': recent_votes,
        'related_macros': related_macros,
        'is_secret_link': is_secret_link,
    }
    
    return render(request, 'macros/macro_detail.html', context)


@login_required
def upload_keycommands(request):
    """Upload and parse Macros file (Key Commands.xml) in memory - show selection page instead of saving file"""
    if request.method == 'POST':
        form = MacroUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Get file from form but don't save it
                uploaded_file = form.cleaned_data['file']
                
                # Read file content into memory
                uploaded_file.seek(0)
                file_content = uploaded_file.read().decode('utf-8')
                
                logger.info(f"Parsing Macros file (Key Commands.xml) in memory: {uploaded_file.name}")
                
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
                        logger.info(f"Using default 'Unspecified' version for upload")
                    except CubaseVersion.DoesNotExist:
                        logger.warning("'Unspecified' CubaseVersion not found, creating it")
                        cubase_version = CubaseVersion.objects.create(
                            version='Unspecified',
                            major_version=0
                        )
                
                # Log the version being used
                logger.info(f"Upload using Cubase version: {cubase_version.version} (ID: {cubase_version.id})")
                
                # Store parsed data in session for the selection step
                request.session['upload_data'] = {
                    'cubase_version_id': cubase_version.id if cubase_version else None,
                    'macros': all_macros,
                    'file_name': uploaded_file.name,
                }
                
                logger.info(f"Found {len(all_macros)} macros for selection")
                messages.success(request, f'Found {len(all_macros)} macros in your file. Please select which ones to save.')
                
                # Redirect to selection page
                return redirect('macros:select_macros_upload')
                
            except Exception as e:
                logger.error(f"Error parsing Macros file (Key Commands.xml): {e}", exc_info=True)
                
                if "No macros found" in str(e) or "No valid macros" in str(e):
                    messages.error(request, "The uploaded file doesn't contain any valid macros. Please check that your file was exported correctly from Cubase.")
                elif "Invalid XML" in str(e) or "XML parsing error" in str(e):
                    messages.error(request, "The uploaded file is not a valid XML file. Please ensure you're uploading a Macros file (Key Commands.xml) from Cubase.")
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
        form = MacroUploadForm()
    
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
    
    if request.method == 'POST':
        # Get selected macro indices
        selected_indices = request.POST.getlist('selected_macros')
        
        if not selected_indices:
            messages.warning(request, 'Please select at least one macro to save.')
            return render(request, 'macros/select_macros_upload.html', {
                'upload_data': upload_data,
                'macros': macros_with_index,
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
        'macros': macros_with_index,
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
                    logger.info(f"Using default 'Unspecified' version for macro save")
                except CubaseVersion.DoesNotExist:
                    logger.warning("'Unspecified' CubaseVersion not found during save, creating it")
                    unspecified_version = CubaseVersion.objects.create(
                        version='Unspecified',
                        major_version=0
                    )
                    cubase_version_id = unspecified_version.id
            
            # Log the version ID being used
            logger.info(f"Saving macros with Cubase version ID: {cubase_version_id}")
            
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
                    # Note: cubase_version is stored per macro from the upload form
                    macro, created = Macro.objects.update_or_create(
                        user=request.user,
                        name=macro_data['name'],
                        defaults={
                            'cubase_version_id': cubase_version_id,  # Each macro gets the Cubase version from upload
                            'description': description,
                            'key_binding': key_binding,
                            'commands_json': commands,
                            'xml_snippet': macro_data.get('xml_snippet', ''),
                            'reference_snippet': macro_data.get('reference_snippet', ''),
                            'is_private': macro_is_private,  # Use individual macro privacy setting
                        }
                    )
                    
                    # Log if version was saved correctly (for debugging)
                    if macro.cubase_version_id != cubase_version_id:
                        logger.warning(f"Macro {macro.id} version mismatch: expected {cubase_version_id}, got {macro.cubase_version_id}")
                    else:
                        logger.debug(f"Macro {macro.id} '{macro.name}' saved with version ID: {cubase_version_id}")
                    
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
            logger.info(f"Saved {created_macros} macros for user {request.user.username}")
            
            return redirect('accounts:profile')
            
    except Exception as e:
        logger.error(f"Error saving selected macros: {e}", exc_info=True)
        messages.error(request, f"Error saving macros: {str(e)}")
        return redirect('macros:upload_keycommands')


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
def toggle_visibility(request, macro_id):
    """Toggle private/public status for a macro (AJAX)"""
    macro = get_object_or_404(Macro, id=macro_id, user=request.user)
    
    macro.is_private = not macro.is_private
    macro.save()
    
    return JsonResponse({
        'success': True,
        'is_private': macro.is_private,
        'message': 'Macro is now ' + ('private' if macro.is_private else 'public')
    })


@login_required
@require_http_methods(["POST"])
def generate_secret_link(request, macro_id):
    """Generate or regenerate a secret link for a private macro (AJAX)"""
    macro = get_object_or_404(Macro, id=macro_id, user=request.user)
    
    if not macro.is_private:
        return JsonResponse({
            'success': False,
            'message': 'Secret links are only available for private macros.'
        })
    
    # Generate or regenerate the secret token
    secret_token = macro.generate_secret_token()
    secret_link = request.build_absolute_uri(f'/macros/share/{secret_token}/')
    
    return JsonResponse({
        'success': True,
        'secret_link': secret_link,
        'message': 'Secret link generated successfully!'
    })



@login_required
def add_to_cart(request, macro_id):
    """Add a macro to the user's cart (staging area)"""
    # Check if macro exists
    macro = get_object_or_404(Macro, id=macro_id)
    
    # Allow adding to cart if:
    # 1. Macro is public (is_private=False)
    # 2. Macro is private but user owns it
    # 3. Macro is private but user accessed it via secret link (stored in session)
    can_add = False
    if not macro.is_private:
        can_add = True
    elif request.user.is_authenticated and macro.user == request.user:
        can_add = True
    elif request.session.get('secret_accessible_macros') and str(macro_id) in request.session['secret_accessible_macros']:
        can_add = True
    
    if not can_add:
        return JsonResponse({
            'success': False, 
            'message': 'This macro is private and cannot be added to cart', 
            'cart_count': len(request.session.get('macro_cart', []))
        })
    
    # Initialize cart if it doesn't exist
    if 'macro_cart' not in request.session:
        request.session['macro_cart'] = []
    
    cart = request.session['macro_cart']
    macro_id_str = str(macro_id)
    
    # Check if macro is already in cart
    if macro_id_str not in cart:
        cart.append(macro_id_str)
        request.session['macro_cart'] = cart
        request.session.modified = True
        return JsonResponse({'success': True, 'message': 'Macro added to cart', 'cart_count': len(cart)})
    else:
        return JsonResponse({'success': False, 'message': 'Macro already in cart', 'cart_count': len(cart)})


@login_required
@require_http_methods(["POST"])
def remove_from_cart(request, macro_id):
    """Remove a macro from the user's cart"""
    macro_id_str = str(macro_id)
    
    if 'macro_cart' in request.session:
        cart = request.session['macro_cart']
        if macro_id_str in cart:
            cart.remove(macro_id_str)
            request.session['macro_cart'] = cart
            request.session.modified = True
            return JsonResponse({'success': True, 'message': 'Macro removed from cart', 'cart_count': len(cart)})
    
    return JsonResponse({'success': False, 'message': 'Macro not in cart', 'cart_count': len(request.session.get('macro_cart', []))})


@login_required
def view_cart(request):
    """View all macros in the cart (staging area)"""
    cart = request.session.get('macro_cart', [])
    
    if not cart:
        context = {
            'macros': [],
            'cart_count': 0,
        }
        return render(request, 'macros/cart.html', context)
    
    # Get all macros in cart
    macros = Macro.objects.filter(
        id__in=cart,
        is_private=False
    ).select_related('user').annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes')
    ).order_by('name')
    
    context = {
        'macros': macros,
        'cart_count': len(cart),
    }
    
    return render(request, 'macros/cart.html', context)


@login_required
def clear_cart(request):
    """Clear all macros from the cart"""
    if 'macro_cart' in request.session:
        del request.session['macro_cart']
        request.session.modified = True
        messages.success(request, 'Cart cleared successfully.')
    return redirect('macros:view_cart')


@login_required
def upload_and_download(request):
    """Upload user's Key Commands.xml file and embed all macros from cart"""
    cart = request.session.get('macro_cart', [])
    
    if not cart:
        messages.error(request, 'Your cart is empty. Please add some macros first.')
        return redirect('macros:view_cart')
    
    # Get all macros in cart
    selected_macros = Macro.objects.filter(
        id__in=cart,
        is_private=False
    )
    
    if request.method == 'POST':
        user_file = request.FILES.get('user_file')
        if not user_file:
            messages.error(request, 'Please upload your Key Commands.xml file.')
            return redirect('macros:upload_and_download')
        
        # Validate file
        if not user_file.name.lower().endswith('.xml'):
            messages.error(request, 'Please upload a valid XML file.')
            return redirect('macros:upload_and_download')
        
        if user_file.size > 10 * 1024 * 1024:  # 10MB limit
            messages.error(request, 'File size must be less than 10MB.')
            return redirect('macros:upload_and_download')
        
        try:
            # Read and parse user's file
            user_file_content = user_file.read().decode('utf-8')
            user_root = ET.fromstring(user_file_content)
        except UnicodeDecodeError:
            messages.error(request, 'Invalid file encoding. Please ensure the file is UTF-8 encoded.')
            return redirect('macros:upload_and_download')
        except ET.ParseError as e:
            messages.error(request, f'Invalid XML file: {str(e)}')
            return redirect('macros:upload_and_download')
        
        try:
            # Use utility function to embed macros into user's file
            xml_content = create_keycommands_xml_with_embedded_macros(user_root, selected_macros)
            
            # Create download records
            for macro in selected_macros:
                MacroDownload.objects.create(
                    macro=macro,
                    user=request.user,
                    ip_address=get_client_ip(request)
                )
                Macro.objects.filter(id=macro.id).update(download_count=F('download_count') + 1)
            
            # Clear cart after successful download
            if 'macro_cart' in request.session:
                del request.session['macro_cart']
                request.session.modified = True
            
            # Create download response
            response = HttpResponse(xml_content, content_type='application/xml')
            filename = f"Key Commands.xml"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            messages.success(request, f'Successfully embedded {len(selected_macros)} macro(s) into your file!')
            return response
            
        except Exception as e:
            logger.error(f"Error embedding macros into user file: {e}")
            messages.error(request, f"Error processing your file: {str(e)}")
            return redirect('macros:upload_and_download')
    
    # GET request - show upload form
    context = {
        'selected_macros': selected_macros,
        'cart_count': len(cart),
    }
    
    return render(request, 'macros/upload_and_download.html', context)


@login_required
def edit_macro(request, macro_id):
    """Edit a macro"""
    # First check if macro exists
    try:
        macro = Macro.objects.get(id=macro_id)
    except Macro.DoesNotExist:
        messages.error(request, 'The macro you are trying to edit does not exist or has been deleted.')
        return redirect('macros:macro_list')
    
    # Check if user owns the macro
    if macro.user != request.user:
        messages.error(request, 'You do not have permission to edit this macro.')
        return redirect('macros:macro_detail', macro_id=macro.id)
    
    if request.method == 'POST':
        # Check if this is a delete action
        if request.POST.get('action') == 'delete_macro':
            macro_name = macro.name
            macro.delete()
            messages.success(request, f'Macro "{macro_name}" has been deleted successfully.')
            
            # Get the referrer URL or default to profile
            referer = request.META.get('HTTP_REFERER')
            if referer:
                # Check if referer is from the same site (basic security check)
                from django.http import HttpResponseRedirect
                from urllib.parse import urlparse
                
                referer_parsed = urlparse(referer)
                current_parsed = urlparse(request.build_absolute_uri())
                
                # Only redirect to referer if it's from the same domain and NOT the edit page
                if (referer_parsed.netloc == current_parsed.netloc or not referer_parsed.netloc) and '/edit/' not in referer_parsed.path:
                    return HttpResponseRedirect(referer)
            
            # Default to user profile if no referrer, referrer is external, or referrer is the edit page
            return redirect('accounts:profile')
        
        # Handle normal form submission
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
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # Get filter parameters
    timeframe = request.GET.get('timeframe', 'all')
    cubase_version_id = request.GET.get('cubase_version')
    sort_by = request.GET.get('sort_by', 'rating')
    
    # Start with public macros
    macros = Macro.objects.filter(is_private=False).select_related(
        'user', 'cubase_version'
    ).annotate(
        avg_rating=Avg('votes__rating'),
        total_votes=Count('votes', distinct=True),
        favorite_count=Count('favorited_by', distinct=True)
    )
    
    # Filter by timeframe
    if timeframe == 'week':
        week_ago = timezone.now() - timedelta(days=7)
        macros = macros.filter(created_at__gte=week_ago)
    elif timeframe == 'month':
        month_ago = timezone.now() - timedelta(days=30)
        macros = macros.filter(created_at__gte=month_ago)
    elif timeframe == 'year':
        year_ago = timezone.now() - timedelta(days=365)
        macros = macros.filter(created_at__gte=year_ago)
    
    # Filter by Cubase version
    if cubase_version_id:
        try:
            macros = macros.filter(cubase_version_id=cubase_version_id)
        except (ValueError, TypeError):
            pass
    
    # Apply sorting
    if sort_by == 'rating':
        macros = macros.order_by('-avg_rating', '-total_votes', '-download_count')
    elif sort_by == 'downloads':
        macros = macros.order_by('-download_count', '-created_at')
    elif sort_by == 'views':
        macros = macros.order_by('-download_count', '-created_at')  # Use downloads as fallback
    elif sort_by == 'favorites':
        macros = macros.order_by('-favorite_count', '-download_count')
    else:
        macros = macros.order_by('-avg_rating', '-total_votes', '-download_count')
    
    # Paginate results
    paginator = Paginator(macros, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get Cubase versions for filter dropdown
    cubase_versions = CubaseVersion.objects.all().order_by('-major_version')
    
    context = {
        'page_obj': page_obj,
        'cubase_versions': cubase_versions,
        'title': 'Most Popular Macros',
    }
    
    return render(request, 'macros/popular_macros.html', context)


