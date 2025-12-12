import os
import django

# 1. Setup Django Environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wedding_project.settings")
django.setup()

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


def create_or_update_superuser():
    """
    Creează sau actualizează superuser-ul bazat pe variabilele de mediu.
    """
    USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    EMAIL = os.environ.get("ADMIN_EMAIL", "admin@invapp.ro")
    PASSWORD = os.environ.get("ADMIN_PASSWORD", "AdminPass123!")

    try:
        user, created = User.objects.get_or_create(username=USERNAME)

        # Actualizăm datele indiferent dacă userul e nou sau existent
        user.email = EMAIL
        user.is_staff = True
        user.is_superuser = True
        # Întotdeauna setăm parola pentru a fi siguri că e cea din Environment
        user.set_password(PASSWORD)
        user.save()

        if created:
            print(f"✅ Created new superuser: {USERNAME}")
        else:
            print(f"🔄 Updated existing superuser: {USERNAME}")

        print(f"🔐 Password set/updated for {USERNAME}")
        print(f"ℹ️  Admin Login Details -> Username: '{USERNAME}' | Email: '{EMAIL}'")
        print("   (Notă: În /admin se folosește Username, în aplicație se folosește Email)")

    except Exception as e:
        print(f"❌ Error creating/updating superuser: {e}")


def setup_social_apps():
    """
    Configurează automat aplicațiile Google și Facebook.
    """
    # ... (restul funcției rămâne la fel, nu trebuie modificată) ...
    # Copiază doar partea de mai sus, dar pentru siguranță îți dau tot fișierul mai jos
    domain_name = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "invapp.onrender.com")
    site, created = Site.objects.get_or_create(id=1, defaults={'domain': domain_name, 'name': 'InvApp'})

    if not created and site.domain != domain_name:
        site.domain = domain_name
        site.name = "InvApp"
        site.save()
        print(f"Updated Site domain to: {domain_name}")

    # Configurare Google
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    google_secret = os.environ.get("GOOGLE_SECRET")

    if google_client_id and google_secret:
        app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={'name': 'Google', 'client_id': google_client_id, 'secret': google_secret}
        )
        if not created:
            app.client_id = google_client_id
            app.secret = google_secret
            app.save()
        app.sites.add(site)

    # Configurare Facebook
    fb_client_id = os.environ.get("FACEBOOK_CLIENT_ID")
    fb_secret = os.environ.get("FACEBOOK_SECRET")

    if fb_client_id and fb_secret:
        app, created = SocialApp.objects.get_or_create(
            provider='facebook',
            defaults={'name': 'Facebook', 'client_id': fb_client_id, 'secret': fb_secret}
        )
        if not created:
            app.client_id = fb_client_id
            app.secret = fb_secret
            app.save()
        app.sites.add(site)


if __name__ == "__main__":
    print("--- Starting Project Auto-Setup ---")
    create_or_update_superuser()  # Changed function call
    setup_social_apps()
    print("--- Setup Complete ---")