import os
import django
import sys

# 1. Inițializare Mediu Django
# Adaugă directorul curent la path pentru a găsi 'wedding_project'
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wedding_project.settings")
django.setup()

from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from allauth.socialaccount.models import SocialApp


def update_site_domain():
    """
    Configurează Site-ul cu ID=1.
    Critic pentru Allauth și link-urile din email-uri.
    """
    print("\n🌐 1. Configuring DOMAIN (Site ID=1)...")

    # Detectăm mediul
    if os.environ.get('RENDER'):
        # Suntem în producție pe Render
        domain = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'invapp-romania.ro')
        name = "InvApp Romania"
        print(f"   -> Production Mode detected. Domain: {domain}")
    else:
        # Suntem local
        # Facebook are nevoie strict de 'localhost', nu '127.0.0.1'
        domain = 'localhost:8000'
        name = "InvApp Local"
        print(f"   -> Local Development Mode. Domain: {domain}")

    # Update sau Create
    # Folosim update_or_create pentru a forța suprascrierea dacă domeniul s-a schimbat
    site, created = Site.objects.update_or_create(
        id=1,
        defaults={
            'domain': domain,
            'name': name
        }
    )
    print(f"   ✅ Site configuration saved: {site.domain} (ID: {site.id})")
    return site


def setup_social_providers(site):
    """
    Configurează Google și Facebook folosind variabilele din .env
    """
    print("\n🔑 2. Configuring SOCIAL APPS (Google/Facebook)...")

    providers = [
        {
            'provider': 'google',
            'name': 'Google',
            'client_id': os.environ.get('GOOGLE_CLIENT_ID'),
            'secret': os.environ.get('GOOGLE_SECRET')
        },
        {
            'provider': 'facebook',
            'name': 'Facebook',
            'client_id': os.environ.get('FACEBOOK_CLIENT_ID'),
            'secret': os.environ.get('FACEBOOK_SECRET')
        }
    ]

    for p in providers:
        if not p['client_id'] or not p['secret']:
            print(f"   ⚠️  Skipping {p['name']}: Missing Client ID or Secret in .env")
            continue

        # Update sau Create SocialApp
        app, created = SocialApp.objects.update_or_create(
            provider=p['provider'],
            defaults={
                'name': p['name'],
                'client_id': p['client_id'],
                'secret': p['secret'],
            }
        )

        # IMPORTANT: Leagă aplicația de Site-ul curent
        app.sites.add(site)

        status = "Created" if created else "Updated"
        print(f"   ✅ {p['name']}: {status} successfully.")


def create_superuser():
    """
    Asigură existența unui cont de admin.
    """
    print("\n👤 3. Checking SUPERUSER...")

    username = os.environ.get("ADMIN_USERNAME", "admin")
    email = os.environ.get("ADMIN_EMAIL", "admin@invapp.ro")
    password = os.environ.get("ADMIN_PASSWORD", "AdminPass123!")

    try:
        user, created = User.objects.get_or_create(username=username, email=email)
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()

        if created:
            print(f"   ✅ Superuser '{username}' created.")
        else:
            print(f"   🔄 Superuser '{username}' updated (Password reset).")

    except Exception as e:
        print(f"   ❌ Error configuring superuser: {e}")


if __name__ == "__main__":
    print("==========================================")
    print("   INVAPP AUTO-SETUP SCRIPT")
    print("==========================================")

    try:
        current_site = update_site_domain()
        setup_social_providers(current_site)
        create_superuser()
        print("\n==========================================")
        print("✅ SETUP COMPLETE! You can now run the server.")
        print("==========================================")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")