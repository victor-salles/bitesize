from django.apps import AppConfig


class EditionsConfig(AppConfig):
    name = "editions"

    def ready(self):
        from . import delivery
        from .signals import edition_built

        edition_built.connect(delivery.queue_delivery_on_build, dispatch_uid="editions.delivery")
