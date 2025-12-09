import os
import django

# 1. Setup Django Environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wedding_project.settings")
django.setup()

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


def create_superuser():
    """
    Creează automat un superuser dacă nu există deja.
    """
    USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    EMAIL = os.environ.get("ADMIN_EMAIL", "admin@invapp.ro")
    PASSWORD = os.environ.get("ADMIN_PASSWORD", "AdminPass123!")  # Fallback nesigur, setează variabila în Render!

    if not User.objects.filter(username=USERNAME).exists():
        print(f"Creating superuser: {USERNAME}")
        User.objects.create_superuser(USERNAME, EMAIL, PASSWORD)
    else:
        print("Superuser already exists. Skipping.")


def setup_social_apps():
    """
    Configurează automat aplicațiile Google și Facebook în baza de date
    pentru a evita eroarea 'DoesNotExist' la login.
    """
    # Asigură-te că Site-ul corect există (ID=1 este default în settings.py)
    site, created = Site.objects.get_or_create(id=1, defaults={'domain': 'invapp.onrender.com', 'name': 'InvApp'})

    # Configurare Google
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    google_secret = os.environ.get("GOOGLE_SECRET")

    if google_client_id and google_secret:
        app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': google_client_id,
                'secret': google_secret,
            }
        )
        if created:
            print("Creating Google SocialApp config...")
            app.sites.add(site)
        else:
            # Updatează cheile dacă s-au schimbat în Environment
            app.client_id = google_client_id
            app.secret = google_secret
            app.save()
            print("Updated Google SocialApp config.")

    # Configurare Facebook
    fb_client_id = os.environ.get("FACEBOOK_CLIENT_ID")
    fb_secret = os.environ.get("FACEBOOK_SECRET")

    if fb_client_id and fb_secret:
        app, created = SocialApp.objects.get_or_create(
            provider='facebook',
            defaults={
                'name': 'Facebook',
                'client_id': fb_client_id,
                'secret': fb_secret,
            }
        )
        if created:
            print("Creating Facebook SocialApp config...")
            app.sites.add(site)
        else:
            app.client_id = fb_client_id
            app.secret = fb_secret
            app.save()
            print("Updated Facebook SocialApp config.")


if __name__ == "__main__":
    print("--- Starting Project Auto-Setup ---")
    create_superuser()
    setup_social_apps()
    print("--- Setup Complete ---")
