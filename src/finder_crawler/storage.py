from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .config import CrawlConfig
from .utils import ensure_directory, write_json


@dataclass
class CompanyRecord:
    industry: str
    company_id: str
    search_payload: Mapping[str, Any]
    detail_payload: Mapping[str, Any]
    search_context: Mapping[str, Any]
    metadata: Mapping[str, Any]

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "industry": self.industry,
            "company_id": self.company_id,
            "search_payload": self.search_payload,
            "detail_payload": self.detail_payload,
            "search_context": self.search_context,
            "metadata": self.metadata,
        }


class JsonStorage:
    def __init__(self, config: CrawlConfig) -> None:
        self._config = config
        ensure_directory(self._config.output_dir)

    def company_path(self, industry: str, company_id: str) -> Path:
        safe_industry = industry.replace("/", "-").replace(" ", "_")
        return self._config.output_dir / safe_industry / f"{company_id}.json"

    def write_company(self, record: CompanyRecord) -> Path:
        path = self.company_path(record.industry, record.company_id)
        write_json(path, record.as_dict())
        return path

