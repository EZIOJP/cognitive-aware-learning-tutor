from backend.quiz.learn_folders import (
    enrich_tag_folder,
    folder_for_tag,
    folder_from_note_path,
)


def test_folder_from_paths():
    assert folder_from_note_path("math-core/MT1_aptitude_interview_notes.md") == "math-core"
    assert folder_from_note_path("numpy/L02_numpy_operations_notes.md") == "numpy"
    assert folder_from_note_path("pandas/L05_pandas_operations_notes.md") == "pandas"
    assert folder_from_note_path("math/MT2_algebra_notes.md") == "math"


def test_folder_for_tag_math_core_first():
    assert folder_for_tag("MT1-T01", ["math-core/MT1_aptitude_interview_notes.md"]) == "math-core"
    assert folder_for_tag("MT0-T01", []) == "math-core"
    assert folder_for_tag("MT1-T19", []) == "math-core"  # legacy alias still folders to math-core
    assert folder_for_tag("MT2-T01", ["math/MT2_algebra_notes.md"]) == "math"
    assert folder_for_tag("L5-T05", ["pandas/L05_pandas_operations_notes.md"]) == "pandas"
    assert folder_for_tag("L2-T01", []) == "numpy"
    assert folder_for_tag("vocab.group.3", []) == "vocab"


def test_enrich_sets_rank_math_core_before_math():
    a = enrich_tag_folder({"id": "MT1-T01", "note_paths": ["math-core/x.md"]})
    b = enrich_tag_folder({"id": "MT2-T01", "note_paths": ["math/y.md"]})
    assert a["folder_rank"] < b["folder_rank"]


def test_remap_legacy_to_folders():
    from backend.transcripts.note_topics import remap_legacy_note_path

    assert (
        remap_legacy_note_path("math/MT1_aptitude_interview_notes.md")
        == "math-core/MT1_aptitude_interview_notes.md"
    )
    assert remap_legacy_note_path("L05_pandas_operations_notes.md") == "pandas/L05_pandas_operations_notes.md"
