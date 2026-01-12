"""Exception types for the python-swidget library."""


class SwidgetException(Exception):
    """Base exception for Swidget-related errors."""


class SwidgetAuthenticationException(SwidgetException):
    """Raised when device authentication fails (HTTP 403)."""


class SwidgetConnectionException(SwidgetException):
    """Raised when a connection to the device cannot be established."""
