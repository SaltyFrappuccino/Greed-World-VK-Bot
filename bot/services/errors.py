class ServiceError(Exception):
    """Ошибка бизнес-логики с текстом, который можно показать игроку как есть."""


class NotFoundError(ServiceError):
    pass


class ValidationError(ServiceError):
    pass


class PermissionDenied(ServiceError):
    pass


class TransformLimitReached(ServiceError):
    pass


class InsufficientFunds(ServiceError):
    pass
