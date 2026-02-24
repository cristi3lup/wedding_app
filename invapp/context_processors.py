from django.conf import settings
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
    Makes images from SiteImage available in all templates
    under the {{ site_images.key }} variable.
    Usage Example: {{ site_images.hero_bg.url }}
    """
    try:
        # Try to fetch images only if the table exists
        images = SiteImage.objects.all()
        images_dict = {}

        for img in images:
            if img.image:
                images_dict[img.key] = img.image

        return {'site_images': images_dict}
    except Exception:
        # If an error occurs (e.g., migration not yet applied), return an empty dict
        # to avoid blocking the entire site.
        return {'site_images': {}}


def seo_settings(request):
    """
    Exposes Google SEO and Analytics IDs to all templates.
    """
    return {
        'GOOGLE_SITE_VERIFICATION': getattr(settings, 'GOOGLE_SITE_VERIFICATION', ''),
        'GA_MEASUREMENT_ID': getattr(settings, 'GA_MEASUREMENT_ID', ''),
        'GOOGLE_MAPS_API_KEY': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
    }
