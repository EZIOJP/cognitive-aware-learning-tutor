from transcript_studio.parse_audit import audit_parse, format_audit_report


def test_audit_live_caption_prefix_dedup_mostly_safe():
    raw = (
        "Hey welcome\n"
        "Hey welcome everyone\n"
        "Hey welcome everyone today we cover numpy arrays"
    )
    report = audit_parse(raw, aggressive=True)
    cleaned = report.cleaned_text
    assert "numpy arrays" in cleaned
    assert report.word_retention_pct > 50
    assert report.review_count == 0 or report.likely_safe_removals >= 1


def test_audit_reports_word_retention():
    raw = "um okay so arrays are um fast and arrays are fast"
    report = audit_parse(raw, aggressive=False)
    assert report.clean_words <= report.raw_words
    assert report.clean_sentences >= 1


def test_format_audit_report_includes_counts():
    report = audit_parse("line one\nline two\nline two extended", aggressive=True)
    text = format_audit_report(report)
    assert "Cleanup audit" in text
    assert "Words:" in text
    assert "Sentences:" in text


def test_audit_notes_retention():
    from transcript_studio.parse_audit import audit_notes, format_notes_audit_report

    source = "numpy arrays indexing reshape arange boolean masking " * 20
    notes = "## NumPy\n\n- arrays and indexing\n- reshape basics\n"
    report = audit_notes(source, notes)
    assert report.source_words > report.notes_words
    assert report.word_retention_pct < 50
    text = format_notes_audit_report(report)
    assert "Notes retention audit" in text
    assert "Retention:" in text
