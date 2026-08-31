"""Reliability tests for chunked voice-note upload.

The watch deletes its only copy of a recording once the PC reports it stored,
so these tests focus on the ways a transfer could silently publish a file that
does not match what was recorded.
"""

from __future__ import annotations

import base64

import pytest

from backend.behavior import voice_notes as vn

CHUNK = 64
NAME = "voice_20260831_141203.opus"


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    notes = tmp_path / "voice_notes"
    monkeypatch.setattr(vn, "NOTES_DIR", notes)
    monkeypatch.setattr(vn, "PARTIAL_DIR", notes / ".partial")
    return notes


def _blob(n: int = 500) -> bytes:
    return bytes((i * 7 + 11) % 256 for i in range(n))


def _begin(blob: bytes, *, name: str = NAME, chunk_size: int = CHUNK):
    total = (len(blob) + chunk_size - 1) // chunk_size
    return vn.begin_upload(
        name=name,
        size=len(blob),
        chunk_size=chunk_size,
        total_chunks=total,
        sha=vn.fnv1a32(blob),
    )


def _send(upload_id: str, blob: bytes, index: int, *, chunk_size: int = CHUNK, corrupt=False):
    piece = blob[index * chunk_size : (index + 1) * chunk_size]
    payload = b"\x00" * len(piece) if corrupt else piece
    return vn.accept_chunk(
        upload_id=upload_id,
        index=index,
        data_b64=base64.b64encode(payload).decode(),
        # Checksum always describes the true bytes, so a corrupted payload fails.
        checksum=vn.fnv1a32(piece),
    )


def _send_all(upload_id: str, blob: bytes, *, chunk_size: int = CHUNK, skip=()):
    total = (len(blob) + chunk_size - 1) // chunk_size
    for i in range(total):
        if i not in skip:
            _send(upload_id, blob, i, chunk_size=chunk_size)
    return total


# --- checksum parity with the watch ---------------------------------------


def test_fnv1a32_matches_standard_vectors():
    """The watch computes the same FNV-1a in JS; a drift here corrupts every transfer."""
    assert vn.fnv1a32(b"") == "h811c9dc5"
    assert vn.fnv1a32(b"a") == "he40c292c"
    assert vn.fnv1a32(b"foobar") == "hbf9cf968"


def test_fnv1a32_is_unpadded_like_js_tostring16():
    # JS (h >>> 0).toString(16) does not zero-pad, so Python must not either.
    for n in range(4000):
        digest = vn.fnv1a32(bytes([n % 256]) * (n % 7 + 1))
        assert not digest[1:].startswith("0") or digest == "h0"


# --- happy path ------------------------------------------------------------


def test_round_trip_reassembles_exact_bytes(_tmp_dirs):
    blob = _blob()
    begin = _begin(blob)
    _send_all(begin["upload_id"], blob)

    result = vn.finish_upload(upload_id=begin["upload_id"])

    assert result["ok"] and result["stored"]
    assert (_tmp_dirs / NAME).read_bytes() == blob


def test_out_of_order_chunks_reassemble_correctly(_tmp_dirs):
    blob = _blob()
    begin = _begin(blob)
    total = (len(blob) + CHUNK - 1) // CHUNK
    for i in reversed(range(total)):
        _send(begin["upload_id"], blob, i)

    assert vn.finish_upload(upload_id=begin["upload_id"])["ok"]
    assert (_tmp_dirs / NAME).read_bytes() == blob


def test_final_chunk_shorter_than_chunk_size_is_accepted(_tmp_dirs):
    blob = _blob(CHUNK * 3 + 1)  # last chunk is a single byte
    begin = _begin(blob)
    _send_all(begin["upload_id"], blob)

    assert vn.finish_upload(upload_id=begin["upload_id"])["ok"]
    assert (_tmp_dirs / NAME).read_bytes() == blob


# --- replay and resume -----------------------------------------------------


def test_replayed_chunk_rewrites_same_offset(_tmp_dirs):
    blob = _blob()
    begin = _begin(blob)
    _send_all(begin["upload_id"], blob)
    for i in range(3):
        _send(begin["upload_id"], blob, i)

    assert vn.finish_upload(upload_id=begin["upload_id"])["ok"]
    assert (_tmp_dirs / NAME).read_bytes() == blob


def test_resume_reports_already_received_chunks():
    blob = _blob()
    begin = _begin(blob)
    _send(begin["upload_id"], blob, 0)
    _send(begin["upload_id"], blob, 2)

    again = _begin(blob)

    assert again["upload_id"] == begin["upload_id"]
    assert again["received"] == [0, 2]
    assert not again["complete"]


def test_resume_after_interruption_completes_without_resending_everything(_tmp_dirs):
    blob = _blob()
    begin = _begin(blob)
    total = (len(blob) + CHUNK - 1) // CHUNK
    _send_all(begin["upload_id"], blob, skip=set(range(3, total)))

    resumed = _begin(blob)
    for i in range(3, total):
        _send(resumed["upload_id"], blob, i)

    assert vn.finish_upload(upload_id=resumed["upload_id"])["ok"]
    assert (_tmp_dirs / NAME).read_bytes() == blob


def test_begin_on_already_published_note_reports_stored(_tmp_dirs):
    blob = _blob()
    begin = _begin(blob)
    _send_all(begin["upload_id"], blob)
    vn.finish_upload(upload_id=begin["upload_id"])

    again = _begin(blob)

    # Watch may retry after losing the ack; it must be told to drop its copy.
    assert again["complete"] and again["stored"]


# --- corruption refusal ----------------------------------------------------


def test_corrupt_chunk_is_rejected_and_not_recorded():
    blob = _blob()
    begin = _begin(blob)

    with pytest.raises(ValueError, match="checksum_mismatch"):
        _send(begin["upload_id"], blob, 0, corrupt=True)

    assert vn.upload_status(upload_id=begin["upload_id"])["received"] == []


def test_wrong_length_chunk_is_rejected():
    blob = _blob()
    begin = _begin(blob)
    short = blob[:10]

    with pytest.raises(ValueError, match="bad_chunk_length"):
        vn.accept_chunk(
            upload_id=begin["upload_id"],
            index=0,
            data_b64=base64.b64encode(short).decode(),
            checksum=vn.fnv1a32(short),
        )


def test_finish_with_missing_chunks_publishes_nothing(_tmp_dirs):
    blob = _blob()
    begin = _begin(blob)
    _send_all(begin["upload_id"], blob, skip={2})

    result = vn.finish_upload(upload_id=begin["upload_id"])

    assert not result["ok"]
    assert result["error"] == "incomplete"
    assert result["missing"] == [2]
    assert not (_tmp_dirs / NAME).exists()


def test_whole_file_checksum_mismatch_discards_and_publishes_nothing(_tmp_dirs):
    """Every chunk can pass individually and the file still be wrong."""
    blob = _blob()
    begin = vn.begin_upload(
        name=NAME,
        size=len(blob),
        chunk_size=CHUNK,
        total_chunks=(len(blob) + CHUNK - 1) // CHUNK,
        sha="hdeadbeef",  # watch declared a digest the bytes do not produce
    )
    _send_all(begin["upload_id"], blob)

    result = vn.finish_upload(upload_id=begin["upload_id"])

    assert not result["ok"]
    assert result["error"] == "file_checksum_mismatch"
    assert result["restart"]
    assert not (_tmp_dirs / NAME).exists()
    assert vn.upload_status(upload_id=begin["upload_id"])["error"] == "unknown_upload"


def test_partial_transfer_is_not_visible_as_a_playable_note(_tmp_dirs):
    blob = _blob()
    begin = _begin(blob)
    _send_all(begin["upload_id"], blob, skip={0})

    assert vn.list_notes() == []
    assert not (_tmp_dirs / NAME).exists()


# --- input guards ----------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["../escape.opus", "voice.mp3", "", "a" * 90 + ".opus", "sub/dir.opus"],
)
def test_bad_names_are_refused(name):
    with pytest.raises(ValueError, match="bad_name"):
        _begin(_blob(), name=name)


def test_declared_chunk_count_must_match_size():
    blob = _blob()
    with pytest.raises(ValueError, match="chunk_count_mismatch"):
        vn.begin_upload(
            name=NAME,
            size=len(blob),
            chunk_size=CHUNK,
            total_chunks=99,
            sha=vn.fnv1a32(blob),
        )


def test_oversized_note_is_refused():
    with pytest.raises(ValueError, match="bad_size"):
        vn.begin_upload(
            name=NAME,
            size=vn.MAX_NOTE_BYTES + 1,
            chunk_size=CHUNK,
            total_chunks=1,
            sha="h0",
        )


def test_index_out_of_range_is_refused():
    blob = _blob()
    begin = _begin(blob)
    with pytest.raises(ValueError, match="index_out_of_range"):
        vn.accept_chunk(
            upload_id=begin["upload_id"], index=999, data_b64="", checksum="h0"
        )


def test_chunk_for_unknown_upload_is_refused():
    with pytest.raises(LookupError, match="unknown_upload"):
        vn.accept_chunk(upload_id="hnope", index=0, data_b64="", checksum="h0")


def test_web_list_and_download(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import app

    notes = tmp_path / "voice_notes"
    monkeypatch.setattr(vn, "NOTES_DIR", notes)
    monkeypatch.setattr(vn, "PARTIAL_DIR", notes / ".partial")
    notes.mkdir(parents=True)

    blob = _blob(128)
    name = "voice_20260831_120000.opus"
    (notes / name).write_bytes(blob)

    client = TestClient(app)
    listed = client.get("/api/behavior/voice-notes").json()
    assert listed["ok"]
    assert [n["name"] for n in listed["notes"]] == [name]

    res = client.get(f"/api/behavior/voice-notes/{name}")
    assert res.status_code == 200
    assert res.content == blob
    assert "audio/opus" in res.headers.get("content-type", "")

    assert client.get("/api/behavior/voice-notes/missing.opus").status_code == 404
    assert client.get("/api/behavior/voice-notes/notvoice.mp3").status_code == 400


# --- hub wiring ------------------------------------------------------------
#
# The unit tests above call the module directly. These drive the real ASGI app
# the way the phone side service will, so body parsing, auth and status codes
# are covered too.


@pytest.fixture(scope="module")
def hub():
    from fastapi.testclient import TestClient

    from backend.behavior.tracker_hub import _build_app
    from backend.wearables.router import _expected_ingest_key

    # Built once and closed explicitly: the hub app is shared process state and
    # leaking a client's worker threads perturbs timing-sensitive tests
    # elsewhere in the suite.
    client = TestClient(_build_app())
    try:
        yield client, {"X-CALT-Wearable-Key": _expected_ingest_key()}
    finally:
        client.close()


def _post(client, headers, path, payload):
    return client.post(f"/api/hub/voice-note/{path}", headers=headers, json=payload)


def test_hub_requires_the_ingest_key(hub):
    client, _ = hub
    assert client.post("/api/hub/voice-note/begin", json={}).status_code == 401


def test_hub_round_trip_with_resume_and_replay(hub, _tmp_dirs):
    client, headers = hub
    blob = _blob(1500)
    total = (len(blob) + CHUNK - 1) // CHUNK
    begin_body = {
        "name": NAME,
        "size": len(blob),
        "chunk_size": CHUNK,
        "total_chunks": total,
        "sha": vn.fnv1a32(blob),
    }

    begin = _post(client, headers, "begin", begin_body).json()
    upload_id = begin["upload_id"]

    def send(i):
        piece = blob[i * CHUNK : (i + 1) * CHUNK]
        return _post(
            client,
            headers,
            "chunk",
            {
                "upload_id": upload_id,
                "index": i,
                "data": base64.b64encode(piece).decode(),
                "checksum": vn.fnv1a32(piece),
            },
        )

    send(0)
    send(1)
    status = client.get(
        "/api/hub/voice-note/status", headers=headers, params={"upload_id": upload_id}
    ).json()
    assert status["received"] == [0, 1]

    early = _post(client, headers, "finish", {"upload_id": upload_id}).json()
    assert early["error"] == "incomplete"

    for i in range(2, total):
        send(i)

    done = _post(client, headers, "finish", {"upload_id": upload_id}).json()
    assert done["ok"] and done["stored"]
    assert (_tmp_dirs / NAME).read_bytes() == blob

    listed = client.get("/api/hub/voice-note/list", headers=headers).json()
    assert [n["name"] for n in listed["notes"]] == [NAME]

    # Watch retries after a lost ack: it must be told the clip is already safe.
    assert _post(client, headers, "begin", begin_body).json()["stored"]


def test_hub_rejects_a_corrupt_chunk_with_400(hub):
    client, headers = hub
    blob = _blob()
    total = (len(blob) + CHUNK - 1) // CHUNK
    begin = _post(
        client,
        headers,
        "begin",
        {
            "name": NAME,
            "size": len(blob),
            "chunk_size": CHUNK,
            "total_chunks": total,
            "sha": vn.fnv1a32(blob),
        },
    ).json()

    res = _post(
        client,
        headers,
        "chunk",
        {
            "upload_id": begin["upload_id"],
            "index": 0,
            "data": base64.b64encode(b"\x00" * CHUNK).decode(),
            "checksum": vn.fnv1a32(blob[:CHUNK]),
        },
    )

    assert res.status_code == 400
    assert "checksum_mismatch" in res.json()["error"]
