from django.conf import settings


class ForceDefaultLanguageMiddleware:
    """
    Middleware to force the default language (LANGUAGE_CODE) for users
    who haven't explicitly set a language preference yet.
    This ignores the browser's 'Accept-Language' header (e.g., phone OS language).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the user already has a language cookie set (meaning they chose a language)
        # or if the session has a language set.
        cookie_name = getattr(settings, 'LANGUAGE_COOKIE_NAME', 'django_language')

        has_cookie = cookie_name in request.COOKIES
        has_session = hasattr(request, 'session') and '_language' in request.session

        # If they are a new visitor (no cookie/session), hide their browser's language preference
        if not has_cookie and not has_session:
            if 'HTTP_ACCEPT_LANGUAGE' in request.META:
                del request.META['HTTP_ACCEPT_LANGUAGE']

        response = self.get_response(request)
        return response