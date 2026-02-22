from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.contrib.auth import views as auth_views
from invapp import views as invapp_views
from django.views.generic.base import RedirectView
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from invapp.sitemaps import StaticViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
}

# URLs that should NOT have a language prefix (Technical endpoints & Social Auth)
urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'invapp/images/favicon.png')),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/'), name='admin_logout'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('webhook/stripe/', invapp_views.stripe_webhook, name='stripe_webhook'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

# URLs that SHOULD have a language prefix (User-facing content)
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # Moved back into localized section
    path('', include('invapp.urls')),
    prefix_default_language=True,  # Critical for SEO: forces /ro/ even for the default language
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)