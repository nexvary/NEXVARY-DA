class NexvaryDAError(Exception):
    """Base error for NEXVARY-DA."""


class PermissionDenied(NexvaryDAError):
    """Raised when a workspace capability is not granted."""


class WorkspaceViolation(NexvaryDAError):
    """Raised when a path escapes every approved workspace root."""


class TerminalError(NexvaryDAError):
    """Raised when a persistent terminal cannot complete an operation."""


class ConfigurationError(NexvaryDAError):
    """Raised when project configuration is invalid."""
