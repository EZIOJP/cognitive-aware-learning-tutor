"""Test defaults — avoid heavy word seed during API tests."""

import os

import pytest

os.environ.setdefault("SEED_WORDS_ON_STARTUP", "false")
os.environ.setdefault("DEV_MODE", "true")
# Run Huey tasks inline so test-all-profiles jobs complete without a worker.
os.environ.setdefault("HUEY_IMMEDIATE", "1")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: optional marker (corpus registry package removed)",
    )
