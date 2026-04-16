class AppError(Exception):
    """Base application error."""


class NotFoundError(AppError):
    """Requested entity was not found."""


class ValidationError(AppError):
    """User input or payload validation failed."""


class ExternalServiceError(AppError):
    """An external dependency failed."""


class AuthenticationError(AppError):
    """Authentication or authorization failed."""


class ConflictError(AppError):
    """Operation conflicts with current persisted state."""

