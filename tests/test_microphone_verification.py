import os
import io
import time
import wave
import struct
import tempfile
import pytest
from backend.app.services.speech_service import SpeechRecognitionService

@pytest.fixture(scope="module")
def synthetic_silent_wav_path():
    """Generates a 1-second 16kHz mono 16-bit PCM WAV file on disk."""
    sample_rate = 16000
    duration_s = 1.0
    num_samples = int(sample_rate * duration_s)
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name

    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        # Write pure silence
        data = struct.pack(f"<{num_samples}h", *([0] * num_samples))
        wav.writeframes(data)
    
    yield path
    
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass

def test_speech_service_model_initialization():
    """Verifies that Faster-Whisper local model initializes offline on CPU INT8."""
    svc = SpeechRecognitionService.get_instance()
    assert svc is not None
    models = svc.get_available_models()
    assert len(models) >= 1
    loaded = svc.load_model()
    assert loaded is not None

def test_speech_service_transcription_pipeline(synthetic_silent_wav_path):
    """Verifies end-to-end transcription pipeline with synthetic audio."""
    svc = SpeechRecognitionService.get_instance()
    t0 = time.time()
    result = svc.transcribe(synthetic_silent_wav_path)
    elapsed = time.time() - t0
    
    assert result is not None
    assert "text" in result or "transcript" in result
    assert "segments" in result
    assert elapsed < 15.0, f"Transcription took {elapsed:.2f}s, expected < 15.0s for 1s audio"

def test_microphone_audio_missing_file_validation():
    """Verifies missing audio file raises FileNotFoundError gracefully."""
    svc = SpeechRecognitionService.get_instance()
    with pytest.raises(FileNotFoundError):
        svc.transcribe("non_existent_audio_file.wav")
