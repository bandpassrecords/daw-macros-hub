from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from .models import UserProfile


class CustomUserCreationForm(UserCreationForm):
    """Custom user registration form - email only, no username, no first/last name"""
    email = forms.EmailField(required=True, help_text="Required. Enter a valid email address.")
    email2 = forms.EmailField(required=True, label="Confirm Email", help_text="Enter the same email address again for verification.")
    
    class Meta:
        model = User
        fields = ("email", "email2", "password1", "password2")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username field
        if 'username' in self.fields:
            del self.fields['username']
        # Add CSS classes to form fields (no placeholders)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control form-control-lg'
            if field_name == 'email':
                field.widget.attrs['autocomplete'] = 'email'
                field.help_text = None
            elif field_name == 'email2':
                field.widget.attrs['autocomplete'] = 'email'
                field.help_text = None
            elif field_name == 'password1':
                field.widget.attrs['autocomplete'] = 'new-password'
                # Keep help_text for error display (template will show it only on error)
            elif field_name == 'password2':
                field.widget.attrs['autocomplete'] = 'new-password'
                # Remove the default help text for password2
                field.help_text = None
    
    def clean_email2(self):
        """Verify that both email fields match"""
        email = self.cleaned_data.get('email')
        email2 = self.cleaned_data.get('email2')
        if email and email2 and email != email2:
            raise forms.ValidationError("The two email fields didn't match.")
        return email2
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]  # Set username to email for compatibility
        if commit:
            user.save()
        return user


class DeleteAccountForm(forms.Form):
    """Form for account deletion with option to delete macros"""
    delete_macros = forms.BooleanField(
        required=False,
        label="I want to delete all my uploaded macros",
        help_text="If checked, you explicitly confirm you want to delete all your macros. Note: Due to system limitations, macros cannot be kept after account deletion, so they will be removed regardless of this setting."
    )
    confirm_delete = forms.BooleanField(
        required=True,
        label="I understand this action cannot be undone",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile"""
    
    class Meta:
        model = UserProfile
        fields = [
            'bio', 'location', 'website', 'avatar', 'preferred_cubase_version',
            'show_email', 'show_real_name', 'email_notifications', 'newsletter_subscription'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Tell us about yourself...'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Los Angeles, CA'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://yourwebsite.com'}),
            'preferred_cubase_version': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Cubase 13'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control-file'}),
            'show_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_real_name': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'newsletter_subscription': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'bio': 'Brief description about yourself and your music production background.',
            'location': 'Your location (city, state/country).',
            'website': 'Your personal website or portfolio.',
            'preferred_cubase_version': 'The version of Cubase you primarily use.',
            'show_email': 'Allow other users to see your email address.',
            'show_real_name': 'Use your real name instead of username in public.',
            'email_notifications': 'Receive email notifications for interactions.',
            'newsletter_subscription': 'Subscribe to our newsletter for updates.',
        }


class UserUpdateForm(forms.ModelForm):
    """Form for updating basic user information - email only, no username"""
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        # Remove username field if it exists
        if 'username' in self.fields:
            del self.fields['username']


class CustomPasswordResetForm(PasswordResetForm):
    """Custom password reset form with Bootstrap styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })


class CustomSetPasswordForm(SetPasswordForm):
    """Custom set password form with Bootstrap styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter new password'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
