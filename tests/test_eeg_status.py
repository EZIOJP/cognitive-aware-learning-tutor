"""LED serial + EEG status soft-fail tests."""

from backend.eeg import led_serial
from backend.eeg import service as eeg_service


def test_status_payload_disabled_by_default():
    payload = eeg_service.status_payload()
    assert payload["ok"] is True
    assert payload["reliable_without_device"] is True
    assert "status" in payload
    assert "buffer_size" in payload
    assert "snap_count" in payload
    assert "last_voltage" in payload


def test_stream_status_values():
    s = eeg_service.stream_status()
    assert s in ("disabled", "offline", "warming", "streaming")


def test_snap_detection_on_voltage_spike():
    before = eeg_service.status_payload()["snap_count"]
    eeg_service._note_sample(1.65)
    eeg_service._note_sample(2.85)
    after = eeg_service.status_payload()
    assert after["snap_count"] == before + 1
    assert after["last_voltage"] == 2.85


def test_led_unknown_action():
    r = led_serial.send_led("not-a-color")
    assert r["ok"] is False
    assert "actions" in r


def test_led_actions_listed():
    st = led_serial.serial_status()
    assert "on" in st["led_actions"]
    assert "off" in st["led_actions"]
    assert "heartbeat" in st["led_actions"]
