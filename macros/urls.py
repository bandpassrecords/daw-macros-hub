from django.urls import path
from . import views

app_name = 'macros'

urlpatterns = [
    # Macro browsing
    path('', views.macro_list, name='macro_list'),
    path('macro/<uuid:macro_id>/', views.macro_detail, name='macro_detail'),
    path('popular/', views.popular_macros, name='popular_macros'),
    
    # Categories
    path('categories/', views.categories, name='categories'),
    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    
    # Key Commands file management
    path('upload/', views.upload_keycommands, name='upload_keycommands'),
    path('upload/select-macros/', views.select_macros_upload, name='select_macros_upload'),
    path('upload/save-macros/', views.save_selected_macros, name='save_selected_macros'),
    path('my-files/', views.my_keycommands, name='my_keycommands'),
    path('keycommands/<uuid:file_id>/', views.keycommands_detail, name='keycommands_detail'),
    path('keycommands/<uuid:file_id>/delete/', views.delete_keycommands_file, name='delete_keycommands_file'),
    
    # Downloads
    path('download/<uuid:file_id>/', views.download_keycommands, name='download_keycommands'),
    path('download-selected/<uuid:file_id>/', views.download_selected_macros, name='download_selected_macros'),
    path('upload-file-for-download/<uuid:file_id>/', views.upload_user_file_for_download, name='upload_user_file_for_download'),
    
    # Macro embedding
    path('embed-macros/<uuid:file_id>/', views.select_macros_for_file, name='select_macros_for_file'),
    
    # Macro management
    path('edit/<uuid:macro_id>/', views.edit_macro, name='edit_macro'),
    
    # AJAX endpoints
    path('favorite/<uuid:macro_id>/', views.toggle_favorite, name='toggle_favorite'),
] 