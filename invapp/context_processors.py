from .models import UserProfile

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