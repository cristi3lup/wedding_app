# wedding_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

# --- ADD THESE NEW IMPORTS ---
# This is the correct, direct import path for the view you found
from djstripe.views import ProcessWebhookView
from django.views.decorators.csrf import csrf_exempt
import uuid

# URLs that should NOT have a language prefix
urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),

    # --- THE FIX ---
    # We are manually creating the generic webhook URL that the Stripe CLI is looking for.
    # We point it to the ProcessWebhookView (which we know exists).
    # We use 'kwargs' to force-feed it a dummy 'uuid' to fix the TypeError.
    #path('stripe/webhook/', csrf_exempt(ProcessWebhookView.as_view()), kwargs={'uuid': uuid.UUID('00000000-0000-0000-0000-000000000000')}, name='djstripe-webhook-generic'),
    # We ALSO keep the standard include, just in case.
    path('stripe/', include('djstripe.urls', namespace='djstripe')),

]

# URLs that SHOULD have a language prefix
urlpatterns += i18n_patterns(
    path('accounts/', include('allauth.urls')),
    path('', include('invapp.urls')),
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)