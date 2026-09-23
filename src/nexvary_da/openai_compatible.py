from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .intelligence import ReasoningRequest, ReasoningResponse
from .provider_config import CloudProviderConfig


class OpenAICompatibleProvider:
    """Small provider adapter for OpenAI-compatible chat-completions endpoints.

    It only transmits fields explicitly present in ReasoningRequest. Project files
    are never discovered or uploaded by this adapter.
    """

    def __init__(
        self,
        config: CloudProviderConfig,
        *,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
    ):
        self.config = config
        self.name = config.name
        self._urlopen = urlopen

    def _payload(self, request: ReasoningRequest) -> dict[str, Any]:
        user_payload = {
            "goal": request.goal,
            "mode": request.mode.value,
            "project_summary": request.project_summary,
            "changed_files": list(request.changed_files),
            "context": request.context,
            "execution_boundary": (
                "Return planning/reasoning only. Local file, shell, Git, build, "
                "test and release actions are executed by NEXVARY-DA."
            ),
        }
        return {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the cloud reasoning component of a hybrid developer agent. "
                        "Do not claim local actions were executed. Return a concise implementation plan."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
        }

    def reason(self, request: ReasoningRequest) -> ReasoningResponse:
        body = json.dumps(self._payload(request), ensure_ascii=False).encode("utf-8")
        http_request = urllib.request.Request(
            self.config.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.resolved_api_key()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "NEXVARY-DA/0.1",
            },
        )
        try:
            response = self._urlopen(http_request, timeout=self.config.timeout_seconds)
            raw = response.read(self.config.max_response_chars + 1)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Cloud provider returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cloud provider request failed: {exc.reason}") from exc

        if len(raw) > self.config.max_response_chars:
            raise RuntimeError("Cloud provider response exceeded configured maximum size")
        try:
            decoded = json.loads(raw.decode("utf-8"))
            content = decoded["choices"][0]["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Cloud provider returned an invalid chat-completions response") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Cloud provider returned an empty reasoning response")
        return ReasoningResponse(
            provider=self.config.name,
            model=self.config.model,
            plan=content.strip(),
        )
