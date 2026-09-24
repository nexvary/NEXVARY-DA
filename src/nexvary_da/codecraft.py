from __future__ import annotations

import base64
import io
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from PIL import Image, ImageOps

from .instruction_image import InstructionScene, InstructionSceneKind
from .permissions import Permission, WorkspaceGuard
from .secret_store import SecretStore
from .state import ProjectState

DEFAULT_BASE_URL = "https://www.codecraftapi.com/v1"
_SECRET_NAME = "codecraft_api_key"
_ENV_NAME = "CODECRAFT_API_KEY"


@dataclass(frozen=True, slots=True)
class CodeCraftModel:
    model_id: str
    name: str
    capabilities: tuple[str, ...]
    context_window: int
    input_per_1k: float | None
    output_per_1k: float | None

    def supports(self, capability: str) -> bool:
        wanted = capability.casefold()
        return wanted in {item.casefold() for item in self.capabilities}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CodeCraftProductPlan:
    model_id: str
    summary: str
    hook_ar: str
    scenes: tuple[InstructionScene, ...]
    usage: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "summary": self.summary,
            "hook_ar": self.hook_ar,
            "scenes": [asdict(scene) for scene in self.scenes],
            "usage": dict(self.usage),
        }


def _json_from_text(text: str) -> dict[str, Any]:
    raw = text.strip()
    fence = chr(96) * 3
    if raw.startswith(fence) and raw.endswith(fence):
        raw = re.sub(r"^" + re.escape(fence) + r"(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*" + re.escape(fence) + r"$", "", raw)
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(raw[start : end + 1])
                return value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _scene_kind(value: str) -> InstructionSceneKind:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "cod": InstructionSceneKind.CASH_ON_DELIVERY,
        "cash": InstructionSceneKind.CASH_ON_DELIVERY,
        "cash_on_delivery": InstructionSceneKind.CASH_ON_DELIVERY,
        "delivery": InstructionSceneKind.SHIPPING,
        "shipping": InstructionSceneKind.SHIPPING,
        "pickup": InstructionSceneKind.PICKUP,
        "booking": InstructionSceneKind.RESERVATION,
        "reservation": InstructionSceneKind.RESERVATION,
        "guarantee": InstructionSceneKind.WARRANTY,
        "warranty": InstructionSceneKind.WARRANTY,
        "application": InstructionSceneKind.APP,
        "app": InstructionSceneKind.APP,
        "sim": InstructionSceneKind.SIM,
        "memory_card": InstructionSceneKind.SIM,
        "qr": InstructionSceneKind.QR,
        "network": InstructionSceneKind.CONNECTIVITY,
        "connectivity": InstructionSceneKind.CONNECTIVITY,
        "installation": InstructionSceneKind.SETUP,
        "setup": InstructionSceneKind.SETUP,
        "feature": InstructionSceneKind.FEATURE,
    }
    return aliases.get(normalized, InstructionSceneKind.OTHER)


def _prepared_image_data_uri(path: Path, *, max_side: int = 1280, max_bytes: int = 1_250_000) -> str:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    quality = 86
    while True:
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= max_bytes or quality <= 54:
            break
        quality -= 8
    if len(data) > max_bytes:
        ratio = (max_bytes / max(len(data), 1)) ** 0.5
        image = image.resize(
            (max(320, int(image.width * ratio)), max(320, int(image.height * ratio))),
            Image.Resampling.LANCZOS,
        )
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=66, optimize=True)
        data = buffer.getvalue()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


class CodeCraftProvider:
    def __init__(
        self,
        guard: WorkspaceGuard,
        state: ProjectState,
        root: str | os.PathLike[str],
        settings: Any,
        secrets: SecretStore,
    ):
        self.guard = guard
        self.state = state
        self.root = Path(root).resolve(strict=True)
        self.settings = settings
        self.secrets = secrets

    def base_url(self) -> str:
        raw = self.settings.get("codecraft_base_url", default=DEFAULT_BASE_URL).strip()
        return (raw or DEFAULT_BASE_URL).rstrip("/")

    def api_key(self) -> str:
        return self.secrets.get(_SECRET_NAME, env_name=_ENV_NAME)

    def has_api_key(self) -> bool:
        return bool(self.api_key())

    def save_api_key(self, value: str) -> None:
        value = value.strip()
        if not value.startswith("cc_"):
            raise ValueError("CodeCraft API key must start with cc_")
        self.secrets.set(_SECRET_NAME, value)

    def delete_api_key(self) -> None:
        self.secrets.delete(_SECRET_NAME)

    def _request_json(
        self,
        method: str,
        endpoint: str,
        *,
        body: dict[str, Any] | None = None,
        timeout: float = 45.0,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        key = self.api_key()
        if not key:
            raise RuntimeError("CodeCraft API key is not configured")
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + key,
            "Accept": "application/json",
            "User-Agent": "NEXVARY-DA/0.1",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urlrequest.Request(
            self.base_url() + "/" + endpoint.lstrip("/"),
            data=data,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urlrequest.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                payload = json.loads(raw) if raw else {}
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        except urlerror.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                envelope = json.loads(raw)
            except json.JSONDecodeError:
                envelope = {}
            detail = ""
            if isinstance(envelope, dict) and isinstance(envelope.get("error"), dict):
                detail = str(envelope["error"].get("message") or "")
            raise RuntimeError("CodeCraft HTTP " + str(exc.code) + ": " + (detail or raw)[:500]) from exc
        except urlerror.URLError as exc:
            raise RuntimeError("CodeCraft connection failed: " + str(exc.reason)) from exc
        if not isinstance(payload, dict):
            raise RuntimeError("CodeCraft returned invalid JSON")
        return payload, response_headers

    def list_models(self) -> tuple[CodeCraftModel, ...]:
        payload, _ = self._request_json("GET", "/models", timeout=20)
        data = payload.get("data")
        if not isinstance(data, list):
            return ()
        models: list[CodeCraftModel] = []
        for item in data:
            if not isinstance(item, dict) or not str(item.get("id") or "").strip():
                continue
            capabilities = item.get("capabilities")
            caps = tuple(str(x) for x in capabilities) if isinstance(capabilities, list) else ()
            pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
            def number(key: str) -> float | None:
                try:
                    value = pricing.get(key)
                    return None if value is None else float(value)
                except (TypeError, ValueError):
                    return None
            try:
                context = int(item.get("context_window") or 0)
            except (TypeError, ValueError):
                context = 0
            models.append(
                CodeCraftModel(
                    model_id=str(item["id"]),
                    name=str(item.get("name") or item["id"]),
                    capabilities=caps,
                    context_window=context,
                    input_per_1k=number("input_per_1k"),
                    output_per_1k=number("output_per_1k"),
                )
            )
        return tuple(models)

    def choose_model(self, *, vision: bool = False, prefer_json: bool = False, preferred: str = "") -> CodeCraftModel:
        models = self.list_models()
        if not models:
            raise RuntimeError("CodeCraft returned no models")
        def acceptable(model: CodeCraftModel, strict_json: bool) -> bool:
            return (not vision or model.supports("vision")) and (not strict_json or model.supports("json_mode"))
        if preferred:
            exact = next((m for m in models if m.model_id == preferred and acceptable(m, prefer_json)), None)
            if exact:
                return exact
        candidates = [m for m in models if acceptable(m, prefer_json)]
        if not candidates and prefer_json:
            candidates = [m for m in models if acceptable(m, False)]
        if not candidates:
            raise RuntimeError("No available CodeCraft model supports the requested input")
        def score(model: CodeCraftModel) -> tuple[int, int, float]:
            useful = sum(model.supports(cap) for cap in ("vision", "json_mode", "reasoning", "tools"))
            price = model.input_per_1k if model.input_per_1k is not None else 999999.0
            return useful, model.context_window, -price
        return sorted(candidates, key=score, reverse=True)[0]

    def status(self) -> dict[str, Any]:
        if not self.has_api_key():
            return {"ready": False, "configured": False, "reason": "API key not configured", "base_url": self.base_url()}
        try:
            models = self.list_models()
            return {
                "ready": True,
                "configured": True,
                "base_url": self.base_url(),
                "models": len(models),
                "vision_models": sum(item.supports("vision") for item in models),
                "model_ids": [item.model_id for item in models],
            }
        except Exception as exc:
            return {
                "ready": False,
                "configured": True,
                "reason": type(exc).__name__ + ": " + str(exc),
                "base_url": self.base_url(),
            }

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "",
        require_vision: bool = False,
        prefer_json: bool = False,
        max_tokens: int = 2500,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        selected = self.choose_model(vision=require_vision, prefer_json=prefer_json, preferred=model)
        body: dict[str, Any] = {
            "model": selected.model_id,
            "messages": messages,
            "stream": False,
            "max_tokens": max(2048, int(max_tokens)),
            "temperature": max(0.0, min(2.0, float(temperature))),
        }
        if prefer_json and selected.supports("json_mode"):
            body["response_format"] = {"type": "json_object"}
        payload, headers = self._request_json("POST", "/chat/completions", body=body, timeout=120)
        content = ""
        choices = payload.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                content = str(message.get("content") or "")
        usage_raw = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        usage = {key: int(usage_raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
        self.state.record_event(
            "codecraft.chat.completed",
            {
                "model": selected.model_id,
                "vision": require_vision,
                "json_mode": bool(body.get("response_format")),
                "usage": usage,
                "rate_limit_remaining": headers.get("x-ratelimit-remaining", ""),
            },
            agent="CodeCraft Provider",
        )
        return {"model": selected.model_id, "content": content, "usage": usage, "capabilities": list(selected.capabilities)}

    def analyze_product_images(
        self,
        image_paths: list[str | os.PathLike[str]] | tuple[str | os.PathLike[str], ...],
        *,
        product_name: str = "",
        model_name: str = "",
        seller_details: str = "",
        preferred_model: str = "",
        max_scenes: int = 6,
    ) -> CodeCraftProductPlan:
        paths = [Path(value).expanduser().resolve(strict=True) for value in image_paths][:4]
        if not paths:
            raise ValueError("At least one product image is required")
        fact_blob = json.dumps(
            {"product_name": product_name.strip(), "model": model_name.strip(), "seller_details": seller_details.strip()},
            ensure_ascii=False,
        )
        system = (
            "You plan visuals for a product advertisement. Never invent specifications, price, warranty, "
            "compatibility, performance claims, or setup steps. Use only seller facts or text/objects clearly "
            "visible in the supplied images. If uncertain, omit it. Return valid JSON only."
        )
        prompt = (
            "Build a semantic ad scene plan from these seller-owned images. Seller facts: " + fact_blob + ". "
            "Return at most " + str(max(1, min(8, int(max_scenes)))) + " scenes using this schema: "
            "{summary: Arabic summary, hook_ar: Arabic hook, scenes: [{kind: one of shipping, cash_on_delivery, "
            "pickup, reservation, warranty, app, sim, qr, connectivity, setup, feature, other; "
            "narration_ar: grounded Arabic narration; visual_cue_en: English direction for an original supporting "
            "scene; evidence: visible text/object or seller fact}]}. Do not include unsupported claims."
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for path in paths:
            content.append({"type": "image_url", "image_url": {"url": _prepared_image_data_uri(path)}})
        response = self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": content}],
            model=preferred_model,
            require_vision=True,
            prefer_json=True,
            max_tokens=3000,
            temperature=0.1,
        )
        parsed = _json_from_text(str(response.get("content") or ""))
        scenes: list[InstructionScene] = []
        raw_scenes = parsed.get("scenes")
        if isinstance(raw_scenes, list):
            for raw in raw_scenes[: max(1, min(8, int(max_scenes)))]:
                if not isinstance(raw, dict):
                    continue
                narration = str(raw.get("narration_ar") or "").strip()
                cue = str(raw.get("visual_cue_en") or "").strip()
                evidence = str(raw.get("evidence") or "").strip()
                if narration and cue and evidence:
                    scenes.append(
                        InstructionScene(
                            kind=_scene_kind(str(raw.get("kind") or "other")),
                            text=evidence,
                            narration=narration,
                            visual_cue=cue,
                        )
                    )
        plan = CodeCraftProductPlan(
            model_id=str(response.get("model") or ""),
            summary=str(parsed.get("summary") or "").strip(),
            hook_ar=str(parsed.get("hook_ar") or "").strip(),
            scenes=tuple(scenes),
            usage=dict(response.get("usage") or {}),
        )
        self.state.record_event(
            "product_ad.codecraft.vision_plan",
            {"model": plan.model_id, "image_count": len(paths), "scene_count": len(plan.scenes), "usage": plan.usage},
            agent="CodeCraft Provider",
        )
        return plan
