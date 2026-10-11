"""ELM services -- every write goes through here.

Services raise domain errors (``ConflictError``,
``NotFoundError``, ``PermissionDeniedError``), never DRF
exceptions, so they stay callable from a Celery task
or a management command.
"""
