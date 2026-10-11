"""Employee Leave Management (ELM) -- a Fusion ERP module.

An independent Django app: it owns its own
tables, its own migrations and its own
contract, and reaches other modules only
through their ``contracts.py``.

    domain/    pure Python -- no Django, DRF or Celery
    models/    its own tables; people are plain user_id integers
    selectors/ every read; ownership filtering lives here
    services/  every write; raises domain errors, never DRF ones
    api/       thin: serializers, views, urls
    contracts.py  the ONLY thing other modules may import
"""
