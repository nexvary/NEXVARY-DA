from __future__ import annotations

import base64
import ctypes
import json
import os
import tempfile
from ctypes import wintypes
from pathlib import Path

from .permissions import Permission, WorkspaceGuard


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob_from_bytes(data: bytes) -> tuple[_DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def _win_crypto():
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is only available on Windows")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return crypt32, kernel32


def _dpapi_protect(data: bytes) -> bytes:
    crypt32, kernel32 = _win_crypto()
    source, _buffer = _blob_from_bytes(data)
    output = _DATA_BLOB()
    flags = 0x01  # CRYPTPROTECT_UI_FORBIDDEN
    ok = crypt32.CryptProtectData(
        ctypes.byref(source),
        "NEXVARY-DA",
        None,
        None,
        None,
        flags,
        ctypes.byref(output),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    crypt32, kernel32 = _win_crypto()
    source, _buffer = _blob_from_bytes(data)
    output = _DATA_BLOB()
    flags = 0x01
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        flags,
        ctypes.byref(output),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)


class SecretStore:
    """Small local secret store.

    On Windows values are encrypted with DPAPI for the current Windows user before
    being written to disk. On other platforms persistence is deliberately disabled;
    callers can still use environment variables for CI and development.
    """

    def __init__(self, guard: WorkspaceGuard, root: str | os.PathLike[str]):
        self.guard = guard
        self.root = Path(root).resolve(strict=True)
        self.path = self.root / ".nexvary-da" / "secrets.json"

    def _read_payload(self) -> dict[str, str]:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def supported(self) -> bool:
        return os.name == "nt"

    def get(self, name: str, *, env_name: str = "") -> str:
        if env_name:
            env = os.environ.get(env_name, "").strip()
            if env:
                return env
        if os.name != "nt":
            return ""
        encoded = self._read_payload().get(name, "")
        if not encoded:
            return ""
        try:
            protected = base64.b64decode(encoded.encode("ascii"), validate=True)
            return _dpapi_unprotect(protected).decode("utf-8")
        except Exception:
            return ""

    def set(self, name: str, value: str) -> None:
        value = value.strip()
        if not value:
            raise ValueError("Secret value cannot be empty")
        if os.name != "nt":
            raise RuntimeError(
                "Persistent secret storage is only enabled on Windows; use an environment variable on this platform."
            )
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        payload = self._read_payload()
        protected = _dpapi_protect(value.encode("utf-8"))
        payload[name] = base64.b64encode(protected).decode("ascii")

        target = self.guard.require(self.path, Permission.WRITE, must_exist=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".secrets.", suffix=".json", dir=target.parent)
        try:
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def delete(self, name: str) -> None:
        if not self.path.is_file():
            return
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        payload = self._read_payload()
        if name not in payload:
            return
        payload.pop(name, None)
        target = self.guard.require(self.path, Permission.WRITE, must_exist=True)
        fd, temp_name = tempfile.mkstemp(prefix=".secrets.", suffix=".json", dir=target.parent)
        try:
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
