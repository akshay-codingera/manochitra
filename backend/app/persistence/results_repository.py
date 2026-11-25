"""JSON-file repository for the required results.json artifact."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from app.core import config


class ResultsRepository:
    """Small atomic JSON repository; no database is required for this brief."""

    def __init__(self, path: Path | None = None):
        self.path = path or config.RESULTS_PATH
        self._lock = RLock()
        self._memory_payload: dict[str, Any] | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write_payload({"schema_version": 1, "generated_at": None, "results": []})
        except OSError:
            pass

    def _read_payload(self) -> dict[str, Any]:
        with self._lock:
            if self._memory_payload is not None:
                return self._memory_payload
            if self.path.exists():
                try:
                    payload = json.loads(self.path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"Could not read results file {self.path}: {exc}") from exc
                if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                    raise RuntimeError("results.json has an invalid structure; expected an object with a results array.")
                return payload
            # Try /tmp fallback before returning empty
            tmp_path = Path("/tmp") / self.path.name
            if tmp_path.exists():
                try:
                    payload = json.loads(tmp_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
                        return payload
                except (OSError, json.JSONDecodeError):
                    pass
            default_payload = {"schema_version": 1, "generated_at": None, "results": []}
            self._memory_payload = default_payload
            return default_payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._memory_payload = payload
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(prefix="results-", suffix=".json", dir=self.path.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                    os.replace(temp_name, self.path)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
            except OSError:
                # Read-only filesystem fallback (e.g. Vercel serverless)
                tmp_dir = Path("/tmp")
                if tmp_dir.exists() and os.access(str(tmp_dir), os.W_OK):
                    try:
                        (tmp_dir / self.path.name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    except OSError:
                        pass

    def all(self) -> list[dict[str, Any]]:
        return self._read_payload()["results"]

    def by_concept(self, concept_id: str) -> dict[str, Any] | None:
        return next((item for item in self.all() if item.get("concept_id") == concept_id), None)

    def upsert(self, result: dict[str, Any]) -> None:
        with self._lock:
            payload = self._read_payload()
            results = payload["results"]
            existing_index = next(
                (index for index, item in enumerate(results) if item.get("concept_id") == result.get("concept_id")),
                None,
            )
            if existing_index is None:
                results.append(result)
            else:
                results[existing_index] = result
            payload["generated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_payload(payload)

    def replace_all(self, results: list[dict[str, Any]]) -> None:
        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
        }
        self._write_payload(payload)


class ModelRunsRepository:
    """Atomic JSON repository for experimental multi-model runs in data/model_runs.json.

    Maintains runs keyed by (concept_id, model) so that one model's result never
    overwrites another model's experimental result.
    """

    def __init__(self, path: Path | None = None):
        self.path = path or config.MODEL_RUNS_PATH
        self._lock = RLock()
        self._memory_payload: dict[str, Any] | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write_payload({"schema_version": 1, "updated_at": None, "runs": []})
        except OSError:
            pass

    def _read_payload(self) -> dict[str, Any]:
        with self._lock:
            if self._memory_payload is not None:
                return self._memory_payload
            if self.path.exists():
                try:
                    payload = json.loads(self.path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"Could not read model_runs file {self.path}: {exc}") from exc
                if not isinstance(payload, dict) or not isinstance(payload.get("runs"), list):
                    raise RuntimeError("model_runs.json has an invalid structure; expected an object with a runs array.")
                return payload
            tmp_path = Path("/tmp") / self.path.name
            if tmp_path.exists():
                try:
                    payload = json.loads(tmp_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict) and isinstance(payload.get("runs"), list):
                        return payload
                except (OSError, json.JSONDecodeError):
                    pass
            default_payload = {"schema_version": 1, "updated_at": None, "runs": []}
            self._memory_payload = default_payload
            return default_payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._memory_payload = payload
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(prefix="model_runs-", suffix=".json", dir=self.path.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                    os.replace(temp_name, self.path)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
            except OSError:
                tmp_dir = Path("/tmp")
                if tmp_dir.exists() and os.access(str(tmp_dir), os.W_OK):
                    try:
                        (tmp_dir / self.path.name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    except OSError:
                        pass

    def all(self) -> list[dict[str, Any]]:
        return self._read_payload()["runs"]

    def by_concept_and_model(self, concept_id: str, model: str) -> dict[str, Any] | None:
        return next(
            (
                item for item in self.all()
                if item.get("concept_id") == concept_id and item.get("model") == model
            ),
            None,
        )

    def upsert(self, result: dict[str, Any]) -> None:
        with self._lock:
            payload = self._read_payload()
            runs = payload["runs"]
            # Match by both concept_id AND model: models never overwrite each other
            existing_index = next(
                (
                    index for index, item in enumerate(runs)
                    if item.get("concept_id") == result.get("concept_id")
                    and item.get("model") == result.get("model")
                ),
                None,
            )
            if existing_index is None:
                runs.append(result)
            else:
                runs[existing_index] = result
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_payload(payload)

    def replace_all(self, runs: list[dict[str, Any]]) -> None:
        payload = {
            "schema_version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "runs": runs,
        }
        self._write_payload(payload)


class VersionsRepository:
    """Atomic JSON repository for concept version history in data/versions.json.

    Tracks every generated diagram version per concept:
    - version number (1, 2, ...)
    - original SVG
    - rejection reason / user feedback
    - regeneration prompt metadata
    - model ID
    - token usage
    - validation report
    - visual-quality report
    - generation timestamp
    - review status ('approved', 'rejected', 'pending_review')
    - reviewed_at timestamp
    """

    def __init__(self, path: Path | None = None):
        self.path = path or config.VERSIONS_PATH
        self._lock = RLock()
        self._memory_payload: dict[str, Any] | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write_payload({"schema_version": 1, "updated_at": None, "versions": {}})
        except OSError:
            pass

    def _read_payload(self) -> dict[str, Any]:
        with self._lock:
            if self._memory_payload is not None:
                return self._memory_payload
            if self.path.exists():
                try:
                    payload = json.loads(self.path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"Could not read versions file {self.path}: {exc}") from exc
                if not isinstance(payload, dict) or not isinstance(payload.get("versions"), dict):
                    raise RuntimeError("versions.json has an invalid structure; expected an object with a versions dict.")
                return payload
            tmp_path = Path("/tmp") / self.path.name
            if tmp_path.exists():
                try:
                    payload = json.loads(tmp_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict) and isinstance(payload.get("versions"), dict):
                        return payload
                except (OSError, json.JSONDecodeError):
                    pass
            default_payload = {"schema_version": 1, "updated_at": None, "versions": {}}
            self._memory_payload = default_payload
            return default_payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._memory_payload = payload
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(prefix="versions-", suffix=".json", dir=self.path.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                    os.replace(temp_name, self.path)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
            except OSError:
                tmp_dir = Path("/tmp")
                if tmp_dir.exists() and os.access(str(tmp_dir), os.W_OK):
                    try:
                        (tmp_dir / self.path.name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    except OSError:
                        pass

    def all_by_concept(self) -> dict[str, list[dict[str, Any]]]:
        return self._read_payload()["versions"]

    def get_versions(self, concept_id: str) -> list[dict[str, Any]]:
        return self._read_payload()["versions"].get(concept_id, [])

    def get_version(self, concept_id: str, version: int) -> dict[str, Any] | None:
        versions = self.get_versions(concept_id)
        return next((v for v in versions if v.get("version") == version), None)

    def get_latest_version(self, concept_id: str) -> dict[str, Any] | None:
        versions = self.get_versions(concept_id)
        if not versions:
            return None
        return max(versions, key=lambda v: v.get("version", 0))

    def add_version(self, concept_id: str, version_data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            payload = self._read_payload()
            concept_versions = payload["versions"].setdefault(concept_id, [])

            # Compute next version number if not explicitly specified
            if "version" not in version_data or not version_data["version"]:
                next_version = (max((v.get("version", 0) for v in concept_versions), default=0)) + 1
                version_data["version"] = next_version

            # Default review status
            version_data.setdefault("concept_id", concept_id)
            version_data.setdefault("review_status", "pending_review")
            version_data.setdefault("rejection_reason", None)
            version_data.setdefault("regeneration_metadata", None)
            version_data.setdefault("generated_at", datetime.now(timezone.utc).isoformat())

            # Check if this version number already exists; replace or append
            idx = next((i for i, v in enumerate(concept_versions) if v.get("version") == version_data["version"]), None)
            if idx is None:
                concept_versions.append(version_data)
            else:
                concept_versions[idx] = version_data

            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_payload(payload)
            return version_data

    def update_review(
        self,
        concept_id: str,
        decision: str,
        note: str = "",
        version: int | None = None,
    ) -> dict[str, Any]:
        """Update review decision on a specific version (or latest if version is None)."""
        with self._lock:
            payload = self._read_payload()
            concept_versions = payload["versions"].get(concept_id, [])
            if not concept_versions:
                raise ValueError(f"No versions found for concept '{concept_id}'.")

            if version is None:
                target_version = max(concept_versions, key=lambda v: v.get("version", 0))
            else:
                target_version = next((v for v in concept_versions if v.get("version") == version), None)
                if target_version is None:
                    raise ValueError(f"Version {version} not found for concept '{concept_id}'.")

            target_version["review_status"] = decision
            target_version["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            if decision == "rejected":
                target_version["rejection_reason"] = note
            elif decision == "approved":
                target_version["approval_note"] = note

            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_payload(payload)
            return target_version

    def seed_initial_versions_from_results(self, results: list[dict[str, Any]]) -> None:
        """Seed version 1 for any concept present in results that does not yet have version history."""
        with self._lock:
            payload = self._read_payload()
            versions_dict = payload["versions"]
            updated = False
            for r in results:
                cid = r.get("concept_id")
                if not cid or cid in versions_dict:
                    continue
                if r.get("svg"):
                    v1_record = {
                        "version": 1,
                        "concept_id": cid,
                        "concept": r.get("concept"),
                        "subject": r.get("subject"),
                        "source_text": r.get("source_text"),
                        "svg": r.get("svg"),
                        "model": r.get("model", "gemini-3.5-flash-lite"),
                        "usage": r.get("usage", {}),
                        "cost": r.get("cost", {}),
                        "retries": r.get("retries", {}),
                        "checks": r.get("checks", {}),
                        "visual_quality": r.get("visual_quality", {}),
                        "status": r.get("status", "PASS"),
                        "latency_ms": r.get("latency_ms"),
                        "timings_ms": r.get("timings_ms", {}),
                        "generated_at": r.get("generated_at"),
                        "review_status": "approved" if r.get("status") == "PASS" else "pending_review",
                        "rejection_reason": None,
                        "regeneration_metadata": None,
                        "reviewed_at": r.get("generated_at"),
                    }
                    versions_dict[cid] = [v1_record]
                    updated = True
            if updated:
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._write_payload(payload)


class ReviewsRepository:
    """Atomic JSON repository for human review decisions in data/reviews.json."""

    def __init__(self, path: Path | None = None):
        self.path = path or config.REVIEWS_PATH
        self._lock = RLock()
        self._memory_payload: dict[str, Any] | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write_payload({"schema_version": 1, "updated_at": None, "reviews": {}})
        except OSError:
            pass

    def _read_payload(self) -> dict[str, Any]:
        with self._lock:
            if self._memory_payload is not None:
                return self._memory_payload
            if self.path.exists():
                try:
                    payload = json.loads(self.path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"Could not read reviews file {self.path}: {exc}") from exc
                if not isinstance(payload, dict) or not isinstance(payload.get("reviews"), dict):
                    raise RuntimeError("reviews.json has an invalid structure; expected an object with a reviews dict.")
                return payload
            tmp_path = Path("/tmp") / self.path.name
            if tmp_path.exists():
                try:
                    payload = json.loads(tmp_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict) and isinstance(payload.get("reviews"), dict):
                        return payload
                except (OSError, json.JSONDecodeError):
                    pass
            default_payload = {"schema_version": 1, "updated_at": None, "reviews": {}}
            self._memory_payload = default_payload
            return default_payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._memory_payload = payload
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(prefix="reviews-", suffix=".json", dir=self.path.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                    os.replace(temp_name, self.path)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
            except OSError:
                tmp_dir = Path("/tmp")
                if tmp_dir.exists() and os.access(str(tmp_dir), os.W_OK):
                    try:
                        (tmp_dir / self.path.name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    except OSError:
                        pass

    def all(self) -> dict[str, dict[str, Any]]:
        return self._read_payload()["reviews"]

    def get(self, concept_id: str) -> dict[str, Any]:
        return self.all().get(concept_id, {"concept_id": concept_id, "decision": "pending", "note": "", "version": 1})

    def save(self, concept_id: str, decision: str, note: str = "", version: int = 1) -> dict[str, Any]:
        with self._lock:
            payload = self._read_payload()
            record = {
                "concept_id": concept_id,
                "decision": decision,
                "note": note,
                "version": version,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            payload["reviews"][concept_id] = record
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_payload(payload)
            return record


