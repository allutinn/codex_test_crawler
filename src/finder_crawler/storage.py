from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping

from .config import CrawlConfig
from .utils import ensure_directory, write_json


@dataclass
class CompanyRecord:
    industry: str
    company_id: str
    storage_id: str
    search_payload: Mapping[str, Any]
    detail_payload: Mapping[str, Any]
    search_context: Mapping[str, Any]
    metadata: Mapping[str, Any]

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "industry": self.industry,
            "company_id": self.company_id,
            "storage_id": self.storage_id,
            "search_payload": self.search_payload,
            "detail_payload": self.detail_payload,
            "search_context": self.search_context,
            "metadata": self.metadata,
        }


class JsonStorage:
    def __init__(self, config: CrawlConfig) -> None:
        self._config = config
        ensure_directory(self._config.output_dir)
        self._index_path = self._config.output_dir / "_index.json"
        self._index: Dict[str, Dict[str, str]] = self._load_index()

    def _load_index(self) -> Dict[str, Dict[str, str]]:
        if not self._index_path.exists():
            return {}
        try:
            with self._index_path.open("r", encoding="utf-8") as handle:
                payload: MutableMapping[str, Any] = json.load(handle)
        except (json.JSONDecodeError, OSError):  # pragma: no cover - defensive
            return {}
        result: Dict[str, Dict[str, str]] = {}
        for industry, mapping in payload.items():
            if isinstance(mapping, Mapping):
                result[str(industry)] = {
                    str(company_id): str(storage_id)
                    for company_id, storage_id in mapping.items()
                }
        return result

    def _save_index(self) -> None:
        write_json(self._index_path, self._index)

    def company_path(self, industry: str, storage_id: str) -> Path:
        safe_industry = industry.replace("/", "-").replace(" ", "_")
        return self._config.output_dir / safe_industry / f"{storage_id}.json"

    def company_exists(self, industry: str, company_id: str) -> bool:
        industry_index = self._index.get(industry, {})
        storage_id = industry_index.get(company_id)
        if not storage_id:
            legacy_path = self.company_path(industry, company_id)
            if legacy_path.exists():
                industry_index[company_id] = company_id
                self._index[industry] = industry_index
                self._save_index()
                return True
            return False
        path = self.company_path(industry, storage_id)
        if path.exists():
            return True
        # Clean up stale index entries if the file disappeared
        del industry_index[company_id]
        if not industry_index:
            self._index.pop(industry, None)
        self._save_index()
        return False

    def write_company(self, record: CompanyRecord) -> Path:
        path = self.company_path(record.industry, record.storage_id)
        if path.exists():
            return path
        write_json(path, record.as_dict())
        industry_index = self._index.setdefault(record.industry, {})
        industry_index[record.company_id] = record.storage_id
        self._save_index()
        return path

    def make_storage_id(self, industry: str, company_name: str, business_id: str | None) -> str:
        name_segment = self._normalise_segment(company_name) or "company"
        business_segment = self._normalise_segment(business_id or "") or "unknown"
        base = f"{name_segment}_{business_segment}" if name_segment else business_segment
        candidate = base or "company"
        counter = 1
        while self.company_path(industry, candidate).exists():
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    @staticmethod
    def _normalise_segment(value: str) -> str:
        value = unicodedata.normalize("NFKD", value.strip().lower())
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = re.sub(r"[^a-z0-9]+", "_", value)
        return value.strip("_")

