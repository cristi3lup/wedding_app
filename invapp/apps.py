from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class InvappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'invapp'
    verbose_name = _('Invitation App')

    # --- ADD THIS FUNCTION ---
    # This imports our new signals.py file when the app starts.
    def ready(self):
        import invapp.signals