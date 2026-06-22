from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

T = TypeVar("T")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Entity:
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()


@dataclass(frozen=True)
class ValueObject:
    pass


@dataclass(frozen=True)
class Email(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if "@" not in normalized or len(normalized) < 5:
            raise ValueError("Invalid email address")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class TenantSlug(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not normalized or len(normalized) > 63:
            raise ValueError("Invalid tenant slug")
        object.__setattr__(self, "value", normalized)


class DomainException(Exception):
    def __init__(self, message: str, code: str = "domain_error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainException):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, code="not_found")


class ConflictError(DomainException):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message, code="conflict")


class UnauthorizedError(DomainException):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, code="unauthorized")


class ForbiddenError(DomainException):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, code="forbidden")


class ValidationError(DomainException):
    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message, code="validation_error")


@dataclass(frozen=True)
class Result(Generic[T]):
    value: T | None = None
    error: str | None = None
    error_code: str | None = None

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def is_failure(self) -> bool:
        return self.error is not None

    @classmethod
    def ok(cls, value: T) -> "Result[T]":
        return cls(value=value)

    @classmethod
    def fail(cls, error: str, error_code: str = "error") -> "Result[T]":
        return cls(error=error, error_code=error_code)


AuditMetadata = dict[str, Any]
