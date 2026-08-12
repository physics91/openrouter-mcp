import asyncio

import pytest

from src.openrouter_mcp.utils.async_utils import raise_first_fatal_result


class FatalFanoutSignal(BaseException):
    pass


@pytest.mark.unit
def test_raise_first_fatal_result_ignores_isolated_failures():
    raise_first_fatal_result(
        [
            "success",
            RuntimeError("ordinary failure"),
            asyncio.CancelledError("child stopped"),
            None,
        ]
    )


@pytest.mark.unit
def test_raise_first_fatal_result_preserves_order_and_identity():
    first_fatal = FatalFanoutSignal("first")
    second_fatal = FatalFanoutSignal("second")

    with pytest.raises(FatalFanoutSignal) as raised:
        raise_first_fatal_result(
            [RuntimeError("ordinary failure"), first_fatal, second_fatal]
        )

    assert raised.value is first_fatal
