"""
Unit tests for the NaN/Infinity-to-None JSON response sanitizer.
"""

import json
import math

from app.utils.json_sanitize import sanitize_json


class TestSanitizeJson:
    def test_nan_becomes_none(self):
        assert sanitize_json(float("nan")) is None

    def test_positive_infinity_becomes_none(self):
        assert sanitize_json(float("inf")) is None

    def test_negative_infinity_becomes_none(self):
        assert sanitize_json(float("-inf")) is None

    def test_normal_float_passes_through(self):
        assert sanitize_json(3.14) == 3.14

    def test_non_float_values_pass_through(self):
        assert sanitize_json("hello") == "hello"
        assert sanitize_json(42) == 42
        assert sanitize_json(True) is True
        assert sanitize_json(None) is None

    def test_nested_dict(self):
        result = sanitize_json({"a": float("nan"), "b": {"c": float("inf"), "d": 1.5}})
        assert result == {"a": None, "b": {"c": None, "d": 1.5}}

    def test_nested_list(self):
        result = sanitize_json([1.0, float("nan"), [float("-inf"), "x"]])
        assert result == [1.0, None, [None, "x"]]

    def test_tuple_becomes_list(self):
        assert sanitize_json((1.0, float("nan"))) == [1.0, None]

    def test_realistic_process_response_is_json_dumpable(self):
        """Mirrors the actual failure: a pandas-derived payload with a NaN
        left over from an all-null column must survive Starlette's
        allow_nan=False JSONResponse rendering."""
        payload = {
            "cleaner": {
                "cleaned_data": [{"id": 1, "processed_at": float("nan")}],
                "report": {"duplicates_removed": 0},
            },
            "hypothesis": {"hypotheses": ["h1"]},
        }
        sanitized = sanitize_json(payload)
        # Would raise ValueError before sanitizing, matching Starlette's renderer
        json.dumps(sanitized, allow_nan=False)
        assert sanitized["cleaner"]["cleaned_data"][0]["processed_at"] is None

    def test_nan_check_does_not_choke_on_bool(self):
        """bool is a subclass of int, not float — make sure isinstance(obj, float)
        doesn't misfire and math.isnan isn't called on a non-float."""
        assert sanitize_json(True) is True
        assert not math.isnan(1.0)  # sanity check the stdlib behaves as expected
