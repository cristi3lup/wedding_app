from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns

# URLs that should NOT have a language prefix
urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),

    # REMOVED: path('stripe/', include('djstripe.urls'...))
    # We are now using our own custom webhook in invapp.urls
]

# URLs that SHOULD have a language prefix
urlpatterns += i18n_patterns(
    path('accounts/', include('allauth.urls')),
    path('', include('invapp.urls')),
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)