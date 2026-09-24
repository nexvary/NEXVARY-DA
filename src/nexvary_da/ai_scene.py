from __future__ import annotations

import copy
import json
import mimetypes
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import parse as urlparse
from urllib import request as urlrequest

from .ai_video import scene_to_prompt
from .instruction_image import InstructionScene
from .permissions import Permission, WorkspaceGuard
from .state import ProjectState


@dataclass(frozen=True, slots=True)
class GeneratedSceneAsset:
    scene_kind: str
    prompt: str
    engine: str
    output: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def patch_comfy_workflow(
    workflow: dict[str, Any],
    *,
    prompt: str,
    negative_prompt: str = "",
    input_image: str = "",
    output_prefix: str = "nexvary-scene",
) -> dict[str, Any]:
    """Patch an exported ComfyUI API workflow without depending on model-specific node ids."""
    result = copy.deepcopy(workflow)

    def replace_tokens(value: Any) -> Any:
        if isinstance(value, str):
            return (
                value.replace("${PROMPT}", prompt)
                .replace("${NEGATIVE_PROMPT}", negative_prompt)
                .replace("${INPUT_IMAGE}", input_image)
                .replace("${OUTPUT_PREFIX}", output_prefix)
            )
        if isinstance(value, list):
            return [replace_tokens(item) for item in value]
        if isinstance(value, dict):
            return {key: replace_tokens(item) for key, item in value.items()}
        return value

    result = replace_tokens(result)
    positive_set = False
    load_image_set = False

    for node in result.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        title = str((node.get("_meta") or {}).get("title") or "").casefold()

        if class_type == "CLIPTextEncode" and "text" in inputs:
            if "negative" in title:
                inputs["text"] = negative_prompt
            elif not positive_set:
                inputs["text"] = prompt
                positive_set = True

        if class_type == "LoadImage" and input_image and "image" in inputs and not load_image_set:
            inputs["image"] = input_image
            load_image_set = True

        if class_type in {"SaveImage", "PreviewImage"} and "filename_prefix" in inputs:
            inputs["filename_prefix"] = output_prefix

        if "filename_prefix" in inputs and class_type not in {"LoadImage"}:
            current = inputs.get("filename_prefix")
            if isinstance(current, str):
                inputs["filename_prefix"] = output_prefix

    return result


def collect_comfy_output_records(history_entry: dict[str, Any]) -> list[dict[str, str]]:
    outputs = history_entry.get("outputs")
    if not isinstance(outputs, dict):
        return []
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for value in node_output.values():
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    continue
                filename = str(item.get("filename") or "").strip()
                if not filename:
                    continue
                record = {
                    "filename": filename,
                    "subfolder": str(item.get("subfolder") or ""),
                    "type": str(item.get("type") or "output"),
                }
                key = (record["filename"], record["subfolder"], record["type"])
                if key not in seen:
                    seen.add(key)
                    found.append(record)
    return found


class ComfyUISceneGenerator:
    """Turn semantic Product Ad scenes into local AI assets through a ComfyUI API workflow."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        state: ProjectState,
        root: str | os.PathLike[str],
        settings: Any,
    ):
        self.guard = guard
        self.state = state
        self.root = Path(root).resolve(strict=True)
        self.settings = settings

    def _base_url(self) -> str:
        return self.settings.get("comfyui_url", default="http://127.0.0.1:8188").rstrip("/")

    def _workflow_path(self) -> Path | None:
        raw = self.settings.get("comfyui_workflow_path", default="").strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = self.root / path
        return path if path.is_file() else None

    def _json_get(self, path: str, *, timeout: float = 5.0) -> dict[str, Any]:
        with urlrequest.urlopen(self._base_url() + path, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        return payload if isinstance(payload, dict) else {}

    def _discover_checkpoint(self) -> str:
        try:
            payload = self._json_get("/object_info/CheckpointLoaderSimple")
            node = payload.get("CheckpointLoaderSimple")
            required = ((node or {}).get("input") or {}).get("required") or {}
            spec = required.get("ckpt_name")
            choices = spec[0] if isinstance(spec, list) and spec else []
            if isinstance(choices, list):
                names = [str(item) for item in choices if str(item).strip()]
                preferred = [name for name in names if name.lower().endswith((".safetensors", ".ckpt"))]
                if preferred:
                    return preferred[0]
                if names:
                    return names[0]
        except Exception:
            pass
        return ""

    @staticmethod
    def _default_image_workflow(checkpoint: str) -> dict[str, Any]:
        return {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": checkpoint},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "${PROMPT}", "clip": ["1", 1]},
                "_meta": {"title": "Positive Prompt"},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "${NEGATIVE_PROMPT}", "clip": ["1", 1]},
                "_meta": {"title": "Negative Prompt"},
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 720, "height": 1280, "batch_size": 1},
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 771245991,
                    "steps": 22,
                    "cfg": 6.5,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                },
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "${OUTPUT_PREFIX}", "images": ["6", 0]},
            },
        }

    def ready(self) -> dict[str, Any]:
        workflow = self._workflow_path()
        try:
            self._json_get("/system_stats", timeout=2.5)
            if workflow is not None:
                return {"ready": True, "workflow": str(workflow), "url": self._base_url(), "mode": "custom"}
            checkpoint = self._discover_checkpoint()
            if checkpoint:
                return {
                    "ready": True,
                    "workflow": "auto-basic-image",
                    "checkpoint": checkpoint,
                    "url": self._base_url(),
                    "mode": "auto",
                }
            return {
                "ready": False,
                "reason": "ComfyUI is running but no API workflow or checkpoint was detected.",
            }
        except Exception as exc:
            return {"ready": False, "reason": f"{type(exc).__name__}: {exc}"}

    @staticmethod
    def _multipart_file(field_name: str, path: Path) -> tuple[bytes, str]:
        boundary = "----NEXVARY" + uuid.uuid4().hex
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        body = bytearray()
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{path.name}"\r\n'
            ).encode("utf-8")
        )
        body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
        body.extend(data)
        body.extend(f"\r\n--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n')
        body.extend(f"--{boundary}--\r\n".encode())
        return bytes(body), boundary

    def upload_reference_image(self, image: Path) -> str:
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        image = Path(image).resolve(strict=True)
        body, boundary = self._multipart_file("image", image)
        request = urlrequest.Request(
            self._base_url() + "/upload/image",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urlrequest.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        name = str(payload.get("name") or image.name)
        subfolder = str(payload.get("subfolder") or "")
        return f"{subfolder}/{name}".strip("/")

    def _queue(self, workflow: dict[str, Any]) -> str:
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        payload = json.dumps({"prompt": workflow}).encode("utf-8")
        request = urlrequest.Request(
            self._base_url() + "/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8", errors="replace"))
        prompt_id = str(result.get("prompt_id") or "")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return a prompt id: {result}")
        return prompt_id

    def _wait_outputs(self, prompt_id: str, *, timeout: float = 900.0) -> list[dict[str, str]]:
        deadline = time.monotonic() + max(10.0, float(timeout))
        history_url = self._base_url() + "/history/" + urlparse.quote(prompt_id, safe="")
        while time.monotonic() < deadline:
            with urlrequest.urlopen(history_url, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            entry = payload.get(prompt_id)
            if isinstance(entry, dict):
                records = collect_comfy_output_records(entry)
                if records:
                    return records
                status = entry.get("status")
                if isinstance(status, dict) and status.get("completed") is True:
                    messages = status.get("messages") or []
                    raise RuntimeError(f"ComfyUI completed without a downloadable output: {messages}")
            time.sleep(1.0)
        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

    def _download(self, record: dict[str, str], destination: Path) -> Path:
        query = urlparse.urlencode(record)
        url = self._base_url() + "/view?" + query
        suffix = Path(record["filename"]).suffix.lower() or ".bin"
        target = destination / f"{uuid.uuid4().hex}{suffix}"
        with urlrequest.urlopen(url, timeout=120) as response:
            target.write_bytes(response.read())
        if not target.is_file() or target.stat().st_size <= 0:
            raise RuntimeError("ComfyUI returned an empty asset")
        return target

    def generate(
        self,
        scenes: list[InstructionScene] | tuple[InstructionScene, ...],
        *,
        product_name: str = "",
        model: str = "",
        reference_image: Path | None = None,
        max_scenes: int = 4,
        timeout_per_scene: float = 900.0,
    ) -> tuple[GeneratedSceneAsset, ...]:
        status = self.ready()
        if status.get("ready") is not True:
            return ()

        workflow_path = self._workflow_path()
        workflow_label = "auto-basic-image"
        if workflow_path is not None:
            try:
                raw_workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid ComfyUI API workflow: {workflow_path}") from exc
            workflow_label = str(workflow_path)
        else:
            checkpoint = str(status.get("checkpoint") or self._discover_checkpoint())
            if not checkpoint:
                return ()
            raw_workflow = self._default_image_workflow(checkpoint)
        if not isinstance(raw_workflow, dict) or not raw_workflow:
            raise ValueError("ComfyUI API workflow must be a non-empty JSON object")

        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        destination = self.root / ".nexvary-da" / "product-ads" / "ai-scenes" / uuid.uuid4().hex
        destination = self.guard.require(destination, Permission.WRITE, must_exist=False)
        destination.mkdir(parents=True, exist_ok=True)

        uploaded_image = ""
        if reference_image is not None and Path(reference_image).is_file():
            uploaded_image = self.upload_reference_image(Path(reference_image))

        negative = (
            "deformed hands, extra fingers, duplicate people, distorted product, "
            "illegible text, watermark, logo, low quality, blurry"
        )
        assets: list[GeneratedSceneAsset] = []
        for index, scene in enumerate(tuple(scenes)[: max(0, int(max_scenes))], 1):
            prompt = scene_to_prompt(scene, product_name=product_name, model=model)
            prefix = f"nexvary-{scene.kind}-{index:02d}-{uuid.uuid4().hex[:8]}"
            workflow = patch_comfy_workflow(
                raw_workflow,
                prompt=prompt,
                negative_prompt=negative,
                input_image=uploaded_image,
                output_prefix=prefix,
            )
            prompt_id = self._queue(workflow)
            outputs = self._wait_outputs(prompt_id, timeout=timeout_per_scene)
            if not outputs:
                continue
            output = self._download(outputs[0], destination)
            assets.append(
                GeneratedSceneAsset(
                    scene_kind=scene.kind,
                    prompt=prompt,
                    engine="comfyui",
                    output=str(output),
                )
            )

        self.state.record_event(
            "product_ad.ai_scenes.generated",
            {
                "scene_count": len(assets),
                "workflow": workflow_label,
                "reference_image": bool(uploaded_image),
                "outputs": [item.to_dict() for item in assets],
            },
            agent="AI Video Router",
        )
        return tuple(assets)
