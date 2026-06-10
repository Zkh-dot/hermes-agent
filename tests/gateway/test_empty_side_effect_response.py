"""Tests for intentional empty gateway responses after terminal side effects."""

from gateway.run import _normalize_empty_agent_response


def test_normalize_empty_response_preserves_side_effect_only_completion():
    result = {
        "final_response": "",
        "api_calls": 1,
        "completed": True,
        "side_effect_only_response": True,
    }

    assert _normalize_empty_agent_response(result, "", history_len=0) == ""


def test_normalize_empty_response_still_warns_for_unmarked_empty_completion():
    result = {
        "final_response": "",
        "api_calls": 1,
        "completed": True,
    }

    response = _normalize_empty_agent_response(result, "", history_len=0)

    assert "no response was generated" in response
