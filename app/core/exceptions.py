"""
Domain exceptions for EasyInventory.

Services and permission helpers raise these. The FastAPI exception
handler in main.py translates them to HTTP responses. This keeps
the service layer free of HTTP concerns and makes it testable
outside of FastAPI (background jobs, CLI commands, etc.).
"""

from __future__ import annotations


class AppError(Exception):
    """Base exception for all domain errors."""

    def __init__(self, detail: str, *, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# ── Auth / Permissions ──


class NotAuthenticated(AppError):
    """Missing or invalid credentials."""

    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(detail, status_code=401)


class InsufficientPermission(AppError):
    """User lacks the required role or permission."""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail, status_code=403)


# ── Resource errors ──


class NotFound(AppError):
    """Requested resource does not exist."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail, status_code=404)


class AlreadyExists(AppError):
    """Attempted to create a resource that already exists."""

    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(detail, status_code=400)


# ── Org-specific ──


class OwnerProtected(InsufficientPermission):
    """Action cannot be performed on the org owner."""

    def __init__(self, action: str = "modify"):
        super().__init__(detail=f"Cannot {action} the organization owner")


class AdminHierarchyViolation(InsufficientPermission):
    """Admin tried to modify another admin (only owner can)."""

    def __init__(self, action: str = "modify"):
        super().__init__(detail=f"Only the owner can {action} an admin")


class InvalidRole(AppError):
    """Role value is not valid for the given context."""

    def __init__(self, detail: str = "Invalid role"):
        super().__init__(detail, status_code=400)
