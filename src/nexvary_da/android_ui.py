from __future__ import annotations

import os
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .state import ProjectState


_BOUNDS = re.compile(r"^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$")
_COMPONENT = re.compile(r"^[A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+$")
_PNG = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True, slots=True)
class AndroidDevice:
    serial: str
    state: str
    details: str


@dataclass(frozen=True, slots=True)
class AndroidNode:
    text: str
    content_desc: str
    resource_id: str
    class_name: str
    clickable: bool
    enabled: bool
    bounds: tuple[int, int, int, int]

    @property
    def center(self) -> tuple[int, int]:
        left, top, right, bottom = self.bounds
        return ((left + right) // 2, (top + bottom) // 2)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"center": list(self.center)}


def parse_adb_devices(output: str) -> tuple[AndroidDevice, ...]:
    devices: list[AndroidDevice] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith("List of devices attached") or line.startswith("* daemon"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        devices.append(
            AndroidDevice(
                serial=parts[0],
                state=parts[1],
                details=" ".join(parts[2:]),
            )
        )
    return tuple(devices)


def parse_uiautomator_xml(text: str) -> tuple[AndroidNode, ...]:
    root = ET.fromstring(text)
    nodes: list[AndroidNode] = []
    for element in root.iter("node"):
        raw_bounds = element.get("bounds") or ""
        match = _BOUNDS.fullmatch(raw_bounds)
        if not match:
            continue
        bounds = tuple(int(match.group(index)) for index in range(1, 5))
        nodes.append(
            AndroidNode(
                text=element.get("text") or "",
                content_desc=element.get("content-desc") or "",
                resource_id=element.get("resource-id") or "",
                class_name=element.get("class") or "",
                clickable=(element.get("clickable") or "").lower() == "true",
                enabled=(element.get("enabled") or "").lower() != "false",
                bounds=bounds,  # type: ignore[arg-type]
            )
        )
    return tuple(nodes)


class AndroidUIHarness:
    """ADB UI automation constrained by NEXVARY's workspace and ADB permission."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        runner: ProcessRunner,
        state: ProjectState,
        root: str | os.PathLike[str],
    ):
        self.guard = guard
        self.runner = runner
        self.state = state
        self.root = Path(root).resolve(strict=True)

    def _require(self) -> None:
        self.guard.require(self.root, Permission.ADB, must_exist=True)

    def devices(self) -> tuple[AndroidDevice, ...]:
        self._require()
        result = self.runner.run(["adb", "devices", "-l"], cwd=self.root, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip() or "adb devices failed")
        return parse_adb_devices(result.stdout)

    def start_component(self, component: str) -> dict[str, Any]:
        self._require()
        if not _COMPONENT.fullmatch(component):
            raise ValueError("Android component must look like package.name/ActivityName")
        result = self.runner.run(
            ["adb", "shell", "am", "start", "-W", "-n", component],
            cwd=self.root,
            timeout=120,
        )
        payload = {
            "returncode": result.returncode,
            "output": result.stdout,
            "component": component,
        }
        self.state.record_event(
            "android.ui.start",
            {"component": component, "returncode": result.returncode},
            agent="UI Inspector",
        )
        return payload

    def hierarchy(self) -> tuple[AndroidNode, ...]:
        self._require()
        remote = "/sdcard/nexvary-da-window.xml"
        dump = self.runner.run(
            ["adb", "shell", "uiautomator", "dump", remote],
            cwd=self.root,
            timeout=90,
        )
        if dump.returncode != 0:
            raise RuntimeError(dump.stdout.strip() or "uiautomator dump failed")
        result = self.runner.run(
            ["adb", "exec-out", "cat", remote],
            cwd=self.root,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip() or "Unable to read UI hierarchy")
        nodes = parse_uiautomator_xml(result.stdout)
        self.state.record_event(
            "android.ui.hierarchy",
            {"node_count": len(nodes)},
            agent="UI Inspector",
        )
        return nodes

    def find(self, label: str) -> tuple[AndroidNode, ...]:
        query = label.strip().casefold()
        if not query:
            raise ValueError("label cannot be empty")
        return tuple(
            node
            for node in self.hierarchy()
            if query in node.text.casefold()
            or query in node.content_desc.casefold()
            or query in node.resource_id.casefold()
        )

    def tap(self, x: int, y: int) -> dict[str, Any]:
        self._require()
        if x < 0 or y < 0:
            raise ValueError("tap coordinates must be non-negative")
        result = self.runner.run(
            ["adb", "shell", "input", "tap", str(int(x)), str(int(y))],
            cwd=self.root,
            timeout=30,
        )
        return {"returncode": result.returncode, "output": result.stdout, "x": int(x), "y": int(y)}

    def tap_label(self, label: str) -> dict[str, Any]:
        matches = self.find(label)
        enabled = [node for node in matches if node.enabled and node.clickable]
        candidates = enabled or [node for node in matches if node.enabled]
        if not candidates:
            raise LookupError(f"No enabled Android UI node matched: {label}")
        node = candidates[0]
        x, y = node.center
        result = self.tap(x, y)
        result["node"] = node.to_dict()
        result["label"] = label
        self.state.record_event(
            "android.ui.tap",
            {"label": label, "x": x, "y": y, "returncode": result["returncode"]},
            agent="UI Inspector",
        )
        return result

    def press_back(self) -> dict[str, Any]:
        self._require()
        result = self.runner.run(
            ["adb", "shell", "input", "keyevent", "KEYCODE_BACK"],
            cwd=self.root,
            timeout=30,
        )
        self.state.record_event(
            "android.ui.back",
            {"returncode": result.returncode},
            agent="UI Inspector",
        )
        return {"returncode": result.returncode, "output": result.stdout}

    def screenshot(self, relative: str = ".nexvary-da/android-ui/screenshot.png") -> dict[str, Any]:
        self._require()
        target = self.guard.require(self.root / relative, Permission.WRITE, must_exist=False)
        result = self.runner.run_bytes(
            ["adb", "exec-out", "screencap", "-p"],
            cwd=self.root,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout.decode("utf-8", errors="replace").strip() or "Android screenshot failed")
        if not result.stdout.startswith(_PNG):
            raise RuntimeError("ADB screencap did not return PNG data")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".android-shot.", suffix=".png", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(result.stdout)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        self.state.record_event(
            "android.ui.screenshot",
            {"path": str(target.relative_to(self.root)), "size_bytes": target.stat().st_size},
            agent="UI Inspector",
        )
        return {
            "path": str(target.relative_to(self.root)),
            "size_bytes": target.stat().st_size,
        }

    def inspect(self) -> dict[str, Any]:
        devices = self.devices()
        active = [device for device in devices if device.state == "device"]
        payload: dict[str, Any] = {
            "devices": [asdict(device) for device in devices],
            "active_device_count": len(active),
            "nodes": [],
        }
        if active:
            payload["nodes"] = [node.to_dict() for node in self.hierarchy()]
        return payload
