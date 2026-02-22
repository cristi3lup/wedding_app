from django.contrib import sitemaps
from django.urls import reverse

class StaticViewSitemap(sitemaps.Sitemap):
    priority = 0.5
    changefreq = 'daily'
    # This enables the i18n features in the sitemap
    i18n = True

    def items(self):
        # List of named URLs you want to include in the sitemap
        return [
            'invapp:landing_page',
            'invapp:faq',
            'invapp:upgrade_plan',
            'invapp:terms_and_conditions',
            'invapp:privacy_policy',
        ]

    def location(self, item):
        return reverse(item)
