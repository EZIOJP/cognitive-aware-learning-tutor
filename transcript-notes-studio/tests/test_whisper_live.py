import numpy as np

from transcript_studio.whisper_live import _to_mono, faster_whisper_model_id


def test_faster_whisper_model_id_maps_hf_names():
    assert faster_whisper_model_id("openai/whisper-large-v3-turbo") == "large-v3-turbo"
    assert faster_whisper_model_id("large-v3") == "large-v3"


def test_to_mono_stereo_downmix():
    stereo = np.array([[1.0, -1.0], [0.5, 0.5]], dtype=np.float32)
    mono = _to_mono(stereo)
    assert mono.shape == (2,)
    assert abs(float(mono[0]) - 0.0) < 1e-6
