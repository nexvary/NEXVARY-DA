from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .permissions import Permission, WorkspaceGuard
from .state import ProjectState


_MARKETPLACE_HOSTS = {
    "amazon.", "ebay.", "aliexpress.", "temu.", "noon.", "walmart.",
}


@dataclass(frozen=True, slots=True)
class ResearchSource:
    title: str
    url: str
    snippet: str
    likely_official: bool
    extracted_chars: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ResearchFact:
    key: str
    value: str
    arabic: str
    source_urls: tuple[str, ...]
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProductResearchReport:
    query: str
    sources: tuple[ResearchSource, ...]
    facts: tuple[ResearchFact, ...]
    warnings: tuple[str, ...]

    @property
    def verified_facts(self) -> tuple[ResearchFact, ...]:
        return tuple(item for item in self.facts if item.verified)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["verified_facts"] = [item.to_dict() for item in self.verified_facts]
        return payload


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _brand_token(product_name: str) -> str:
    for token in re.findall(r"[A-Za-z0-9]{3,}", product_name):
        return token.lower()
    return ""


def _likely_official(url: str, title: str, product_name: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host or any(marker in host for marker in _MARKETPLACE_HOSTS):
        return False
    brand = _brand_token(product_name)
    if brand and brand in _compact(host):
        return True
    lowered = title.lower()
    return bool(brand and brand in lowered and any(word in lowered for word in ("official", "support", "manual")))


def extract_fact_candidates(text: str) -> list[tuple[str, str, str]]:
    """Extract conservative camera/product facts without inventing unsupported specs."""
    value = re.sub(r"\s+", " ", text or "")
    found: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(key: str, raw: str, arabic: str) -> None:
        normalized = raw.strip()
        marker = (key, normalized.lower())
        if not normalized or marker in seen:
            return
        seen.add(marker)
        found.append((key, normalized, arabic))

    for match in re.finditer(r"\b(720p|1080p|2k|3k|4k|5k|8k)\b", value, flags=re.I):
        raw = match.group(1).upper()
        add("resolution", raw, f"دقة الفيديو المذكورة في المصادر: {raw}")

    for match in re.finditer(r"\b(\d{1,2}(?:\.\d+)?)\s*(MP|megapixels?)\b", value, flags=re.I):
        raw = f"{match.group(1)} MP"
        add("megapixels", raw, f"الدقة المذكورة للكاميرا: {raw}")

    for match in re.finditer(r"\b(2\.4\s*GHz|5\s*GHz|Wi-?Fi\s*6|Wi-?Fi)\b", value, flags=re.I):
        raw = re.sub(r"\s+", " ", match.group(1))
        add("wifi", raw, f"الاتصال المذكور في المصادر: {raw}")

    for match in re.finditer(r"\b(4G\s*LTE|4G|5G)\b", value, flags=re.I):
        raw = re.sub(r"\s+", " ", match.group(1).upper())
        add("cellular", raw, f"اتصال الشبكة المذكور في المصادر: {raw}")

    for match in re.finditer(r"\b(IP(?:65|66|67|68))\b", value, flags=re.I):
        raw = match.group(1).upper()
        add("ip_rating", raw, f"تصنيف الحماية المذكور: {raw}")

    for match in re.finditer(
        r"\b(?:micro\s*SD|microSD|TF\s*card)\b.{0,55}?\b(\d{2,4})\s*GB\b",
        value,
        flags=re.I,
    ):
        raw = f"{match.group(1)} GB"
        add("storage", raw, f"سعة بطاقة الذاكرة المذكورة تصل إلى {raw}")

    if re.search(r"\b(?:night vision|infrared night|IR night)\b", value, flags=re.I):
        add("night_vision", "night vision", "تذكر المصادر وجود رؤية ليلية")

    if re.search(r"\b(?:two[- ]way audio|2[- ]way audio|two[- ]way talk)\b", value, flags=re.I):
        add("two_way_audio", "two-way audio", "تذكر المصادر وجود صوت ثنائي الاتجاه")

    if re.search(r"\b(?:motion detection|human detection|person detection)\b", value, flags=re.I):
        add("detection", "motion/human detection", "تذكر المصادر وجود خاصية كشف الحركة أو الأشخاص")

    return found


class ProductResearcher:
    """Research an exact product/model and keep source provenance for every extracted fact."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        state: ProjectState,
        root: str | Path,
    ):
        self.guard = guard
        self.state = state
        self.root = Path(root).resolve(strict=True)

    def research(
        self,
        product_name: str,
        model: str,
        *,
        max_results: int = 8,
        max_fetch: int = 5,
    ) -> ProductResearchReport:
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        product_name = product_name.strip()
        model = model.strip()
        if not product_name and not model:
            raise ValueError("Product name or model is required for research")

        try:
            from ddgs import DDGS
        except ImportError as exc:
            raise RuntimeError("Product research requires the ddgs package") from exc

        try:
            import trafilatura
        except ImportError as exc:
            raise RuntimeError("Product research requires the trafilatura package") from exc

        exact = " ".join(part for part in (product_name, model) if part).strip()
        queries = [
            f'"{exact}" official specifications',
            f'"{exact}" manual setup installation',
        ]

        raw_results: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        client = DDGS()
        for query in queries:
            try:
                results = client.text(query, max_results=max_results)
            except Exception:
                continue
            for item in results or []:
                url = str(item.get("href") or item.get("url") or "").strip()
                if not url.startswith(("http://", "https://")) or url in seen_urls:
                    continue
                seen_urls.add(url)
                raw_results.append(
                    {
                        "title": str(item.get("title") or "").strip(),
                        "url": url,
                        "snippet": str(item.get("body") or item.get("snippet") or "").strip(),
                    }
                )

        if not raw_results:
            report = ProductResearchReport(exact, (), (), ("لم يتم العثور على مصادر بحث متاحة.",))
            self.state.record_event(
                "product_research.completed",
                {"query": exact, "source_count": 0, "verified_fact_count": 0},
                agent="Product Research",
            )
            return report

        def score(item: dict[str, str]) -> tuple[int, int]:
            hay = _compact(item["title"] + " " + item["snippet"])
            model_hit = 1 if model and _compact(model) in hay else 0
            official = 1 if _likely_official(item["url"], item["title"], product_name) else 0
            return (official, model_hit)

        raw_results.sort(key=score, reverse=True)
        sources: list[ResearchSource] = []
        source_texts: list[str] = []

        for index, item in enumerate(raw_results[:max_fetch]):
            extracted = ""
            try:
                downloaded = trafilatura.fetch_url(item["url"])
                if downloaded:
                    extracted = trafilatura.extract(
                        downloaded,
                        include_comments=False,
                        include_tables=True,
                        favor_precision=True,
                    ) or ""
            except Exception:
                extracted = ""
            source_text = " ".join(part for part in (item["title"], item["snippet"], extracted) if part)
            sources.append(
                ResearchSource(
                    title=item["title"],
                    url=item["url"],
                    snippet=item["snippet"],
                    likely_official=_likely_official(item["url"], item["title"], product_name),
                    extracted_chars=len(extracted),
                )
            )
            source_texts.append(source_text)

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for index, source_text in enumerate(source_texts):
            for key, value, arabic in extract_fact_candidates(source_text):
                group_key = (key, value.lower())
                bucket = grouped.setdefault(
                    group_key,
                    {"key": key, "value": value, "arabic": arabic, "source_indexes": set()},
                )
                bucket["source_indexes"].add(index)

        facts: list[ResearchFact] = []
        for bucket in grouped.values():
            indexes = sorted(bucket["source_indexes"])
            urls = tuple(sources[index].url for index in indexes)
            verified = len(indexes) >= 2 or any(sources[index].likely_official for index in indexes)
            facts.append(
                ResearchFact(
                    key=bucket["key"],
                    value=bucket["value"],
                    arabic=bucket["arabic"],
                    source_urls=urls,
                    verified=verified,
                )
            )

        warnings: list[str] = []
        if not any(source.likely_official for source in sources):
            warnings.append("لم أتعرف آليًا على مصدر يبدو رسميًا؛ لن تُستخدم الحقائق أحادية المصدر في التعليق.")
        if not any(fact.verified for fact in facts):
            warnings.append("لم توجد مواصفات وصلت إلى حد التحقق؛ سيبقى الإعلان معتمدًا على بيانات البائع والفيديو الحقيقي فقط.")

        report = ProductResearchReport(exact, tuple(sources), tuple(facts), tuple(warnings))
        self.state.record_event(
            "product_research.completed",
            {
                "query": exact,
                "source_count": len(sources),
                "verified_fact_count": len(report.verified_facts),
                "warning_count": len(warnings),
            },
            agent="Product Research",
        )
        return report
