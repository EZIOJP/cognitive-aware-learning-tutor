import pytest

from backend.transcripts.library import (
    build_relative_path,
    normalize_folder_path,
    normalize_filename,
)


def test_normalize_folder_path():
    assert normalize_folder_path("Scaler/Lectures") == "Scaler/Lectures"
    assert normalize_folder_path("../bad") == "bad"
    assert normalize_folder_path("") == ""


def test_build_relative_path():
    assert build_relative_path("scaler/lectures", "Intro.md") == "scaler/lectures/Intro.md"
    assert build_relative_path("", "Intro.md") == "Intro.md"


def test_normalize_filename_requires_md():
    assert normalize_filename("My Note").endswith(".md")
