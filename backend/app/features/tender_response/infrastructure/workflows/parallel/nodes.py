"""Node factories for the parallel tender-response workflow."""

import asyncio
from time import perf_counter
from typing import Literal, cast

from app.core.config import settings
from app.features.tender_response.domain.models import (
    HistoricalAlignmentResult,
    ReferenceAssessmentResult,
    TenderQuestion,
)
from app.features.tender_response.domain.risk_rules import (
    detect_high_risk_response,
    detect_inconsistent_response,
    find_generation_validation_error,
)
from app.features.tender_response.infrastructure.services.answer_generation_service import (
    AnswerGenerationService,
)
from app.features.tender_response.infrastructure.services.conflict_review_service import (
    ConflictReviewer,
)
from app.features.tender_response.infrastructure.services.domain_tagging_service import (
    DomainTaggingService,
)
from app.features.tender_response.infrastructure.services.reference_assessment_service import (
    ReferenceAssessmentService,
)
from app.features.tender_response.infrastructure.workflows.common.builders import (
    build_reference_payload,
    failed_question_result,
    primary_domain_tag,
)
from app.features.tender_response.infrastructure.workflows.common.debug import debug_log
from app.features.tender_response.infrastructure.workflows.common.state import (
    BatchTenderResponseState,
    QuestionProcessingState,
    ReviewPayload,
)
from app.features.tender_response.schemas.responses import (
    QuestionFlags,
    QuestionMetadata,
    QuestionRisk,
    TenderQuestionResponse,
    TenderResponseSummary,
)

RiskLevel = Literal["high", "medium", "low"]
GroundingStatus = Literal[
    "grounded",
    "partial_reference",
    "conflict",
    "insufficient_reference",
    "no_reference",
    "failed",
]
OverallCompletionStatus = Literal[
    "completed",
    "completed_with_flags",
    "conflict",
    "unanswered",
    "partial_failure",
    "failed",
]


def _require_question(state: QuestionProcessingState | BatchTenderResponseState) -> TenderQuestion:
    question = state.get("current_question")
    if question is None:
        raise RuntimeError("Question state was missing current_question.")
    return question


def _require_alignment(state: QuestionProcessingState) -> HistoricalAlignmentResult:
    alignment = state.get("current_alignment")
    if alignment is None:
        raise RuntimeError("Question state was missing current_alignment.")
    return alignment


def _require_assessment(state: QuestionProcessingState) -> ReferenceAssessmentResult:
    assessment = state.get("current_assessment")
    if assessment is None:
        raise RuntimeError("Question state was missing current_assessment.")
    return assessment


def _review_with_defaults(state: QuestionProcessingState) -> ReviewPayload:
    return cast(
        ReviewPayload,
        state.get("current_review")
        or {
            "confidence_level": "low",
            "confidence_reason": "",
            "risk_level": "low",
            "risk_reason": "No risk review was returned.",
            "inconsistent_response": False,
        },
    )


def _completed_results_with_answers(
    results: list[TenderQuestionResponse],
) -> list[TenderQuestionResponse]:
    return [
        result
        for result in results
        if result.status == "completed" and (result.generated_answer or "").strip()
    ]


def _merged_session_completed_results(
    *,
    previous_results: list[TenderQuestionResponse],
    current_results: list[TenderQuestionResponse],
) -> list[TenderQuestionResponse]:
    merged_by_id: dict[str, TenderQuestionResponse] = {
        result.question_id: result for result in _completed_results_with_answers(previous_results)
    }
    for result in _completed_results_with_answers(current_results):
        merged_by_id[result.question_id] = result
    return list(merged_by_id.values())


def _validate_partial_answer_contract(*, answer: str, review: ReviewPayload) -> str | None:
    """Return a validation error when a partial answer omits its missing-scope disclosure."""

    if "(" not in answer or ")" not in answer:
        return "Partial answer must identify missing scope in parentheses."
    return None


def _confidence_from_supported_coverage(
    *,
    assessment: ReferenceAssessmentResult,
    current_confidence_level: str,
) -> str:
    """Map supported coverage to the final confidence bucket.

    Coverage policy:
    - 100% => high
    - 50-99% => medium
    - 0-49% => low

    Fallback for tests/legacy callers with no coverage estimate:
    keep the current confidence level except cap partial answers at medium.
    """

    coverage = assessment.supported_coverage_percent
    if coverage is None:
        if (
            assessment.grounding_status == "partial_reference"
            and current_confidence_level == "high"
        ):
            return "medium"
        return current_confidence_level
    if coverage >= 100:
        return "high"
    if coverage >= 50:
        return "medium"
    return "low"


def _build_failed_generated_answer_result(
    *,
    question,
    alignment,
    assessment,
    domain_tag: str,
    review: ReviewPayload,
    used_reference_ids: set[str],
    error_message: str,
    generation_attempt_count: int,
    generation_retry_history: list[str],
    last_invalid_answer: str | None,
    last_invalid_confidence_level: str | None,
    last_invalid_confidence_reason: str | None,
) -> TenderQuestionResponse:
    """Return a failed result for generated outputs that cannot be safely displayed."""

    return TenderQuestionResponse(
        question_id=question.question_id,
        original_question=question.original_question,
        generated_answer=None,
        domain_tag=domain_tag,
        confidence_level="low",
        confidence_reason="Generated answer failed output validation.",
        historical_alignment_indicator=alignment.matched,
        status="failed",
        grounding_status="failed",
        flags=QuestionFlags(
            high_risk=review["risk_level"] == "high",
            inconsistent_response=review["inconsistent_response"],
        ),
        risk=QuestionRisk(
            level=cast(RiskLevel, review["risk_level"]),
            reason=review["risk_reason"],
        ),
        metadata=QuestionMetadata(
            source_row_index=question.source_row_index,
            alignment_record_id=alignment.record_id,
            alignment_score=alignment.alignment_score,
        ),
        references=build_reference_payload(
            alignment.references,
            used_reference_ids=used_reference_ids,
        ),
        error_message=error_message,
        extensions={
            "reference_assessment_reason": assessment.reason,
            "confidence_review_reason": review["confidence_reason"],
            "generation_attempt_count": generation_attempt_count,
            "generation_retry_history": generation_retry_history,
            "last_invalid_answer": last_invalid_answer,
            "last_invalid_confidence_level": last_invalid_confidence_level,
            "last_invalid_confidence_reason": last_invalid_confidence_reason,
        },
    )


def _set_retry_feedback(
    *,
    state: QuestionProcessingState,
    error_message: str,
) -> dict:
    """Persist compact retry memory for a recoverable generation validation error."""

    review = state["current_review"] or {
        "confidence_level": "",
        "confidence_reason": "",
        "risk_level": "low",
        "risk_reason": "",
        "inconsistent_response": False,
    }
    retry_history = list(state.get("generation_retry_history", []))
    retry_history.append(error_message)
    return {
        "generation_validation_error": error_message,
        "generation_retry_history": retry_history,
        "last_invalid_answer": (state.get("current_answer") or "").strip() or None,
        "last_invalid_confidence_level": review["confidence_level"] or None,
        "last_invalid_confidence_reason": review["confidence_reason"] or None,
        "current_result": None,
    }


def make_retrieve_alignment_node(alignment_repository):
    """Create the node that retrieves historical evidence for one question."""

    async def retrieve_alignment(state: QuestionProcessingState) -> dict:
        started_at = perf_counter()
        question = _require_question(state)
        question_id = question.question_id
        debug_log(f"question={question_id} retrieve_alignment start")
        if hasattr(alignment_repository, "find_historical_evidence"):
            alignment = await alignment_repository.find_historical_evidence(
                question,
                threshold=state["alignment_threshold"],
            )
        else:
            alignment = await alignment_repository.find_best_match(
                question,
                threshold=state["alignment_threshold"],
            )
        duration_ms = (perf_counter() - started_at) * 1000
        debug_log(
            f"question={question_id} retrieve_alignment end "
            f"matched={alignment.matched} refs={len(alignment.references)} "
            f"duration_ms={duration_ms:.2f}"
        )
        return {"current_alignment": alignment}

    return retrieve_alignment


def make_assess_references_node(reference_assessment_service: ReferenceAssessmentService):
    """Create the node that decides whether references are sufficient."""

    async def assess_references(state: QuestionProcessingState) -> dict:
        started_at = perf_counter()
        question = _require_question(state)
        question_id = question.question_id
        debug_log(f"question={question_id} assess_references start")
        assessment = await reference_assessment_service.assess(
            question=question,
            references=_require_alignment(state).references,
        )
        duration_ms = (perf_counter() - started_at) * 1000
        debug_log(
            f"question={question_id} assess_references end "
            f"grounding_status={assessment.grounding_status} "
            f"usable_refs={len(assessment.usable_reference_ids)} "
            f"duration_ms={duration_ms:.2f}"
        )
        return {"current_assessment": assessment}

    return assess_references


def make_generate_answer_node(answer_generation_service: AnswerGenerationService):
    """Create the node that generates a grounded answer and review metadata."""

    async def generate_answer(state: QuestionProcessingState) -> dict:
        started_at = perf_counter()
        question = _require_question(state)
        alignment = _require_alignment(state)
        assessment = _require_assessment(state)
        question_id = question.question_id
        debug_log(
            f"question={question_id} generate_answer start "
            f"usable_refs={len(assessment.usable_reference_ids)}"
        )
        usable_reference_ids = set(assessment.usable_reference_ids)
        usable_references = [
            reference
            for reference in alignment.references
            if reference.record_id in usable_reference_ids
        ]
        grounded_result = await answer_generation_service.generate_grounded_response(
            question=question,
            usable_references=usable_references,
            attempt_number=state.get("generation_attempt_count", 0) + 1,
            validation_error=state.get("generation_validation_error"),
            last_invalid_answer=state.get("last_invalid_answer"),
            last_invalid_confidence_level=state.get("last_invalid_confidence_level"),
            last_invalid_confidence_reason=state.get("last_invalid_confidence_reason"),
            assessment_reason=assessment.reason,
        )
        duration_ms = (perf_counter() - started_at) * 1000
        debug_log(
            f"question={question_id} generate_answer end "
            f"confidence={grounded_result.confidence_level} "
            f"risk={grounded_result.risk_level} duration_ms={duration_ms:.2f}"
        )
        review: ReviewPayload = {
            "confidence_level": grounded_result.confidence_level,
            "confidence_reason": grounded_result.confidence_reason,
            "risk_level": grounded_result.risk_level,
            "risk_reason": grounded_result.risk_reason,
            "inconsistent_response": grounded_result.inconsistent_response,
        }
        return {
            "current_grounded_result": grounded_result,
            "current_answer": grounded_result.generated_answer,
            "current_review": review,
            "generation_attempt_count": state.get("generation_attempt_count", 0) + 1,
        }

    return generate_answer


def make_finalize_unanswered_node(domain_tagging_service: DomainTaggingService):
    """Create the node that returns unanswered results."""

    def finalize_unanswered(state: QuestionProcessingState) -> dict:
        question = _require_question(state)
        alignment = _require_alignment(state)
        assessment = _require_assessment(state)
        debug_log(
            f"question={question.question_id} finalize_unanswered "
            f"grounding_status={assessment.grounding_status} refs={len(alignment.references)}"
        )
        domain_tag = primary_domain_tag(
            question=question,
            alignment=alignment,
            domain_tagging_service=domain_tagging_service,
        )
        assessment_reason = assessment.reason.strip()
        has_conflict = assessment.grounding_status == "conflict"
        requires_human_review = (
            "human review" in assessment_reason.lower()
            or "conflicting historical references" in assessment_reason.lower()
            or has_conflict
        )
        risk_level = "medium" if requires_human_review else "low"
        risk_reason = (
            "Conflicting historical references require human review before answering."
            if has_conflict
            else "No grounded answer was produced."
        )
        error_message = assessment_reason if requires_human_review else None

        result = TenderQuestionResponse(
            question_id=question.question_id,
            original_question=question.original_question,
            generated_answer=None,
            domain_tag=domain_tag,
            confidence_level=None,
            confidence_reason=None,
            historical_alignment_indicator=alignment.matched,
            status="unanswered",
            grounding_status=cast(GroundingStatus, assessment.grounding_status),
            flags=QuestionFlags(
                high_risk=False,
                inconsistent_response=False,
                has_conflict=has_conflict,
            ),
            risk=QuestionRisk(level=cast(RiskLevel, risk_level), reason=risk_reason),
            metadata=QuestionMetadata(
                source_row_index=question.source_row_index,
                alignment_record_id=alignment.record_id,
                alignment_score=alignment.alignment_score,
            ),
            references=build_reference_payload(alignment.references),
            error_message=error_message,
            extensions={
                "reference_assessment_reason": assessment.reason,
                "requires_human_review": requires_human_review,
                "conflicts": [],
            },
        )
        return {"current_result": result}

    return finalize_unanswered


def make_assess_output_node(domain_tagging_service: DomainTaggingService):
    """Create the node that validates and materializes grounded answers."""

    def assess_output(state: QuestionProcessingState) -> dict:
        started_at = perf_counter()
        question = _require_question(state)
        alignment = _require_alignment(state)
        assessment = _require_assessment(state)
        review = _review_with_defaults(state)
        answer = (state["current_answer"] or "").strip()
        debug_log(f"question={question.question_id} assess_output start")
        usable_reference_ids = set(assessment.usable_reference_ids)
        used_references = [
            reference
            for reference in alignment.references
            if reference.record_id in usable_reference_ids
        ]
        primary_reference_answer = used_references[0].answer if used_references else None

        high_risk = detect_high_risk_response(
            question=question.original_question,
            generated_answer=answer,
            historical_alignment_answer=primary_reference_answer,
        )
        inconsistent_response = detect_inconsistent_response(
            generated_answer=answer,
            historical_alignment_answer=primary_reference_answer,
        )
        domain_tag = domain_tagging_service.tag(
            question=question,
            generated_answer=answer,
            alignment=alignment,
        )

        if not answer:
            duration_ms = (perf_counter() - started_at) * 1000
            debug_log(
                f"question={question.question_id} assess_output retry_empty_answer "
                f"duration_ms={duration_ms:.2f}"
            )
            return _set_retry_feedback(
                state=state,
                error_message="Generated answer was empty after output validation.",
            )

        if assessment.grounding_status == "partial_reference":
            partial_validation_error = _validate_partial_answer_contract(
                answer=answer,
                review=review,
            )
            if partial_validation_error is not None:
                duration_ms = (perf_counter() - started_at) * 1000
                debug_log(
                    f"question={question.question_id} assess_output retry_partial_contract "
                    f"duration_ms={duration_ms:.2f}"
                )
                return _set_retry_feedback(
                    state=state,
                    error_message=partial_validation_error,
                )
        review = {
            **review,
            "confidence_level": _confidence_from_supported_coverage(
                assessment=assessment,
                current_confidence_level=review["confidence_level"],
            ),
        }

        generation_validation_error = find_generation_validation_error(
            question=question.original_question,
            generated_answer=answer,
            historical_alignment_answer=primary_reference_answer,
        )
        if generation_validation_error is not None:
            duration_ms = (perf_counter() - started_at) * 1000
            debug_log(
                f"question={question.question_id} assess_output retry_claim_validation "
                f"duration_ms={duration_ms:.2f}"
            )
            return _set_retry_feedback(
                state=state,
                error_message=generation_validation_error,
            )

        duration_ms = (perf_counter() - started_at) * 1000
        debug_log(
            f"question={question.question_id} assess_output completed "
            f"confidence={review['confidence_level']} duration_ms={duration_ms:.2f}"
        )
        result = TenderQuestionResponse(
            question_id=question.question_id,
            original_question=question.original_question,
            generated_answer=answer,
            domain_tag=domain_tag,
            confidence_level=cast(RiskLevel, review["confidence_level"]),
            confidence_reason=review["confidence_reason"],
            historical_alignment_indicator=alignment.matched,
            status="completed",
            grounding_status=cast(GroundingStatus, assessment.grounding_status),
            flags=QuestionFlags(
                high_risk=review["risk_level"] == "high" or high_risk,
                inconsistent_response=review["inconsistent_response"] or inconsistent_response,
            ),
            risk=QuestionRisk(
                level=cast(RiskLevel, review["risk_level"]),
                reason=review["risk_reason"],
            ),
            metadata=QuestionMetadata(
                source_row_index=question.source_row_index,
                alignment_record_id=alignment.record_id,
                alignment_score=alignment.alignment_score,
            ),
            references=build_reference_payload(
                alignment.references,
                used_reference_ids=usable_reference_ids,
            ),
            error_message=None,
            extensions={
                "reference_assessment_reason": assessment.reason,
                "confidence_review_reason": review["confidence_reason"],
            },
        )
        return {"current_result": result}

    return assess_output


def make_fail_generation_node(domain_tagging_service: DomainTaggingService):
    """Create the node that materializes a failed result after retry exhaustion."""

    def fail_generation(state: QuestionProcessingState) -> dict:
        question = _require_question(state)
        alignment = _require_alignment(state)
        assessment = _require_assessment(state)
        review = _review_with_defaults(state)
        domain_tag = domain_tagging_service.tag(
            question=question,
            generated_answer=(state.get("current_answer") or ""),
            alignment=alignment,
        )
        error_message = (
            state.get("generation_validation_error") or "Generated answer failed output validation."
        )
        used_reference_ids = set(assessment.usable_reference_ids)
        return {
            "current_result": _build_failed_generated_answer_result(
                question=question,
                alignment=alignment,
                assessment=assessment,
                domain_tag=domain_tag,
                review=review,
                used_reference_ids=used_reference_ids,
                error_message=error_message,
                generation_attempt_count=state.get("generation_attempt_count", 0),
                generation_retry_history=list(state.get("generation_retry_history", [])),
                last_invalid_answer=state.get("last_invalid_answer"),
                last_invalid_confidence_level=state.get("last_invalid_confidence_level"),
                last_invalid_confidence_reason=state.get("last_invalid_confidence_reason"),
            )
        }

    return fail_generation


def make_process_question_node(question_graph):
    """Create the batch-level node that invokes the single-question subgraph."""

    async def process_question(state: BatchTenderResponseState) -> dict:
        question = _require_question(state)
        started_at = perf_counter()
        debug_log(f"question={question.question_id} process_question start")
        try:
            result = await question_graph.ainvoke(
                {
                    "current_question": question,
                    "alignment_threshold": state["alignment_threshold"],
                    "current_alignment": None,
                    "current_assessment": None,
                    "current_review": None,
                    "current_grounded_result": None,
                    "current_answer": None,
                    "generation_attempt_count": 0,
                    "generation_validation_error": None,
                    "generation_retry_history": [],
                    "last_invalid_answer": None,
                    "last_invalid_confidence_level": None,
                    "last_invalid_confidence_reason": None,
                    "current_result": None,
                }
            )
            duration_ms = (perf_counter() - started_at) * 1000
            debug_log(
                f"question={question.question_id} process_question end "
                f"status={result['current_result'].status} duration_ms={duration_ms:.2f}"
            )
            return {"question_results": [result["current_result"]]}
        except Exception as exc:
            duration_ms = (perf_counter() - started_at) * 1000
            debug_log(
                f"question={question.question_id} process_question failed "
                f"duration_ms={duration_ms:.2f} error={exc}"
            )
            return {
                "question_results": [failed_question_result(question, str(exc))],
                "run_errors": [f"{question.question_id}: {exc}"],
            }

    return process_question


def prepare_conflict_review(state: BatchTenderResponseState) -> dict:
    """Batch barrier before dispatching parallel conflict review jobs."""

    current_completed = _completed_results_with_answers(state.get("question_results", []))
    session_completed = _completed_results_with_answers(state.get("session_completed_results", []))
    debug_log(
        "prepare_conflict_review "
        f"current_results={len(state.get('question_results', []))} "
        f"current_completed={len(current_completed)} "
        f"session_memory={len(state.get('session_completed_results', []))} "
        f"session_completed={len(session_completed)}"
    )
    return {}


def make_review_conflict_group_node(conflict_review_service: ConflictReviewer):
    """Create the node that reviews one group of up to ten target answers."""

    async def review_conflict_group(state: BatchTenderResponseState) -> dict:
        job = state["current_conflict_job"] or {"target_question_ids": []}
        current_by_id = {item.question_id: item for item in state["question_results"]}
        target_results = [
            current_by_id[question_id]
            for question_id in job["target_question_ids"]
            if question_id in current_by_id
            and current_by_id[question_id].status == "completed"
            and (current_by_id[question_id].generated_answer or "").strip()
        ]
        reference_results = _merged_session_completed_results(
            previous_results=state.get("session_completed_results", []),
            current_results=state.get("question_results", []),
        )
        debug_log(
            "conflict_review start "
            f"targets={len(target_results)} "
            f"target_ids={[item.question_id for item in target_results]} "
            f"references={len(reference_results)}"
        )
        if not target_results or len(reference_results) < 2:
            debug_log("conflict_review skip insufficient candidates")
            return {"conflict_findings": []}

        try:
            findings = await asyncio.wait_for(
                conflict_review_service.review_conflicts(
                    target_results=target_results,
                    reference_results=reference_results,
                ),
                timeout=settings.tender_conflict_review_timeout_seconds,
            )
        except TimeoutError:
            debug_log("conflict_review failed error=timed out")
            return {
                "conflict_findings": [],
                "conflict_review_errors": ["Session conflict review timed out and was skipped."],
            }
        except Exception as exc:
            debug_log(f"conflict_review failed error={exc}")
            return {
                "conflict_findings": [],
                "conflict_review_errors": [str(exc)],
            }

        debug_log(f"conflict_review end findings={len(findings)}")
        return {"conflict_findings": findings}

    return review_conflict_group


def apply_conflicts(state: BatchTenderResponseState) -> dict:
    """Project validated conflict findings onto current question results and session memory."""

    current_results = list(state.get("question_results", []))
    session_results = list(state.get("session_completed_results", []))
    all_reference_results = _merged_session_completed_results(
        previous_results=session_results,
        current_results=current_results,
    )
    reference_by_id = {item.question_id: item for item in all_reference_results}
    conflict_map: dict[str, list[dict[str, str]]] = {}

    for finding in state.get("conflict_findings", []):
        target_question_id = finding.get("target_question_id")
        conflicting_question_id = finding.get("conflicting_question_id")
        reason = (finding.get("reason") or "").strip()
        severity = (finding.get("severity") or "").strip().lower()
        if (
            not target_question_id
            or not conflicting_question_id
            or not reason
            or severity not in {"high", "medium", "low"}
            or target_question_id == conflicting_question_id
        ):
            continue
        if (
            target_question_id not in reference_by_id
            or conflicting_question_id not in reference_by_id
        ):
            continue

        conflicting_result = reference_by_id[conflicting_question_id]
        conflict_entry = {
            "conflicting_question_id": conflicting_question_id,
            "conflicting_question": conflicting_result.original_question,
            "reason": reason,
            "severity": severity,
        }
        conflict_map.setdefault(target_question_id, [])
        if conflict_entry not in conflict_map[target_question_id]:
            conflict_map[target_question_id].append(conflict_entry)

        if conflicting_question_id in {item.question_id for item in current_results}:
            reciprocal_result = reference_by_id[target_question_id]
            reciprocal_entry = {
                "conflicting_question_id": target_question_id,
                "conflicting_question": reciprocal_result.original_question,
                "reason": reason,
                "severity": severity,
            }
            conflict_map.setdefault(conflicting_question_id, [])
            if reciprocal_entry not in conflict_map[conflicting_question_id]:
                conflict_map[conflicting_question_id].append(reciprocal_entry)

    updated_results: list[TenderQuestionResponse] = []
    for result in current_results:
        conflicts = conflict_map.get(result.question_id, [])
        existing_conflicts = list(result.extensions.get("conflicts", []))
        merged_conflicts = existing_conflicts + [
            item for item in conflicts if item not in existing_conflicts
        ]
        updated_results.append(
            result.model_copy(
                update={
                    "flags": result.flags.model_copy(
                        update={"has_conflict": result.flags.has_conflict or bool(merged_conflicts)}
                    ),
                    "extensions": {
                        **result.extensions,
                        "conflicts": merged_conflicts,
                    },
                }
            )
        )

    updated_session_results = _merged_session_completed_results(
        previous_results=session_results,
        current_results=updated_results,
    )
    debug_log(
        "apply_conflicts "
        f"validated_findings={len(state.get('conflict_findings', []))} "
        f"conflicted_questions="
        f"{sum(bool(conflict_map.get(item.question_id)) for item in updated_results)} "
        f"session_completed={len(updated_session_results)}"
    )
    return {
        "question_results": updated_results,
        "session_completed_results": updated_session_results,
    }


def summarize_batch(state: BatchTenderResponseState) -> dict:
    """Roll up per-question results into a batch summary for the API response."""

    question_results = state.get("question_results", [])
    total_questions = len(question_results)
    failed_questions = sum(item.status == "failed" for item in question_results)
    unanswered_questions = sum(item.status == "unanswered" for item in question_results)
    completed_questions = sum(item.status == "completed" for item in question_results)
    conflict_count = sum(item.flags.has_conflict for item in question_results)
    flagged_questions = sum(
        item.flags.high_risk or item.flags.inconsistent_response for item in question_results
    )

    if total_questions == 0:
            overall_status: OverallCompletionStatus = "completed"
    elif failed_questions == total_questions:
        overall_status = "failed"
    elif failed_questions > 0:
        overall_status = "partial_failure"
    elif conflict_count > 0:
        overall_status = "conflict"
    elif unanswered_questions == total_questions:
        overall_status = "unanswered"
    elif flagged_questions > 0:
        overall_status = "completed_with_flags"
    else:
        overall_status = "completed"

    return {
        "summary": TenderResponseSummary(
            total_questions_processed=total_questions,
            flagged_high_risk_or_inconsistent_responses=flagged_questions,
            overall_completion_status=overall_status,
            completed_questions=completed_questions,
            unanswered_questions=unanswered_questions,
            failed_questions=failed_questions,
            conflict_count=conflict_count,
        )
    }
