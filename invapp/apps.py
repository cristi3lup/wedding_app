from django.apps import AppConfig

class InvappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'invapp'

    def ready(self):
        # We have removed the signal import to avoid the djstripe error.
        # import invapp.signals
        pass