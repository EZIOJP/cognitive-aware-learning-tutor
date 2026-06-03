"""Test defaults — avoid heavy word seed during API tests."""

import os

os.environ.setdefault("SEED_WORDS_ON_STARTUP", "false")
os.environ.setdefault("DEV_MODE", "true")
