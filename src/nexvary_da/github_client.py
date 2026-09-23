from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .errors import ConfigurationError
from .permissions import Permission, WorkspaceGuard


_REPO = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


class GitHubRESTClient:
    """Minimal local GitHub REST client with explicit network/release gates."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        project_root: str,
        repository_url: str,
        *,
        token_env: str = "GITHUB_TOKEN",
        api_base: str = "https://api.github.com",
        urlopen: Callable[..., Any] = urllib.request.urlopen,
    ):
        match = _REPO.fullmatch(repository_url.strip())
        if not match:
            raise ConfigurationError("repository_url must be a canonical https://github.com/owner/repo URL")
        self.guard = guard
        self.project_root = project_root
        self.owner, self.repo = match.group(1), match.group(2)
        self.token_env = token_env
        self.api_base = api_base.rstrip("/")
        self._urlopen = urlopen

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "NEXVARY-DA/0.1",
        }
        token = os.environ.get(self.token_env, "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(self, path: str, *, method: str = "GET", body: dict[str, Any] | None = None, release: bool = False) -> Any:
        self.guard.require(self.project_root, Permission.NETWORK, must_exist=True)
        if release:
            self.guard.require(self.project_root, Permission.RELEASE, must_exist=True)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.api_base + path,
            data=data,
            method=method,
            headers=self._headers() | ({"Content-Type": "application/json"} if data else {}),
        )
        try:
            response = self._urlopen(request, timeout=60)
            raw = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GitHub API returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("GitHub API returned invalid JSON") from exc

    def repository(self) -> dict[str, Any]:
        return self._request(f"/repos/{self.owner}/{self.repo}")

    def pull_requests(self, *, state: str = "open", per_page: int = 20) -> list[dict[str, Any]]:
        if state not in {"open", "closed", "all"}:
            raise ValueError("state must be open, closed, or all")
        value = self._request(f"/repos/{self.owner}/{self.repo}/pulls?state={state}&per_page={max(1, min(per_page, 100))}")
        return value if isinstance(value, list) else []

    def workflow_runs(self, *, branch: str = "", per_page: int = 20) -> list[dict[str, Any]]:
        query = f"?per_page={max(1, min(per_page, 100))}"
        if branch:
            from urllib.parse import quote
            query += "&branch=" + quote(branch, safe="")
        value = self._request(f"/repos/{self.owner}/{self.repo}/actions/runs{query}")
        return value.get("workflow_runs", []) if isinstance(value, dict) else []

    def run_artifacts(self, run_id: int) -> list[dict[str, Any]]:
        value = self._request(f"/repos/{self.owner}/{self.repo}/actions/runs/{int(run_id)}/artifacts")
        return value.get("artifacts", []) if isinstance(value, dict) else []

    def releases(self, *, per_page: int = 20) -> list[dict[str, Any]]:
        value = self._request(f"/repos/{self.owner}/{self.repo}/releases?per_page={max(1, min(per_page, 100))}")
        return value if isinstance(value, list) else []

    def create_draft_release(self, tag_name: str, name: str, body: str = "", *, target: str = "") -> dict[str, Any]:
        if not tag_name.strip() or not name.strip():
            raise ValueError("tag_name and name are required")
        payload: dict[str, Any] = {
            "tag_name": tag_name,
            "name": name,
            "body": body,
            "draft": True,
            "prerelease": False,
        }
        if target:
            payload["target_commitish"] = target
        value = self._request(
            f"/repos/{self.owner}/{self.repo}/releases",
            method="POST",
            body=payload,
            release=True,
        )
        if not isinstance(value, dict):
            raise RuntimeError("GitHub did not return a release object")
        return value
