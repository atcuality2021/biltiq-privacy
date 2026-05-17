"""Tests for my_module — pytest scaffold.

Each test asserts ONE thing and ties to a spec.md acceptance criterion.
Replace MyService, my_module, and placeholder values with real names.
"""

import pytest
from my_module import MyService  # replace with the actual import


class TestMyServiceDoSomething:
    """Unit tests for MyService.do_something()."""

    def test_returns_expected_value_for_valid_input(self) -> None:
        """Happy path: valid input returns the expected result."""
        svc = MyService()
        result = svc.do_something("valid_input")
        assert result == "expected_output"

    def test_raises_value_error_for_empty_input(self) -> None:
        """Failure path: empty input raises ValueError."""
        svc = MyService()
        with pytest.raises(ValueError, match="input must not be empty"):
            svc.do_something("")

    def test_private_helper_not_called_for_cached_result(
        self, mocker: "pytest_mock.MockerFixture"  # type: ignore[name-defined]  # requires pytest-mock
    ) -> None:
        """Mocking example: at most 50% of deps mocked per test."""
        svc = MyService()
        mocker.patch.object(svc, "_expensive_call", return_value="cached")
        result = svc.do_something("cached_key")
        assert result == "cached"
