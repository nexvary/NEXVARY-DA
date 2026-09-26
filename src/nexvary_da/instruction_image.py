from __future__ import annotations

import base64
import os
import re
import shutil
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from PIL import Image

from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .state import ProjectState


_ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_MAX_IMAGES = 12
_MAX_BYTES = 40 * 1024 * 1024


class InstructionSceneKind(StrEnum):
    SHIPPING = "shipping"
    CASH_ON_DELIVERY = "cash_on_delivery"
    PICKUP = "pickup"
    RESERVATION = "reservation"
    WARRANTY = "warranty"
    APP = "app"
    SIM = "sim"
    QR = "qr"
    CONNECTIVITY = "connectivity"
    SETUP = "setup"
    FEATURE = "feature"
    OTHER = "other"


_VISUAL_CUES = {
    InstructionSceneKind.SHIPPING: "سيارة بريد أو توصيل تتحرك ومعها طرد المنتج",
    InstructionSceneKind.CASH_ON_DELIVERY: "مندوب بريد يسلم المنتج للعميل والعميل يدفع له نقدًا",
    InstructionSceneKind.PICKUP: "عميل يستلم المنتج من مخزن أو نقطة استلام",
    InstructionSceneKind.RESERVATION: "تقويم وحجز مسبق مع تنبيه إلى توفر الكمية",
    InstructionSceneKind.WARRANTY: "درع ضمان وشارة جودة وفحص المنتج",
    InstructionSceneKind.APP: "هاتف يعرض تطبيق المنتج وخطوات التسجيل أو الإضافة",
    InstructionSceneKind.SIM: "تركيب شريحة اتصال أو بطاقة ذاكرة داخل المنتج",
    InstructionSceneKind.QR: "هاتف يمسح رمز QR الموجود على المنتج أو العبوة",
    InstructionSceneKind.CONNECTIVITY: "المنتج يتصل بالشبكة أو الهاتف وتظهر حالة الاتصال",
    InstructionSceneKind.SETUP: "خطوات تشغيل وتركيب المنتج بصورة مبسطة",
    InstructionSceneKind.FEATURE: "لقطة توضيحية للميزة المذكورة مع إبراز المنتج",
    InstructionSceneKind.OTHER: "مشهد توضيحي أصلي مرتبط مباشرة بالنص المستخرج",
}


@dataclass(frozen=True, slots=True)
class InstructionScene:
    kind: str
    text: str
    narration: str
    visual_cue: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class InstructionImageAnalysis:
    source: str
    imported: str
    engine: str
    text: str
    scenes: tuple[InstructionScene, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "imported": self.imported,
            "engine": self.engine,
            "text": self.text,
            "scenes": [scene.to_dict() for scene in self.scenes],
        }


def _clean_line(value: str) -> str:
    value = re.sub(r"[\t\r]+", " ", str(value))
    value = re.sub(r"\s+", " ", value).strip(" -•|")
    return value.strip()


def _classify(line: str) -> InstructionSceneKind:
    low = line.casefold()
    if any(k in low for k in ("البريد", "مندوب", "شحن", "التوصيل")) and any(
        k in low for k in ("نقد", "فلوس", "الدفع", "تحصيل")
    ):
        return InstructionSceneKind.CASH_ON_DELIVERY
    if any(k in low for k in ("البريد", "شحن", "التوصيل", "الطرد")):
        return InstructionSceneKind.SHIPPING
    if any(k in low for k in ("استلام", "المخزن", "فرعنا", "فروعنا")):
        return InstructionSceneKind.PICKUP
    if any(k in low for k in ("حجز", "الكمية", "متوفر", "التوفر")):
        return InstructionSceneKind.RESERVATION
    if any(k in low for k in ("ضمان", "الجودة", "جودة", "سلامة", "مطابقة")):
        return InstructionSceneKind.WARRANTY
    if any(k in low for k in ("تطبيق", "google play", "app", "حساب", "تسجيل الدخول")):
        return InstructionSceneKind.APP
    if any(k in low for k in ("شريحة", "sim", "كارت الذاكرة", "بطاقة الذاكرة", "microsd")):
        return InstructionSceneKind.SIM
    if "qr" in low or "رمز" in low and "مسح" in low:
        return InstructionSceneKind.QR
    if any(k in low for k in ("wifi", "wi-fi", "4g", "5g", "ربط", "اتصال", "الشبكة")):
        return InstructionSceneKind.CONNECTIVITY
    if any(k in low for k in ("تشغيل", "تركيب", "ثبت", "تثبيت", "اضغط", "اختر", "أضف")):
        return InstructionSceneKind.SETUP
    if any(k in low for k in ("ميزة", "مميزات", "كاميرا", "صوت", "رؤية", "كشف", "طاقة")):
        return InstructionSceneKind.FEATURE
    return InstructionSceneKind.OTHER


def plan_instruction_scenes(text: str, *, max_scenes: int = 12) -> tuple[InstructionScene, ...]:
    raw_lines = re.split(r"[\n]+|(?<=[:؛.!؟])\s+", str(text))
    lines: list[str] = []
    for raw in raw_lines:
        line = _clean_line(raw)
        if len(line) < 4:
            continue
        if line not in lines:
            lines.append(line)

    scenes: list[InstructionScene] = []
    for line in lines[: max(1, int(max_scenes))]:
        kind = _classify(line)
        narration = line if line.endswith((".", "!", "؟", "؛", "،")) else line + "."
        scenes.append(
            InstructionScene(
                kind=kind.value,
                text=line,
                narration=narration,
                visual_cue=_VISUAL_CUES[kind],
            )
        )
    return tuple(scenes)


class InstructionImageInterpreter:
    """Local OCR + deterministic scene planning for seller-supplied instruction images."""

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

    def _import_images(self, selected: list[str] | tuple[str, ...]) -> list[tuple[Path, Path]]:
        if not selected:
            return []
        if len(selected) > _MAX_IMAGES:
            raise ValueError(f"Choose no more than {_MAX_IMAGES} instruction images")
        self.guard.require(self.root, Permission.WRITE, must_exist=True)

        batch = self.root / ".nexvary-da" / "product-ads" / "instruction-images" / uuid.uuid4().hex
        batch = self.guard.require(batch, Permission.WRITE, must_exist=False)
        batch.mkdir(parents=True, exist_ok=True)

        imported: list[tuple[Path, Path]] = []
        for index, raw in enumerate(selected, 1):
            source = Path(raw).expanduser().resolve(strict=True)
            if source.suffix.lower() not in _ALLOWED:
                raise ValueError(f"Unsupported instruction image type: {source.suffix}")
            if source.stat().st_size > _MAX_BYTES:
                raise ValueError(f"Instruction image is too large: {source.name}")
            try:
                with Image.open(source) as probe:
                    probe.verify()
            except Exception as exc:
                raise ValueError(f"Invalid instruction image: {source.name}") from exc
            target = batch / f"{index:02d}{source.suffix.lower()}"
            shutil.copy2(source, target)
            imported.append((source, target))
        return imported

    def _windows_ocr(self, image: Path) -> str:
        # Windows.Media.Ocr is local and uses OCR languages installed with Windows.
        script = r'''
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime]

function Await($op, [Type]$type) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq "AsTask" -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait()
    return $task.Result
}

$path = $env:NEXVARY_OCR_IMAGE
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { throw "Windows OCR language is not available." }
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$result.Text
'''
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        result = self.runner.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            cwd=self.root,
            timeout=120,
            env={"NEXVARY_OCR_IMAGE": str(image)},
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout[-3000:] or "Windows OCR failed")
        return result.stdout.strip()

    def _tesseract_ocr(self, image: Path) -> str:
        exe = shutil.which("tesseract")
        if not exe:
            raise RuntimeError("No local OCR engine is available")
        result = self.runner.run(
            [exe, str(image), "stdout", "-l", "ara+eng", "--psm", "6"],
            cwd=self.root,
            timeout=180,
        )
        if result.returncode != 0:
            # Retry English/default language if Arabic data is not installed.
            result = self.runner.run(
                [exe, str(image), "stdout", "--psm", "6"],
                cwd=self.root,
                timeout=180,
            )
        if result.returncode != 0:
            raise RuntimeError(result.stdout[-3000:] or "Tesseract OCR failed")
        return result.stdout.strip()

    def _extract(self, image: Path) -> tuple[str, str]:
        errors: list[str] = []
        if os.name == "nt":
            try:
                text = self._windows_ocr(image)
                if text.strip():
                    return text, "windows-media-ocr"
            except Exception as exc:
                errors.append(f"Windows OCR: {type(exc).__name__}: {exc}")
        try:
            text = self._tesseract_ocr(image)
            if text.strip():
                return text, "tesseract"
        except Exception as exc:
            errors.append(f"Tesseract: {type(exc).__name__}: {exc}")
        raise RuntimeError("تعذر استخراج النص محليًا. " + " | ".join(errors))

    def analyze(self, selected: list[str] | tuple[str, ...]) -> tuple[InstructionImageAnalysis, ...]:
        imported = self._import_images(selected)
        analyses: list[InstructionImageAnalysis] = []
        for source, image in imported:
            text, engine = self._extract(image)
            scenes = plan_instruction_scenes(text)
            analyses.append(
                InstructionImageAnalysis(
                    source=str(source),
                    imported=str(image.relative_to(self.root)),
                    engine=engine,
                    text=text,
                    scenes=scenes,
                )
            )
        self.state.record_event(
            "product_ad.instruction_images.analyzed",
            {
                "image_count": len(analyses),
                "scene_count": sum(len(item.scenes) for item in analyses),
                "engines": sorted({item.engine for item in analyses}),
            },
            agent="Image Instruction Interpreter",
        )
        return tuple(analyses)
