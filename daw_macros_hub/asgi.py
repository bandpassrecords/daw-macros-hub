"""
ASGI config for daw_macros_hub project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Production ASGI - uses production settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'daw_macros_hub.settings.production')

application = get_asgi_application()
