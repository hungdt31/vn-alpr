"""Errors raised by services. The API turns them into HTTP responses in one place (api/main.py)."""

from __future__ import annotations


class AppError(Exception):
    """A request refused by a business rule. `message` is shown to the user as is."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    """The request is valid but the current state forbids it (lot full, ticket in use, ...)."""

    status_code = 409


class Invalid(AppError):
    """The input itself is wrong (bad plate format, unknown vehicle type, unreadable image)."""

    status_code = 422


class Forbidden(AppError):
    status_code = 403


class BadImage(AppError):
    status_code = 400
