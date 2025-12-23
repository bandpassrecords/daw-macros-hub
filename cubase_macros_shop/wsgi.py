"""
WSGI config for cubase_macros_shop project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Production WSGI - uses production settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cubase_macros_shop.settings.production')

application = get_wsgi_application()
