from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional

from .utils import ensure_directory, timestamp_utc, write_json


@dataclass
class IndustryProgress:
    """Track crawl progress for a single industry."""

    name: str
    next_page: int = 1
    next_index: int = 1
    completed: bool = False
    pages_visited: int = 0
    last_visited_page: int = 0
    companies_written: int = 0
    last_company_id: Optional[str] = None

    def as_dict(self) -> Mapping[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "IndustryProgress":
        return cls(
            name=str(payload.get("name")),
            next_page=int(payload.get("next_page", 1)),
            next_index=int(payload.get("next_index", 1)),
            completed=bool(payload.get("completed", False)),
            pages_visited=int(payload.get("pages_visited", 0)),
            companies_written=int(payload.get("companies_written", 0)),
            last_company_id=(payload.get("last_company_id") or None),
            last_visited_page=int(payload.get("last_visited_page", 0)),
        )


@dataclass
class RunState:
    """Persisted progress for a long running crawl."""

    run_id: str
    created_at: str = field(default_factory=timestamp_utc)
    industries: Dict[str, IndustryProgress] = field(default_factory=dict)
    total_companies_written: int = 0
    total_pages_visited: int = 0

    @classmethod
    def initialise(cls, run_id: str, industries: Iterable[str]) -> "RunState":
        state = cls(run_id=run_id)
        for name in industries:
            state.industries[name] = IndustryProgress(name=name)
        return state

    @classmethod
    def load(cls, path: Path) -> "RunState":
        payload = {} if not path.exists() else cls._read_json(path)
        run_id = str(payload.get("run_id") or path.parent.name)
        state = cls(run_id=run_id)
        state.created_at = str(payload.get("created_at", timestamp_utc()))
        state.total_companies_written = int(payload.get("total_companies_written", 0))
        state.total_pages_visited = int(payload.get("total_pages_visited", 0))
        industries_payload = payload.get("industries", {})
        if isinstance(industries_payload, Mapping):
            for name, progress_payload in industries_payload.items():
                if isinstance(progress_payload, Mapping):
                    state.industries[name] = IndustryProgress.from_dict(progress_payload)
        return state

    def ensure_industries(self, industries: Iterable[str]) -> None:
        for name in industries:
            if name not in self.industries:
                self.industries[name] = IndustryProgress(name=name)

    def remaining_industries(self) -> List[str]:
        return [name for name, prog in self.industries.items() if not prog.completed]

    def industry_progress(self, industry: str) -> IndustryProgress:
        try:
            return self.industries[industry]
        except KeyError:  # pragma: no cover - defensive
            raise KeyError(f"Industry '{industry}' not present in run state")

    def record_page_visit(self, industry: str, page: int) -> None:
        progress = self.industry_progress(industry)
        if page != progress.last_visited_page:
            progress.pages_visited += 1
            progress.last_visited_page = page
            self.total_pages_visited += 1

    def record_company(
        self,
        industry: str,
        page: int,
        index_on_page: int,
        company_id: Optional[str],
        wrote_to_storage: bool,
    ) -> None:
        progress = self.industry_progress(industry)
        progress.next_page = page
        progress.next_index = index_on_page + 1
        progress.last_company_id = company_id
        if wrote_to_storage:
            progress.companies_written += 1
            self.total_companies_written += 1

    def mark_page_complete(self, industry: str, page: int) -> None:
        progress = self.industry_progress(industry)
        if progress.next_page <= page:
            progress.next_page = page + 1
            progress.next_index = 1

    def mark_industry_complete(self, industry: str) -> None:
        progress = self.industry_progress(industry)
        progress.completed = True

    def to_dict(self) -> Mapping[str, object]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "industries": {name: prog.as_dict() for name, prog in self.industries.items()},
            "total_companies_written": self.total_companies_written,
            "total_pages_visited": self.total_pages_visited,
        }

    def save(self, path: Path) -> None:
        ensure_directory(path.parent)
        write_json(path, self.to_dict())

    @staticmethod
    def _read_json(path: Path) -> MutableMapping[str, object]:
        import json

        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)


@dataclass
class RunWorkspace:
    """Filesystem layout helper for crawl runs."""

    base_dir: Path
    run_dir: Path
    companies_dir: Path
    logs_dir: Path
    state_path: Path
    metadata_path: Path
    is_resume: bool
    run_id: str

    @classmethod
    def prepare(cls, config_output_dir: Path, run_id: Optional[str], resume_from: Optional[Path]) -> "RunWorkspace":
        ensure_directory(config_output_dir)
        is_resume = False
        if resume_from:
            run_dir = resume_from if resume_from.is_absolute() else config_output_dir / resume_from
            run_dir = run_dir.resolve()
            if not run_dir.exists():
                raise FileNotFoundError(f"Cannot resume crawl; directory not found: {run_dir}")
            run_id_value = run_dir.name
            is_resume = True
        else:
            run_id_value = run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            run_dir = (config_output_dir / run_id_value).resolve()
            ensure_directory(run_dir)

        companies_dir = run_dir / "companies"
        logs_dir = run_dir / "logs"
        state_path = run_dir / "state.json"
        metadata_path = run_dir / "run_metadata.json"

        ensure_directory(companies_dir)
        ensure_directory(logs_dir)

        return cls(
            base_dir=config_output_dir,
            run_dir=run_dir,
            companies_dir=companies_dir,
            logs_dir=logs_dir,
            state_path=state_path,
            metadata_path=metadata_path,
            is_resume=is_resume,
            run_id=run_id_value,
        )

