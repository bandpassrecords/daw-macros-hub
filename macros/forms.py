from django import forms
from django.core.exceptions import ValidationError
from .models import KeyCommandsFile, Macro, MacroVote, MacroCollection, CubaseVersion
from .utils import KeyCommandsParser


class KeyCommandsFileForm(forms.ModelForm):
    """Form for uploading Key Commands XML files"""
    
    class Meta:
        model = KeyCommandsFile
        fields = ['name', 'description', 'file', 'cubase_version', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter a name for your Key Commands file'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your Key Commands setup (optional)'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control-file',
                'accept': '.xml'
            }),
            'cubase_version': forms.Select(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'name': 'Give your Key Commands file a descriptive name.',
            'description': 'Optional description of what makes this setup special.',
            'file': 'Upload your Key Commands.xml file exported from Cubase.',
            'cubase_version': 'Select the Cubase version this file was created with.',
            'is_public': 'Allow other users to see and use macros from this file.',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cubase_version'].queryset = CubaseVersion.objects.all()
        self.fields['cubase_version'].empty_label = "Select Cubase Version"
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size (10MB limit)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("File size cannot exceed 10MB.")
            
            # Check file extension
            if not file.name.lower().endswith('.xml'):
                raise ValidationError("Only XML files are allowed.")
            
            # Validate XML content
            try:
                file.seek(0)  # Reset file pointer
                content = file.read().decode('utf-8')
                file.seek(0)  # Reset again for later use
                
                # Basic XML validation
                try:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(content)
                    
                    # Check if it's a Key Commands file
                    if root.tag != 'KeyCommands':
                        raise ValidationError("Invalid Key Commands file: Root element must be 'KeyCommands'")
                    
                    # Check for either Macros or Categories section (both are valid Cubase formats)
                    macros_list = root.find(".//list[@name='Macros']")
                    categories_list = root.find(".//list[@name='Categories']")
                    
                    if macros_list is None and categories_list is None:
                        raise ValidationError("Invalid Key Commands file: No Macros or Categories section found")
                    
                    # Check if there are any items in whichever section exists
                    items_found = False
                    if macros_list is not None:
                        macro_items = macros_list.findall("item")
                        items_found = len(macro_items) > 0
                    
                    if categories_list is not None and not items_found:
                        category_items = categories_list.findall("item")
                        items_found = len(category_items) > 0
                        
                    if not items_found:
                        raise ValidationError("Invalid Key Commands file: No macros or categories found")
                        
                except ET.ParseError as pe:
                    raise ValidationError(f"Invalid XML format: {pe}")
                    
            except UnicodeDecodeError:
                raise ValidationError("File must be a valid UTF-8 encoded XML file.")
            except ValidationError:
                raise  # Re-raise validation errors
            except Exception as e:
                raise ValidationError(f"Error validating file: {str(e)}")
        
        return file


class MacroForm(forms.ModelForm):
    """Form for editing individual macros"""
    
    class Meta:
        model = Macro
        fields = ['name', 'description', 'key_binding', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Macro name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe what this macro does (optional)'
            }),
            'key_binding': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Ctrl+Alt+M'
            }),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'name': 'Name of the macro/command.',
            'description': 'Optional description of what this macro does.',
            'key_binding': 'Keyboard shortcut for this macro.',
            'is_public': 'Allow other users to discover and use this macro.',
        }


class MacroVoteForm(forms.ModelForm):
    """Form for voting/rating macros"""
    
    class Meta:
        model = MacroVote
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Share your thoughts about this macro (optional)'
            }),
        }
        help_texts = {
            'rating': 'Rate this macro from 1 to 5 stars.',
            'comment': 'Optional comment about your experience with this macro.',
        }


class MacroCollectionForm(forms.ModelForm):
    """Form for creating macro collections"""
    
    class Meta:
        model = MacroCollection
        fields = ['name', 'description', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Collection name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe this collection of macros'
            }),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'name': 'Name for your macro collection.',
            'description': 'Describe what type of macros are in this collection.',
            'is_public': 'Allow other users to see this collection.',
        }


class MacroSearchForm(forms.Form):
    """Form for searching macros"""
    SORT_CHOICES = [
        ('newest', 'Newest First'),
        ('oldest', 'Oldest First'),
        ('most_popular', 'Most Popular'),
        ('highest_rated', 'Highest Rated'),
        ('most_downloaded', 'Most Downloaded'),
        ('alphabetical', 'Alphabetical'),
    ]
    
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search macros...'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    cubase_version = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="All Versions",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    sort_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='newest',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    has_key_binding = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import MacroCategory
        
        self.fields['category'].queryset = MacroCategory.objects.all()
        self.fields['cubase_version'].queryset = CubaseVersion.objects.all()


class CubaseVersionForm(forms.ModelForm):
    """Form for adding new Cubase versions"""
    
    class Meta:
        model = CubaseVersion
        fields = ['version', 'major_version', 'minor_version', 'patch_version']
        widgets = {
            'version': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Cubase 13.0.1'
            }),
            'major_version': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '13'
            }),
            'minor_version': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0'
            }),
            'patch_version': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '1'
            }),
        }
        help_texts = {
            'version': 'Full version string as it appears in Cubase.',
            'major_version': 'Major version number.',
            'minor_version': 'Minor version number.',
            'patch_version': 'Patch version number.',
        }


class MacroSelectionForm(forms.Form):
    """Form for selecting macros to include in a download"""
    
    def __init__(self, macros, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for macro in macros:
            field_name = f'macro_{macro.id}'
            self.fields[field_name] = forms.BooleanField(
                required=False,
                label=macro.name,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            ) 