"""Orchestrates prompt -> Gemini -> SVG validation -> one repair -> logging."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core import config
from app.core.concepts import CONCEPT_BY_ID
from app.core.models import calculate_token_cost, validate_model_id
from app.services.gemini_client import GeminiAPIError, GeminiClient, MissingAPIKeyError, ModelResponse
from app.services.prompt_builder import build_feedback_regeneration_prompt, build_generation_prompt
from app.services.retry_handler import call_with_transient_retries
from app.validators.concept_structure_validator import validate_concept_structure
from app.validators.svg_validator import extract_svg, validate_svg
from app.validators.visual_quality_validator import VisualQualityReport, validate_visual_quality


class GenerationPipeline:
    def __init__(self, client: GeminiClient | None = None):
        self.client = client or GeminiClient()

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_id: str | None = None,
        usage_metadata_available: bool = True,
    ) -> dict[str, Any]:
        target_model = model_id or self.client.model
        return calculate_token_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_id=target_model,
            billing_tier=config.GEMINI_BILLING_TIER,
            usage_metadata_available=usage_metadata_available,
        )

    @staticmethod
    def _empty_checks(reason: str) -> dict[str, dict[str, Any]]:
        return {
            name: {"passed": False, "detail": reason}
            for name in (
                "valid_svg",
                "within_viewbox",
                "title_and_labels",
                "has_animation",
                "scientific_terms",
                "concept_structure",
            )
        }

    def _validate_full(self, svg: str, concept: dict[str, Any], timings: dict[str, float]) -> tuple[Any, VisualQualityReport]:
        """Run standard SVG validation, advanced concept structure validation, and visual quality safeguards."""
        svg_val_start = time.perf_counter()
        report = validate_svg(svg, concept)
        timings["svg_validation_ms"] += (time.perf_counter() - svg_val_start) * 1000

        cs_val_start = time.perf_counter()
        cs_result = validate_concept_structure(report.parsed_root, concept)
        timings["concept_structure_ms"] += (time.perf_counter() - cs_val_start) * 1000

        report.checks["concept_structure"] = cs_result

        vq_start = time.perf_counter()
        vq_report = validate_visual_quality(report.parsed_root, concept)
        timings["visual_quality_ms"] += (time.perf_counter() - vq_start) * 1000

        timings["validation_ms"] = round(timings["svg_validation_ms"] + timings["concept_structure_ms"] + timings["visual_quality_ms"], 2)
        return report, vq_report

    async def generate(self, concept_id: str, model: str | None = None) -> dict[str, Any]:
        concept = CONCEPT_BY_ID.get(concept_id)
        if concept is None:
            raise ValueError(f"Unknown concept id '{concept_id}'.")

        chosen_model = validate_model_id(model or self.client.model)
        active_client = (
            self.client
            if self.client.model == chosen_model
            else GeminiClient(api_key=self.client.api_key, model=chosen_model)
        )

        started = time.perf_counter()
        input_tokens = 0
        output_tokens = 0
        thinking_tokens = 0
        usage_metadata_available = True
        model_response_count = 0
        api_retries = 0
        validation_retries = 0
        attempt_history: list[dict[str, Any]] = []
        trace_id = str(uuid4())
        timings: dict[str, float] = {
            "prompt_build_ms": 0.0,
            "model_request_with_retries_ms": 0.0,
            "svg_validation_ms": 0.0,
            "concept_structure_ms": 0.0,
            "visual_quality_ms": 0.0,
            "validation_ms": 0.0,
        }
        svg = ""
        last_error: str | None = None
        final_checks: dict[str, dict[str, Any]] = self._empty_checks("Generation has not completed.")
        final_vq: VisualQualityReport | None = None
        status = "ERROR"

        async def request(prompt: str) -> ModelResponse:
            request_started = time.perf_counter()
            try:
                outcome = await call_with_transient_retries(lambda: active_client.generate_svg(prompt))
                nonlocal api_retries
                api_retries += outcome.retries
                return outcome.value
            finally:
                timings["model_request_with_retries_ms"] += (time.perf_counter() - request_started) * 1000

        try:
            prompt_started = time.perf_counter()
            first_prompt = build_generation_prompt(concept)
            timings["prompt_build_ms"] += (time.perf_counter() - prompt_started) * 1000
            first_response = await request(first_prompt)
            model_response_count += 1
            input_tokens += first_response.input_tokens
            output_tokens += first_response.output_tokens
            thinking_tokens += getattr(first_response, "thinking_tokens", 0)
            usage_metadata_available = usage_metadata_available and getattr(first_response, "usage_metadata_available", True)
            svg = extract_svg(first_response.text)

            first_report, first_vq = self._validate_full(svg, concept, timings)
            attempt_history.append({
                "attempt": 1,
                "model": chosen_model,
                "checks": first_report.as_dict(),
                "passed": first_report.passed,
                "visual_quality": first_vq.to_dict(),
            })
            final_checks = first_report.as_dict()
            final_vq = first_vq
            status = "PASS" if first_report.passed else "FAIL"

            if not first_report.passed:
                validation_retries = 1
                prompt_started = time.perf_counter()
                repair_prompt = build_generation_prompt(concept, failure_reasons=first_report.failures)
                timings["prompt_build_ms"] += (time.perf_counter() - prompt_started) * 1000
                try:
                    repaired_response = await request(repair_prompt)
                    model_response_count += 1
                    input_tokens += repaired_response.input_tokens
                    output_tokens += repaired_response.output_tokens
                    thinking_tokens += getattr(repaired_response, "thinking_tokens", 0)
                    usage_metadata_available = usage_metadata_available and getattr(repaired_response, "usage_metadata_available", True)
                    repaired_svg = extract_svg(repaired_response.text)

                    repaired_report, repaired_vq = self._validate_full(repaired_svg, concept, timings)
                    attempt_history.append({
                        "attempt": 2,
                        "model": chosen_model,
                        "checks": repaired_report.as_dict(),
                        "passed": repaired_report.passed,
                        "repair_reasons": first_report.failures,
                        "visual_quality": repaired_vq.to_dict(),
                    })
                    svg = repaired_svg
                    final_checks = repaired_report.as_dict()
                    final_vq = repaired_vq
                    status = "PASS" if repaired_report.passed else "FAIL"
                    if not repaired_report.passed:
                        last_error = "The SVG still failed validation after the single permitted repair attempt."
                except GeminiAPIError as exc:
                    api_retries += getattr(exc, "retry_count", 0)
                    last_error = f"The corrective generation failed: {exc}"
                    status = "FAIL"
                except MissingAPIKeyError:
                    raise

        except MissingAPIKeyError:
            raise
        except GeminiAPIError as exc:
            api_retries += getattr(exc, "retry_count", 0)
            status_desc = {
                408: "Request Timeout",
                429: "Rate Limit Exceeded",
                503: "High Demand / Service Unavailable",
            }.get(exc.status_code, "Error")
            last_error = f"Gemini API error (HTTP {exc.status_code} {status_desc}): {exc}"
            status = "ERROR"
            final_checks = self._empty_checks("Not run because the Gemini request did not return an SVG.")

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        usage_metadata_available = usage_metadata_available and model_response_count > 0
        cost = self._calculate_cost(input_tokens, output_tokens, chosen_model, usage_metadata_available)
        return {
            "trace_id": trace_id,
            "concept_id": concept["id"],
            "concept": concept["name"],
            "subject": concept["subject"],
            "source_text": concept["source_text"],
            "svg": svg,
            "model": chosen_model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "thinking_tokens": thinking_tokens,
                "metadata_available": usage_metadata_available,
            },
            "cost": cost,
            "retries": {
                "api_retries": api_retries,
                "validation_retries": validation_retries,
                "total_retries": api_retries + validation_retries,
            },
            "checks": final_checks,
            "visual_quality": final_vq.to_dict() if final_vq else None,
            "status": status,
            "latency_ms": elapsed_ms,
            "timings_ms": {key: round(value, 2) for key, value in timings.items()},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "last_error": last_error,
            "attempt_history": attempt_history,
            "prompt_version": "science-svg-editorial-v2",
        }

    async def regenerate_with_feedback(
        self,
        concept_id: str,
        feedback: str,
        previous_version_data: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        concept = CONCEPT_BY_ID.get(concept_id)
        if concept is None:
            raise ValueError(f"Unknown concept id '{concept_id}'.")

        chosen_model = validate_model_id(model or self.client.model)
        active_client = (
            self.client
            if self.client.model == chosen_model
            else GeminiClient(api_key=self.client.api_key, model=chosen_model)
        )

        previous_data = previous_version_data or {}
        prev_svg = previous_data.get("svg", "")
        prev_version = previous_data.get("version", 1)
        prev_failures = [
            f"{name}: {check.get('detail', '')}"
            for name, check in previous_data.get("checks", {}).items()
            if isinstance(check, dict) and not check.get("passed")
        ]
        prev_vq_issues = previous_data.get("visual_quality", {}).get("review_requirements", [])

        started = time.perf_counter()
        input_tokens = 0
        output_tokens = 0
        thinking_tokens = 0
        usage_metadata_available = True
        model_response_count = 0
        api_retries = 0
        validation_retries = 0
        attempt_history: list[dict[str, Any]] = []
        trace_id = str(uuid4())
        timings: dict[str, float] = {
            "prompt_build_ms": 0.0,
            "model_request_with_retries_ms": 0.0,
            "svg_validation_ms": 0.0,
            "concept_structure_ms": 0.0,
            "visual_quality_ms": 0.0,
            "validation_ms": 0.0,
        }
        svg = ""
        last_error: str | None = None
        final_checks: dict[str, dict[str, Any]] = self._empty_checks("Regeneration has not completed.")
        final_vq: VisualQualityReport | None = None
        status = "ERROR"

        async def request(prompt: str) -> ModelResponse:
            request_started = time.perf_counter()
            try:
                outcome = await call_with_transient_retries(lambda: active_client.generate_svg(prompt))
                nonlocal api_retries
                api_retries += outcome.retries
                return outcome.value
            finally:
                timings["model_request_with_retries_ms"] += (time.perf_counter() - request_started) * 1000

        try:
            prompt_started = time.perf_counter()
            first_prompt = build_feedback_regeneration_prompt(
                concept=concept,
                previous_svg=prev_svg,
                user_feedback=feedback,
                failure_reasons=prev_failures,
                visual_quality_issues=prev_vq_issues,
            )
            timings["prompt_build_ms"] += (time.perf_counter() - prompt_started) * 1000
            first_response = await request(first_prompt)
            model_response_count += 1
            input_tokens += first_response.input_tokens
            output_tokens += first_response.output_tokens
            thinking_tokens += getattr(first_response, "thinking_tokens", 0)
            usage_metadata_available = usage_metadata_available and getattr(first_response, "usage_metadata_available", True)
            svg = extract_svg(first_response.text)

            first_report, first_vq = self._validate_full(svg, concept, timings)
            attempt_history.append({
                "attempt": 1,
                "model": chosen_model,
                "checks": first_report.as_dict(),
                "passed": first_report.passed,
                "visual_quality": first_vq.to_dict(),
            })
            final_checks = first_report.as_dict()
            final_vq = first_vq
            status = "PASS" if first_report.passed else "FAIL"

            if not first_report.passed:
                validation_retries = 1
                prompt_started = time.perf_counter()
                repair_prompt = build_feedback_regeneration_prompt(
                    concept=concept,
                    previous_svg=svg,
                    user_feedback=f"{feedback} (Also resolve new validation failures: {', '.join(first_report.failures)})",
                    failure_reasons=first_report.failures,
                )
                timings["prompt_build_ms"] += (time.perf_counter() - prompt_started) * 1000
                try:
                    repaired_response = await request(repair_prompt)
                    model_response_count += 1
                    input_tokens += repaired_response.input_tokens
                    output_tokens += repaired_response.output_tokens
                    thinking_tokens += getattr(repaired_response, "thinking_tokens", 0)
                    usage_metadata_available = usage_metadata_available and getattr(repaired_response, "usage_metadata_available", True)
                    repaired_svg = extract_svg(repaired_response.text)

                    repaired_report, repaired_vq = self._validate_full(repaired_svg, concept, timings)
                    attempt_history.append({
                        "attempt": 2,
                        "model": chosen_model,
                        "checks": repaired_report.as_dict(),
                        "passed": repaired_report.passed,
                        "repair_reasons": first_report.failures,
                        "visual_quality": repaired_vq.to_dict(),
                    })
                    svg = repaired_svg
                    final_checks = repaired_report.as_dict()
                    final_vq = repaired_vq
                    status = "PASS" if repaired_report.passed else "FAIL"
                    if not repaired_report.passed:
                        last_error = "The regenerated SVG still failed validation after the single permitted repair attempt."
                except GeminiAPIError as exc:
                    api_retries += getattr(exc, "retry_count", 0)
                    last_error = f"The corrective generation failed: {exc}"
                    status = "FAIL"
                except MissingAPIKeyError:
                    raise

        except MissingAPIKeyError:
            raise
        except GeminiAPIError as exc:
            api_retries += getattr(exc, "retry_count", 0)
            status_desc = {
                408: "Request Timeout",
                429: "Rate Limit Exceeded",
                503: "High Demand / Service Unavailable",
            }.get(exc.status_code, "Error")
            last_error = f"Gemini API error (HTTP {exc.status_code} {status_desc}): {exc}"
            status = "ERROR"
            final_checks = self._empty_checks("Not run because the Gemini request did not return an SVG.")

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        usage_metadata_available = usage_metadata_available and model_response_count > 0
        cost = self._calculate_cost(input_tokens, output_tokens, chosen_model, usage_metadata_available)
        return {
            "trace_id": trace_id,
            "concept_id": concept["id"],
            "concept": concept["name"],
            "subject": concept["subject"],
            "source_text": concept["source_text"],
            "svg": svg,
            "model": chosen_model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "thinking_tokens": thinking_tokens,
                "metadata_available": usage_metadata_available,
            },
            "cost": cost,
            "retries": {
                "api_retries": api_retries,
                "validation_retries": validation_retries,
                "total_retries": api_retries + validation_retries,
            },
            "checks": final_checks,
            "visual_quality": final_vq.to_dict() if final_vq else None,
            "status": status,
            "review_status": "pending_review",
            "latency_ms": elapsed_ms,
            "timings_ms": {key: round(value, 2) for key, value in timings.items()},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "last_error": last_error,
            "attempt_history": attempt_history,
            "prompt_version": "science-svg-feedback-revision-v1",
            "regeneration_metadata": {
                "from_version": prev_version,
                "feedback": feedback,
                "prompt_type": "feedback_revision",
            },
        }
