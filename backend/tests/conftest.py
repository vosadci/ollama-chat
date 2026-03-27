import os
import sys
from pathlib import Path

import pytest

# Make sure the backend package root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from middleware.rate_limit import _COUNTS as _rate_counts


@pytest.fixture(autouse=True)
def _clear_rate_limit_state():
    """Reset the in-process rate-limiter counters before every test.

    Without this, tests that exercise the chat endpoint share a global
    counter and can trip the 10-req/min limit when the test suite runs
    sequentially from the same fake IP.
    """
    _rate_counts.clear()
    yield
    _rate_counts.clear()


def pytest_configure(config):
    """Register the 'integration' custom marker."""
    config.addinivalue_line(
        "markers",
        "integration: live tests that require a running Ollama instance",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when OLLAMA_URL is not set.

    Tests marked with @pytest.mark.integration are skipped unless the
    ``OLLAMA_URL`` environment variable is explicitly set, so CI always
    passes without a running Ollama instance.
    """
    if os.getenv("OLLAMA_URL"):
        return  # env var present — run everything

    skip_marker = pytest.mark.skip(
        reason=(
            "integration tests skipped: set OLLAMA_URL to run against "
            "a live Ollama instance"
        )
    )
    for item in items:
        if item.get_closest_marker("integration"):
            item.add_marker(skip_marker)
