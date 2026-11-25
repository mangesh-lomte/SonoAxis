import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.speech_service import SpeechRecognitionService
from backend.app.core.config import settings

fixtures_dir = os.path.abspath("D:/sovoice/tests/fixtures")

@pytest.fixture(scope="session")
def speech_service():
    return SpeechRecognitionService.get_instance()

def test_health_endpoint(unauth_client):
    res = unauth_client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_engine_status_endpoint(client):
    res = client.get("/api/engine/status")
    assert res.status_code == 200
    data = res.json()
    assert "engine" in data
    assert "available_models" in data
    assert len(data["available_models"]) >= 2

def test_model_availability(speech_service):
    models = speech_service.get_available_models()
    model_names = [m["name"] for m in models]
    assert "base.en" in model_names
    assert "small.en" in model_names

def test_offline_model_loading(speech_service):
    # Verifies local offline load
    model = speech_service.load_model("base.en", force_device="cpu")
    assert model is not None
    assert speech_service._loaded_model_name == "base.en"

def test_valid_audio_transcription(speech_service):
    wav_path = os.path.join(fixtures_dir, "test_a_basic.wav")
    assert os.path.exists(wav_path)
    
    result = speech_service.transcribe(wav_path, model_name="small.en")
    assert "transcript" in result
    assert "segments" in result
    assert "audio_duration_seconds" in result
    assert "processing_time_seconds" in result
    assert "real_time_factor" in result
    assert "liver" in result["transcript"].lower()
    assert "spleen" in result["transcript"].lower()
    assert "kidney" in result["transcript"].lower()

def test_transcription_timestamps_structure(speech_service):
    wav_path = os.path.join(fixtures_dir, "test_a_basic.wav")
    result = speech_service.transcribe(wav_path, model_name="small.en", word_timestamps=True)
    
    assert len(result["segments"]) > 0
    seg = result["segments"][0]
    assert "start" in seg
    assert "end" in seg
    assert "text" in seg
    assert seg["end"] >= seg["start"]
    
    # Verify word timestamps
    assert "words" in seg
    assert len(seg["words"]) > 0
    w = seg["words"][0]
    assert "word" in w
    assert "start" in w
    assert "end" in w

def test_correction_preservation(speech_service):
    wav_path = os.path.join(fixtures_dir, "test_b_correction.wav")
    result = speech_service.transcribe(wav_path, model_name="small.en")
    t = result["transcript"].lower()
    assert "10.2" in t
    assert "10.8" in t
    assert "correction" in t

def test_negation_and_laterality(speech_service):
    wav_path = os.path.join(fixtures_dir, "test_c_negation.wav")
    result = speech_service.transcribe(wav_path, model_name="small.en")
    t = result["transcript"].lower()
    assert "no gallstones" in t
    assert "no hydronephrosis" in t
    assert "left kidney" in t

def test_missing_model_error(speech_service):
    with pytest.raises(FileNotFoundError) as exc_info:
        speech_service.load_model("nonexistent_model.en")
    assert "not downloaded locally" in str(exc_info.value)

def test_empty_audio_rejection(client):
    empty_file_path = os.path.join(fixtures_dir, "empty.wav")
    with open(empty_file_path, "wb") as f:
        pass  # 0 bytes
    
    with open(empty_file_path, "rb") as f:
        res = client.post("/api/audio/transcribe", files={"file": ("empty.wav", f, "audio/wav")})
    
    if os.path.exists(empty_file_path):
        os.remove(empty_file_path)
    
    assert res.status_code in [400, 422, 500]

def test_unsupported_format_rejection(client):
    fake_exe = os.path.join(fixtures_dir, "malicious.exe")
    with open(fake_exe, "wb") as f:
        f.write(b"NOT_AN_AUDIO_FILE")
    
    with open(fake_exe, "rb") as f:
        res = client.post("/api/audio/transcribe", files={"file": ("malicious.exe", f, "application/octet-stream")})
    
    if os.path.exists(fake_exe):
        os.remove(fake_exe)
    
    assert res.status_code == 400
    assert "Unsupported file extension" in res.json()["detail"]

def test_api_transcribe_endpoint(client):
    wav_path = os.path.join(fixtures_dir, "test_f_ambiguous.wav")
    with open(wav_path, "rb") as f:
        res = client.post(
            "/api/audio/transcribe",
            files={"file": ("test_f_ambiguous.wav", f, "audio/wav")},
            data={"model_name": "small.en", "word_timestamps": "true"}
        )
    assert res.status_code == 200
    data = res.json()
    assert "transcript" in data
    assert "cyst" in data["transcript"].lower()
    assert "8" in data["transcript"]
