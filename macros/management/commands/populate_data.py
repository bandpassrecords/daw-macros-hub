from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from macros.models import CubaseVersion, MacroCategory
from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Populate the database with initial data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before populating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            CubaseVersion.objects.all().delete()
            MacroCategory.objects.all().delete()

        self.stdout.write('Creating Cubase versions...')
        self.create_cubase_versions()
        
        self.stdout.write('Creating macro categories...')
        self.create_categories()
        
        self.stdout.write('Creating sample users...')
        self.create_sample_users()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully populated database with initial data')
        )

    def create_cubase_versions(self):
        """Create common Cubase versions"""
        versions = [
            {'version': 'Cubase 13.0.30', 'major': 13, 'minor': 0, 'patch': 30},
            {'version': 'Cubase 13.0.20', 'major': 13, 'minor': 0, 'patch': 20},
            {'version': 'Cubase 13.0.10', 'major': 13, 'minor': 0, 'patch': 10},
            {'version': 'Cubase 13.0.0', 'major': 13, 'minor': 0, 'patch': 0},
            {'version': 'Cubase 12.0.70', 'major': 12, 'minor': 0, 'patch': 70},
            {'version': 'Cubase 12.0.60', 'major': 12, 'minor': 0, 'patch': 60},
            {'version': 'Cubase 12.0.52', 'major': 12, 'minor': 0, 'patch': 52},
            {'version': 'Cubase 12.0.40', 'major': 12, 'minor': 0, 'patch': 40},
            {'version': 'Cubase 12.0.30', 'major': 12, 'minor': 0, 'patch': 30},
            {'version': 'Cubase 12.0.20', 'major': 12, 'minor': 0, 'patch': 20},
            {'version': 'Cubase 12.0.10', 'major': 12, 'minor': 0, 'patch': 10},
            {'version': 'Cubase 12.0.0', 'major': 12, 'minor': 0, 'patch': 0},
            {'version': 'Cubase 11.0.41', 'major': 11, 'minor': 0, 'patch': 41},
            {'version': 'Cubase 11.0.40', 'major': 11, 'minor': 0, 'patch': 40},
            {'version': 'Cubase 11.0.30', 'major': 11, 'minor': 0, 'patch': 30},
            {'version': 'Cubase 11.0.20', 'major': 11, 'minor': 0, 'patch': 20},
            {'version': 'Cubase 11.0.10', 'major': 11, 'minor': 0, 'patch': 10},
            {'version': 'Cubase 11.0.0', 'major': 11, 'minor': 0, 'patch': 0},
            {'version': 'Cubase 10.5.20', 'major': 10, 'minor': 5, 'patch': 20},
            {'version': 'Cubase 10.5.12', 'major': 10, 'minor': 5, 'patch': 12},
            {'version': 'Cubase 10.5.0', 'major': 10, 'minor': 5, 'patch': 0},
            {'version': 'Cubase 10.0.60', 'major': 10, 'minor': 0, 'patch': 60},
            {'version': 'Cubase 10.0.50', 'major': 10, 'minor': 0, 'patch': 50},
            {'version': 'Cubase 10.0.40', 'major': 10, 'minor': 0, 'patch': 40},
            {'version': 'Cubase 10.0.30', 'major': 10, 'minor': 0, 'patch': 30},
            {'version': 'Cubase 10.0.20', 'major': 10, 'minor': 0, 'patch': 20},
            {'version': 'Cubase 10.0.15', 'major': 10, 'minor': 0, 'patch': 15},
            {'version': 'Cubase 10.0.10', 'major': 10, 'minor': 0, 'patch': 10},
            {'version': 'Cubase 10.0.0', 'major': 10, 'minor': 0, 'patch': 0},
        ]

        for version_data in versions:
            version, created = CubaseVersion.objects.get_or_create(
                version=version_data['version'],
                defaults={
                    'major_version': version_data['major'],
                    'minor_version': version_data['minor'],
                    'patch_version': version_data['patch'],
                }
            )
            if created:
                self.stdout.write(f'  Created: {version.version}')

    def create_categories(self):
        """Create common macro categories based on the XML file"""
        categories = [
            'Preferences',
            'Process Logical Preset',
            'Process Project Logical Editor',
            'MIDI',
            'Editors',
            'Edit',
            'MIDI Quantize',
            'Quantize Category',
            'Set Insert Length',
            'Devices',
            'Beat Designer',
            'Mixer',
            'Crossfade Editor',
            'Media',
            'File',
            'Transport',
            'Project',
            'Audio',
            'Video',
            'Zoom',
            'Snap/Quantize',
            'Navigate',
            'Nudge',
            'Select',
            'Macros',
            'Process',
            'Windows',
            'Functions',
            'Tools',
            'Generic Remote',
            'Expression Maps',
            'VST',
            'Control Room',
            'Score',
            'Sampler Control',
            'LoopMash',
            'Automation',
            'Marker',
            'Comping',
            'Track Versions',
            'Key Commands',
        ]

        for category_name in categories:
            category, created = MacroCategory.objects.get_or_create(
                name=category_name
            )
            if created:
                self.stdout.write(f'  Created category: {category_name}')

    def create_sample_users(self):
        """Create sample users for demonstration"""
        sample_users = [
            {
                'username': 'john_producer',
                'email': 'john@example.com',
                'first_name': 'John',
                'last_name': 'Producer',
                'bio': 'Electronic music producer specializing in techno and house music.',
                'location': 'Berlin, Germany',
                'preferred_cubase_version': 'Cubase 13'
            },
            {
                'username': 'sarah_composer',
                'email': 'sarah@example.com',
                'first_name': 'Sarah',
                'last_name': 'Composer',
                'bio': 'Film composer with 10+ years of experience in orchestral arrangements.',
                'location': 'Los Angeles, CA',
                'preferred_cubase_version': 'Cubase 12'
            },
            {
                'username': 'mike_engineer',
                'email': 'mike@example.com',
                'first_name': 'Mike',
                'last_name': 'Engineer',
                'bio': 'Audio engineer working with various genres from rock to jazz.',
                'location': 'Nashville, TN',
                'preferred_cubase_version': 'Cubase 13'
            },
        ]

        for user_data in sample_users:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                }
            )
            
            if created:
                user.set_password('samplepass123')
                user.save()
                
                # Create or update profile
                profile, profile_created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'bio': user_data['bio'],
                        'location': user_data['location'],
                        'preferred_cubase_version': user_data['preferred_cubase_version'],
                        'show_real_name': True,
                        'email_notifications': True,
                    }
                )
                
                self.stdout.write(f'  Created user: {user.username}')
            else:
                self.stdout.write(f'  User already exists: {user.username}') 