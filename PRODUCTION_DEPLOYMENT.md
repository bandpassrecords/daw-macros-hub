# Production Deployment Guide

This guide explains how to deploy your Django application to production with the production-ready settings.

**Related Guides:**
- `SYSTEMD_SERVICE_SETUP.md` - Detailed systemd service setup for auto-start on boot and cron jobs
- `LETS_ENCRYPT_SETUP.md` - Complete Let's Encrypt SSL certificate setup
- `ENV_SETUP_INSTRUCTIONS.md` - Environment variables configuration

## Prerequisites

1. Python 3.8+ installed
2. All dependencies installed: `pip install -r requirements.txt`
3. Database migrations run: `python manage.py migrate`
4. Static files collected: `python manage.py collectstatic`

## Environment Variables Setup

Create a `.env` file in your project root (same directory as `manage.py`) with the following variables:

```env
# Django Core Settings
DEBUG=False
SECRET_KEY=your-generated-secret-key-here
ALLOWED_HOSTS=cms.bandpassrecords.com

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=info@bandpassrecords.com
SERVER_EMAIL=info@bandpassrecords.com

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Security Settings (for production with SSL)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CSRF_TRUSTED_ORIGINS=https://cms.bandpassrecords.com

# Logging
DJANGO_LOG_LEVEL=INFO
```

## Generate Secret Key

Generate a secure secret key:

```bash
python manage.py shell
```

Then run:
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

Copy the output and use it as your `SECRET_KEY` in the `.env` file.

## Pre-Deployment Checklist

### 1. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

This will collect all static files into the `staticfiles` directory for WhiteNoise to serve.

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Create Superuser (if needed)

```bash
python manage.py createsuperuser
```

### 4. Update Site Domain

1. Go to Django Admin: `http://cms.bandpassrecords.com/admin/`
2. Navigate to Sites > Sites
3. Update the default site:
   - Domain name: `cms.bandpassrecords.com`
   - Display name: `Cubase Macros Hub`

### 5. Test the Application

```bash
python manage.py runserver
```

Visit your site and test:
- User registration
- Login/Logout
- Google OAuth (if configured)
- Password reset
- File uploads

## Production Server Setup

### Option 1: Using Gunicorn + Nginx (Recommended)

1. **Install Gunicorn:**
   ```bash
   pip install gunicorn
   ```

2. **Create Systemd Service for Auto-Start on Boot:**
   
   a. **Create service file:**
      ```bash
      sudo nano /etc/systemd/system/cubase-macros-shop.service
      ```
   
   b. **Add service configuration:**
      ```ini
      [Unit]
      Description=Gunicorn daemon for Cubase Macros Hub Django application
      After=network.target

      [Service]
      User=www-data
      Group=www-data
      WorkingDirectory=/path/to/your/project/cubase-macros-shop
      Environment="PATH=/path/to/venv/bin"
      EnvironmentFile=/path/to/your/project/.env
      ExecStart=/path/to/venv/bin/gunicorn \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          --access-logfile /var/log/gunicorn/access.log \
          --error-logfile /var/log/gunicorn/error.log \
          --env DJANGO_SETTINGS_MODULE=cubase_macros_shop.settings.production \
          cubase_macros_shop.wsgi:application

      Restart=always
      RestartSec=3

      [Install]
      WantedBy=multi-user.target
      ```
      
      **Important:** Replace `/path/to/your/project` and `/path/to/venv` with your actual paths!
   
   c. **Create log directory:**
      ```bash
      sudo mkdir -p /var/log/gunicorn
      sudo chown www-data:www-data /var/log/gunicorn
      ```
   
   d. **Reload systemd and enable service:**
      ```bash
      sudo systemctl daemon-reload
      sudo systemctl enable cubase-macros-shop.service
      sudo systemctl start cubase-macros-shop.service
      ```
   
   e. **Verify service is running:**
      ```bash
      sudo systemctl status cubase-macros-shop.service
      ```
      
      You should see `Active: active (running)`
   
   **See `SYSTEMD_SERVICE_SETUP.md` for detailed instructions and troubleshooting.**

4. **Install Let's Encrypt SSL Certificate:**
   
   a. **Install Certbot:**
      ```bash
      # Ubuntu/Debian
      sudo apt update
      sudo apt install certbot python3-certbot-nginx
      
      # CentOS/RHEL
      sudo yum install certbot python3-certbot-nginx
      ```
   
   b. **Obtain SSL Certificate:**
      ```bash
      sudo certbot --nginx -d cms.bandpassrecords.com
      ```
      
      Certbot will:
      - Ask for your email address (for renewal reminders)
      - Ask to agree to terms of service
      - Optionally ask to share email with EFF
      - Automatically configure Nginx with SSL
      - Set up automatic renewal
   
   c. **Test Auto-Renewal:**
      ```bash
      sudo certbot renew --dry-run
      ```
      
      This verifies that automatic renewal will work. Certbot automatically renews certificates before they expire (Let's Encrypt certificates are valid for 90 days).

5. **Configure Nginx** (`/etc/nginx/sites-available/cms.bandpassrecords.com`):
   ```nginx
   server {
       listen 80;
       server_name cms.bandpassrecords.com;
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name cms.bandpassrecords.com;

       # Let's Encrypt certificates (automatically configured by Certbot)
       ssl_certificate /etc/letsencrypt/live/cms.bandpassrecords.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/cms.bandpassrecords.com/privkey.pem;
       
       # SSL Configuration (recommended settings)
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_prefer_server_ciphers on;
       ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
       ssl_session_cache shared:SSL:10m;
       ssl_session_timeout 10m;
       
       # Security Headers
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
       add_header X-Frame-Options "DENY" always;
       add_header X-Content-Type-Options "nosniff" always;
       add_header X-XSS-Protection "1; mode=block" always;

       client_max_body_size 10M;

       location /static/ {
           alias /path/to/your/project/staticfiles/;
           expires 30d;
           add_header Cache-Control "public, immutable";
       }

       location /media/ {
           alias /path/to/your/project/media/;
           expires 30d;
       }

       location / {
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_pass http://unix:/run/gunicorn.sock;
       }
   }
   ```

6. **Enable Site and Restart Nginx:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/cms.bandpassrecords.com /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```
   
   **Note:** If you used Certbot in step 4, it may have already created and enabled the site configuration automatically.

## Let's Encrypt SSL Certificate Setup

### Initial Setup

1. **Prerequisites:**
   - Domain `cms.bandpassrecords.com` must point to your server's IP address
   - Port 80 (HTTP) must be open and accessible
   - Nginx must be installed and running

2. **Install Certbot:**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install certbot python3-certbot-nginx
   
   # CentOS/RHEL/Fedora
   sudo yum install certbot python3-certbot-nginx
   # or for newer versions:
   sudo dnf install certbot python3-certbot-nginx
   ```

3. **Obtain Certificate:**
   ```bash
   sudo certbot --nginx -d cms.bandpassrecords.com
   ```
   
   Follow the prompts:
   - Enter your email address (for renewal notifications)
   - Agree to terms of service
   - Choose whether to redirect HTTP to HTTPS (recommended: Yes)

4. **Verify Certificate:**
   ```bash
   sudo certbot certificates
   ```
   
   You should see your certificate listed with expiration date.

### Auto-Renewal

Let's Encrypt certificates expire after 90 days. Certbot automatically sets up renewal, but verify it works:

1. **Test Renewal:**
   ```bash
   sudo certbot renew --dry-run
   ```
   
   This simulates renewal without actually renewing the certificate.

2. **Check Renewal Timer:**
   ```bash
   sudo systemctl status certbot.timer
   ```
   
   Certbot runs twice daily to check for expiring certificates and renews them automatically.

3. **Manual Renewal (if needed):**
   ```bash
   sudo certbot renew
   ```

### Renewal Hooks (Optional)

You can add hooks to run commands after certificate renewal:

1. **Create renewal hook script:**
   ```bash
   sudo nano /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
   ```
   
   Add:
   ```bash
   #!/bin/bash
   systemctl reload nginx
   ```
   
2. **Make it executable:**
   ```bash
   sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
   ```

### Troubleshooting SSL

**Certificate not renewing:**
```bash
# Check renewal logs
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# Force renewal
sudo certbot renew --force-renewal
```

**Nginx not loading certificate:**
```bash
# Check certificate paths
sudo certbot certificates

# Verify Nginx can read certificates
sudo nginx -t

# Check file permissions
ls -la /etc/letsencrypt/live/cms.bandpassrecords.com/
```

**Port 80 blocked:**
- Let's Encrypt needs port 80 open for validation
- If behind a firewall, ensure port 80 is open
- If using CloudFlare or similar, ensure DNS is properly configured

### Option 2: Using Docker

Create a `Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "cubase_macros_shop.wsgi:application"]
```

### Option 3: Using Platform-as-a-Service

**Heroku:**
1. Install Heroku CLI
2. Create `Procfile`:
   ```
   web: gunicorn cubase_macros_shop.wsgi:application
   ```
3. Deploy: `git push heroku main`

**PythonAnywhere:**
1. Upload your code
2. Configure web app
3. Set environment variables in web app configuration

**Railway/Render:**
1. Connect your Git repository
2. Set environment variables in dashboard
3. Deploy automatically

## Security Checklist

- [ ] `DEBUG = False` in production
- [ ] `SECRET_KEY` is unique and secure (not in version control)
- [ ] `ALLOWED_HOSTS` includes your domain
- [ ] Let's Encrypt SSL certificate installed and working
- [ ] Certbot auto-renewal tested and working
- [ ] `SECURE_SSL_REDIRECT = True`
- [ ] `SESSION_COOKIE_SECURE = True`
- [ ] `CSRF_COOKIE_SECURE = True`
- [ ] `CSRF_TRUSTED_ORIGINS` includes your domain
- [ ] `.env` file is in `.gitignore`
- [ ] Database backups configured
- [ ] Error logging configured
- [ ] Email notifications for errors working

## Monitoring and Maintenance

### Logs

Logs are stored in `logs/django.log`. Monitor for errors:
```bash
tail -f logs/django.log
```

### Database Backups

For SQLite, regularly backup the database:
```bash
cp db.sqlite3 backups/db_$(date +%Y%m%d_%H%M%S).sqlite3
```

### Updates

1. Pull latest code
2. Install dependencies: `pip install -r requirements.txt`
3. Run migrations: `python manage.py migrate`
4. Collect static files: `python manage.py collectstatic --noinput`
5. Restart server: `sudo systemctl restart gunicorn`

## Performance Optimization

1. **Enable Caching** (add to settings.py):
   ```python
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
       }
   }
   ```

2. **Database Optimization:**
   - Consider upgrading to PostgreSQL for better performance
   - Add database indexes for frequently queried fields

3. **Static Files:**
   - Use CDN for static files (CloudFlare, AWS CloudFront)
   - Enable compression (already configured with WhiteNoise)

## Troubleshooting

### 500 Internal Server Error
- Check logs: `tail -f logs/django.log`
- Verify `DEBUG = False` and error pages are configured
- Check database connection
- Verify static files are collected

### Static Files Not Loading
- Run: `python manage.py collectstatic --noinput`
- Check `STATIC_ROOT` path
- Verify WhiteNoise middleware is enabled

### Database Errors
- Check database file permissions
- Verify database file exists
- Check disk space

### Email Not Sending
- Verify email credentials in `.env`
- Check email provider settings
- Test with console backend first

## Support

For issues or questions, check:
- Django Documentation: https://docs.djangoproject.com/
- Django Deployment Checklist: https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

