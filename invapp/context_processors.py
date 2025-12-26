from .models import UserProfile, SiteImage


def add_active_plan_to_context(request):
    """
    A context processor to add the user's active plan to every page context.
    """
    if request.user.is_authenticated:
        try:
            # We use select_related('plan') for efficiency. This fetches
            # the UserProfile and its related Plan in a single database query.
            user_profile = UserProfile.objects.select_related('plan').get(user=request.user)
            return {'active_plan': user_profile.plan}
        except UserProfile.DoesNotExist:
            # This handles cases like the superuser, who might not have a profile.
            return {'active_plan': None}

    # If the user is not logged in, there is no plan.
    return {'active_plan': None}


def site_assets(request):
    """
    Face imaginile din SiteImage disponibile în toate template-urile
    sub variabila {{ site_images.cheie }}.
    Exemplu utilizare: {{ site_images.hero_bg.url }}
    """
    try:
        # Încercăm să preluăm imaginile doar dacă tabelul există
        images = SiteImage.objects.all()
        images_dict = {}

        for img in images:
            if img.image:
                images_dict[img.key] = img.image

        return {'site_images': images_dict}
    except Exception:
        # Dacă apare o eroare (ex: încă nu s-a făcut migrarea), returnăm un dict gol
        # pentru a nu bloca tot site-ul.
        return {'site_images': {}}