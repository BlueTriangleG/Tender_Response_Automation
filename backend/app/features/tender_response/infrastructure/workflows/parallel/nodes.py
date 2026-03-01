"""Node factories for the parallel tender-response workflow."""

from time import perf_counter

from app.features.tender_response.domain.risk_rules import (
    detect_high_risk_response,
    detect_inconsistent_response,
)
from app.features.tender_response.infrastructure.repositories.qa_alignment_repository import (
    QaAlignmentRepository,
)
from app.features.tender_response.infrastructure.services.answer_generation_service import (
    AnswerGenerationService,
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

_PARTIAL_CONFIDENCE_REASON_MARKERS = (
    "missing",
    "not evidence",
    "not evidenced",
    "not supported",
    "unsupported",
    "not documented",
    "not provided",
    "scope",
    "partial",
    "cannot",
    "can't",
    "does not",
    "do not",
)


def _validate_partial_answer_contract(*, answer: str, review: ReviewPayload) -> str | None:
    """Return a validation error when a partial answer does not explain its gap clearly."""

    if "(" not in answer or ")" not in answer:
        return "Partial answer must identify missing scope in parentheses."
    if review["confidence_level"] not in {"low", "medium"}:
        return "Partial answer confidence must be low or medium."
    confidence_reason = review["confidence_reason"].strip().lower()
    if not confidence_reason:
        return "Partial answer confidence reason must explain missing scope."
    if not any(marker in confidence_reason for marker in _PARTIAL_CONFIDENCE_REASON_MARKERS):
        return "Partial answer confidence reason must identify the missing evidence or scope."
    return None


def _build_failed_generated_answer_result(
    *,
    question,
    alignment,
    assessment,
    domain_tag: str,
    review: ReviewPayload,
    used_reference_ids: set[str],
    error_message: str,
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
        risk=QuestionRisk(level=review["risk_level"], reason=review["risk_reason"]),
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


def make_retrieve_alignment_node(alignment_repository: QaAlignmentRepository):
    """Create the node that retrieves historical QA matches."""

    async def retrieve_alignment(state: QuestionProcessingState) -> dict:
        started_at = perf_counter()
        question_id = state["current_question"].question_id
        debug_log(f"question={question_id} retrieve_alignment start")
        alignment = await alignment_repository.find_best_match(
            state["current_question"],
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
        question_id = state["current_question"].question_id
        debug_log(f"question={question_id} assess_references start")
        assessment = await reference_assessment_service.assess(
            question=state["current_question"],
            references=state["current_alignment"].references,
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
        alignment = state["current_alignment"]
        assessment = state["current_assessment"]
        question_id = state["current_question"].question_id
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
            question=state["current_question"],
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
        question = state["current_question"]
        alignment = state["current_alignment"]
        assessment = state["current_assessment"]
        debug_log(
            f"question={question.question_id} finalize_unanswered "
            f"grounding_status={assessment.grounding_status} refs={len(alignment.references)}"
        )
        domain_tag = primary_domain_tag(
            question=question,
            alignment=alignment,
            domain_tagging_service=domain_tagging_service,
        )

        result = TenderQuestionResponse(
            question_id=question.question_id,
            original_question=question.original_question,
            generated_answer=None,
            domain_tag=domain_tag,
            confidence_level=None,
            confidence_reason=None,
            historical_alignment_indicator=alignment.matched,
            status="unanswered",
            grounding_status=assessment.grounding_status,
            flags=QuestionFlags(high_risk=False, inconsistent_response=False),
            risk=QuestionRisk(level="low", reason="No grounded answer was produced."),
            metadata=QuestionMetadata(
                source_row_index=question.source_row_index,
                alignment_record_id=alignment.record_id,
                alignment_score=alignment.alignment_score,
            ),
            references=build_reference_payload(alignment.references),
            error_message=None,
            extensions={"reference_assessment_reason": assessment.reason},
        )
        return {"current_result": result}

    return finalize_unanswered


def make_assess_output_node(domain_tagging_service: DomainTaggingService):
    """Create the node that validates and materializes grounded answers."""

    def assess_output(state: QuestionProcessingState) -> dict:
        started_at = perf_counter()
        question = state["current_question"]
        alignment = state["current_alignment"]
        assessment = state["current_assessment"]
        review: ReviewPayload = state["current_review"]  # type: ignore[assignment]
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
            confidence_level=review["confidence_level"],
            confidence_reason=review["confidence_reason"],
            historical_alignment_indicator=alignment.matched,
            status="completed",
            grounding_status=assessment.grounding_status,
            flags=QuestionFlags(
                high_risk=review["risk_level"] == "high" or high_risk,
                inconsistent_response=review["inconsistent_response"] or inconsistent_response,
            ),
            risk=QuestionRisk(level=review["risk_level"], reason=review["risk_reason"]),
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
        question = state["current_question"]
        alignment = state["current_alignment"]
        assessment = state["current_assessment"]
        review: ReviewPayload = state["current_review"] or {  # type: ignore[assignment]
            "confidence_level": "low",
            "confidence_reason": "",
            "risk_level": "low",
            "risk_reason": "No risk review was returned.",
            "inconsistent_response": False,
        }
        domain_tag = domain_tagging_service.tag(
            question=question,
            generated_answer=(state.get("current_answer") or ""),
            alignment=alignment,
        )
        error_message = (
            state.get("generation_validation_error")
            or "Generated answer failed output validation."
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
            )
        }

    return fail_generation


def make_process_question_node(question_graph):
    """Create the batch-level node that invokes the single-question subgraph."""

    async def process_question(state: BatchTenderResponseState) -> dict:
        question = state["current_question"]
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


def summarize_batch(state: BatchTenderResponseState) -> dict:
    """Roll up per-question results into a batch summary for the API response."""

    question_results = state.get("question_results", [])
    total_questions = len(question_results)
    failed_questions = sum(item.status == "failed" for item in question_results)
    unanswered_questions = sum(item.status == "unanswered" for item in question_results)
    completed_questions = sum(item.status == "completed" for item in question_results)
    flagged_questions = sum(
        item.flags.high_risk or item.flags.inconsistent_response for item in question_results
    )

    if total_questions == 0:
        overall_status = "completed"
    elif failed_questions == total_questions:
        overall_status = "failed"
    elif failed_questions > 0:
        overall_status = "partial_failure"
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
        )
    }
