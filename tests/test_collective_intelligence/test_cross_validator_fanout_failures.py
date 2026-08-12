import asyncio
from unittest.mock import AsyncMock

import pytest

from src.openrouter_mcp.collective_intelligence.base import ProcessingResult
from src.openrouter_mcp.collective_intelligence.cross_validator import CrossValidator


class FatalValidatorSignal(BaseException):
    pass


@pytest.mark.asyncio
@pytest.mark.unit
async def test_peer_review_propagates_fatal_signal_after_sibling_completion(
    mock_model_provider,
    sample_task,
    sample_processing_results,
):
    validator = CrossValidator(mock_model_provider)
    fatal_signal = FatalValidatorSignal("fatal validator state")
    fatal_started = asyncio.Event()
    sibling_started = asyncio.Event()
    release_sibling = asyncio.Event()

    async def execute(validator_model_id, validation_task):
        if validator_model_id == "fatal-validator":
            fatal_started.set()
            raise fatal_signal

        sibling_started.set()
        await release_sibling.wait()
        return ProcessingResult(
            task_id=validation_task.task_id,
            model_id=validator_model_id,
            content="No errors found",
            confidence=0.9,
        )

    validator._execute_validation_task = AsyncMock(side_effect=execute)
    review_task = asyncio.create_task(
        validator._peer_review_validation(
            sample_processing_results[0],
            sample_task,
            ["fatal-validator", "sibling-validator"],
        )
    )

    await fatal_started.wait()
    await sibling_started.wait()
    await asyncio.sleep(0)
    assert not review_task.done()

    release_sibling.set()
    with pytest.raises(FatalValidatorSignal) as raised:
        await review_task

    assert raised.value is fatal_signal
    assert validator._execute_validation_task.await_count == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_peer_review_keeps_child_cancellation_in_failure_metadata(
    mock_model_provider,
    sample_task,
    sample_processing_results,
):
    validator = CrossValidator(mock_model_provider)

    async def execute(validator_model_id, validation_task):
        if validator_model_id == "cancelled-validator":
            raise asyncio.CancelledError("validator stopped")
        return ProcessingResult(
            task_id=validation_task.task_id,
            model_id=validator_model_id,
            content="No errors found",
            confidence=0.9,
        )

    validator._execute_validation_task = AsyncMock(side_effect=execute)

    report = await validator._peer_review_validation(
        sample_processing_results[0],
        sample_task,
        ["cancelled-validator", "sibling-validator"],
    )

    assert report.issues == []
    assert report.metadata["validator_failures"] == [
        {
            "validator_model_id": "cancelled-validator",
            "criteria": "accuracy",
            "error": "",
        }
    ]
