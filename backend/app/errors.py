"""Domain exceptions. Services raise these; one handler in main.py maps them to HTTP."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Unauthorized(DomainError):
    status_code = 401


class Forbidden(DomainError):
    status_code = 403


class Invalid(DomainError):
    status_code = 422


class TooLarge(DomainError):
    status_code = 413
