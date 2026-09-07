"""Shared, real, dedicated exception for every real workflow block's
own validation/execution error (Parties 5.4.3-5.4.11) -- one shared
type, not nine separate, identical `ValueError` subclasses."""


class WorkflowBlockError(ValueError):
    """Real, dedicated exception."""
