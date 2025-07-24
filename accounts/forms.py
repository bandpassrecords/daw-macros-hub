from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile


class CustomUserCreationForm(UserCreationForm):
    """Custom user registration form with additional fields"""
    email = forms.EmailField(required=True, help_text="Required. Enter a valid email address.")
    first_name = forms.CharField(max_length=30, required=False, help_text="Optional.")
    last_name = forms.CharField(max_length=30, required=False, help_text="Optional.")
    
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes to form fields
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if field_name == 'email':
                field.widget.attrs['placeholder'] = 'Enter your email address'
            elif field_name == 'username':
                field.widget.attrs['placeholder'] = 'Choose a username'
            elif field_name == 'first_name':
                field.widget.attrs['placeholder'] = 'First name (optional)'
            elif field_name == 'last_name':
                field.widget.attrs['placeholder'] = 'Last name (optional)'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


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
    """Form for updating basic user information"""
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True 