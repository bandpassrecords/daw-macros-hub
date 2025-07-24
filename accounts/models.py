from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """Extended user profile model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    preferred_cubase_version = models.CharField(max_length=50, blank=True)
    
    # Privacy settings
    show_email = models.BooleanField(default=False)
    show_real_name = models.BooleanField(default=True)
    
    # Account settings
    email_notifications = models.BooleanField(default=True)
    newsletter_subscription = models.BooleanField(default=False)
    
    # Stats
    total_uploads = models.PositiveIntegerField(default=0)
    total_downloads = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    @property
    def display_name(self):
        """Return the display name for the user"""
        if self.show_real_name and (self.user.first_name or self.user.last_name):
            return f"{self.user.first_name} {self.user.last_name}".strip()
        return self.user.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create or update user profile when user is created or updated"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save user profile when user is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        UserProfile.objects.create(user=instance)
