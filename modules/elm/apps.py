"""Employee Leave Management (ELM) -- Fusion ERP module.

Independent Django app under ``modules/elm``. Owns its own tables,
its own migrations and its own contract. Follows the platform rules:

    domain/    pure Python -- no Django, DRF or Celery
    models/    its own tables; people are plain ``user_id`` integers
    selectors/ every read; ownership filtering lives here
    services/  every write; raises domain errors, never DRF exceptions
    api/       thin: serializers, views, urls
    contracts.py  the ONLY thing other modules may import
"""
from django.apps import AppConfig


class ElmConfig(AppConfig):
    name = "modules.elm"
    label = "elm"
    verbose_name = "Employee Leave Management"
