from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from .errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class CloudProviderConfig:
    """Non-secret cloud provider configuration.

    API keys are referenced by environment-variable name and are never serialized
    into project state by this class.
    """

    name: str
    endpoint: str
    model: str
    api_key_env: str
    timeout_seconds: float = 60.0
    max_response_chars: int = 120_000

    def __post_init__(self) -> None:
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ConfigurationError("Cloud endpoint must be an absolute HTTPS URL")
        if not self.name.strip():
            raise ConfigurationError("Cloud provider name cannot be empty")
        if not self.model.strip():
            raise ConfigurationError("Cloud model cannot be empty")
        if not self.api_key_env.strip():
            raise ConfigurationError("api_key_env cannot be empty")
        if self.timeout_seconds <= 0:
            raise ConfigurationError("timeout_seconds must be positive")
        if self.max_response_chars < 1_000:
            raise ConfigurationError("max_response_chars is too small")

    def resolved_api_key(self) -> str:
        value = os.environ.get(self.api_key_env, "").strip()
        if not value:
            raise ConfigurationError(
                f"Cloud API credential is not configured in environment variable {self.api_key_env}"
            )
        return value

    def safe_summary(self) -> dict[str, object]:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "model": self.model,
            "api_key_env": self.api_key_env,
            "credential_present": bool(os.environ.get(self.api_key_env, "").strip()),
            "timeout_seconds": self.timeout_seconds,
            "max_response_chars": self.max_response_chars,
        }

    @classmethod
    def from_env(cls, prefix: str = "NEXVARY_DA_CLOUD_") -> "CloudProviderConfig":
        def need(suffix: str) -> str:
            key = prefix + suffix
            value = os.environ.get(key, "").strip()
            if not value:
                raise ConfigurationError(f"Required environment variable is missing: {key}")
            return value

        timeout = os.environ.get(prefix + "TIMEOUT_SECONDS", "60").strip()
        limit = os.environ.get(prefix + "MAX_RESPONSE_CHARS", "120000").strip()
        try:
            timeout_value = float(timeout)
            limit_value = int(limit)
        except ValueError as exc:
            raise ConfigurationError("Cloud timeout/response limit must be numeric") from exc
        return cls(
            name=need("NAME"),
            endpoint=need("ENDPOINT"),
            model=need("MODEL"),
            api_key_env=need("API_KEY_ENV"),
            timeout_seconds=timeout_value,
            max_response_chars=limit_value,
        )
