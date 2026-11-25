import os
import pytest
from backend.app.services.speech_service import SpeechRecognitionService
from backend.app.structuring.engine import structuring_engine

fixtures_dir = os.path.abspath("D:/sovoice/tests/fixtures")

@pytest.fixture(scope="session")
def speech_service():
    return SpeechRecognitionService.get_instance()

def test_voice_to_report_test_a_basic(speech_service):
    """
    Test A (Basic organ findings):
    Audio: 'Liver is normal in size. Spleen measures eleven centimeters. Right kidney measures ten point two centimeters.'
    """
    audio_path = os.path.join(fixtures_dir, "test_a_basic.wav")
    assert os.path.exists(audio_path)
    
    # 1. Transcribe actual audio using local Faster-Whisper
    transcription = speech_service.transcribe(audio_path, model_name="small.en")
    raw_text = transcription["transcript"]
    assert len(raw_text) > 0

    # 2. Pass real transcription to structuring engine
    report = structuring_engine.structure_transcript(
        transcript=raw_text,
        template_id="usg-abdomen-pelvis-male",
        audio_segments=transcription["segments"]
    )

    # 3. Verify canonical output
    active_keys = [s.key for s in report.sections if s.is_present]
    assert active_keys == ["liver", "spleen", "right_kidney"]
    
    liver = next(s for s in report.sections if s.key == "liver")
    spleen = next(s for s in report.sections if s.key == "spleen")
    rk = next(s for s in report.sections if s.key == "right_kidney")
    
    assert "normal in size" in liver.text.lower()
    assert any("11" in m.raw_str for m in spleen.measurements)
    assert any("10.2" in m.raw_str for m in rk.measurements)
    assert report.impression is None  # Undictated remains blank

def test_voice_to_report_test_b_mandatory_correction(speech_service):
    """
    Test B (Mandatory explicit correction):
    Audio: 'Right kidney measures ten point two centimeters. Liver is normal in size. Correction: right kidney measures ten point eight centimeters.'
    """
    audio_path = os.path.join(fixtures_dir, "test_b_correction.wav")
    transcription = speech_service.transcribe(audio_path, model_name="small.en")
    raw_text = transcription["transcript"]

    report = structuring_engine.structure_transcript(
        transcript=raw_text,
        template_id="usg-abdomen-pelvis-male",
        audio_segments=transcription["segments"]
    )

    active_keys = [s.key for s in report.sections if s.is_present]
    assert "liver" in active_keys
    assert "right_kidney" in active_keys
    assert "left_kidney" not in active_keys

    rk = next(s for s in report.sections if s.key == "right_kidney")
    assert "10.8" in rk.text
    assert "10.2" not in rk.text
    assert any("10.8" in m.raw_str for m in rk.measurements)
    assert not any("10.2" in m.raw_str for m in rk.measurements)

    # Verify superseded audit history
    assert len(report.superseded_history) == 1
    assert report.superseded_history[0].organ_key == "right_kidney"
    assert "10.2" in report.superseded_history[0].superseded_text

def test_voice_to_report_test_c_negation_and_laterality(speech_service):
    """
    Test C (Negation and laterality):
    Audio: 'No gallstones are seen. No hydronephrosis is noted in the left kidney.'
    """
    audio_path = os.path.join(fixtures_dir, "test_c_negation.wav")
    transcription = speech_service.transcribe(audio_path, model_name="small.en")
    raw_text = transcription["transcript"]

    report = structuring_engine.structure_transcript(
        transcript=raw_text,
        template_id="usg-abdomen-pelvis-male",
        audio_segments=transcription["segments"]
    )

    active_keys = [s.key for s in report.sections if s.is_present]
    assert "gall_bladder" in active_keys
    assert "left_kidney" in active_keys
    assert "right_kidney" not in active_keys

    gb = next(s for s in report.sections if s.key == "gall_bladder")
    lk = next(s for s in report.sections if s.key == "left_kidney")
    assert gb.findings[0].is_negation is True
    assert lk.findings[0].is_negation is True

def test_voice_to_report_test_d_female_pelvis(speech_service):
    """
    Test D (Female pelvis & multi-dimensional measurements):
    Audio: 'Uterus measures seven point two by three point five by four point one centimeters. Endometrium measures six millimeters. Both ovaries are normal in size.'
    """
    audio_path = os.path.join(fixtures_dir, "test_d_female.wav")
    transcription = speech_service.transcribe(audio_path, model_name="small.en")
    raw_text = transcription["transcript"]

    report = structuring_engine.structure_transcript(
        transcript=raw_text,
        template_id="usg-abdomen-pelvis-female",
        audio_segments=transcription["segments"]
    )

    active_keys = [s.key for s in report.sections if s.is_present]
    assert "uterus" in active_keys
    assert "endometrium" in active_keys
    assert "ovaries_bilateral" in active_keys

    uterus = next(s for s in report.sections if s.key == "uterus")
    endo = next(s for s in report.sections if s.key == "endometrium")
    assert uterus.measurements[0].dimension == 3
    assert any("6" in m.raw_str for m in endo.measurements)

def test_voice_to_report_test_e_complex_eponyms(speech_service):
    """
    Test E (Complex medical terminology):
    Audio: 'Both kidneys demonstrate preserved corticomedullary differentiation. No calculus or hydroureter is noted.'
    """
    audio_path = os.path.join(fixtures_dir, "test_e_complex.wav")
    transcription = speech_service.transcribe(audio_path, model_name="small.en")
    raw_text = transcription["transcript"]

    report = structuring_engine.structure_transcript(
        transcript=raw_text,
        template_id="usg-abdomen-pelvis-male",
        audio_segments=transcription["segments"]
    )

    kc = next(s for s in report.sections if s.key == "kidneys_common")
    assert kc.is_present is True
    assert "corticomedullary" in kc.text.lower()

def test_voice_to_report_test_f_ambiguous(speech_service):
    """
    Test F (Ambiguous finding):
    Audio: 'A small cyst measuring eight millimeters is noted.'
    """
    audio_path = os.path.join(fixtures_dir, "test_f_ambiguous.wav")
    transcription = speech_service.transcribe(audio_path, model_name="small.en")
    raw_text = transcription["transcript"]

    report = structuring_engine.structure_transcript(
        transcript=raw_text,
        template_id="usg-abdomen-pelvis-male",
        audio_segments=transcription["segments"]
    )

    assert len(report.unassigned_findings) == 1
    unassigned = report.unassigned_findings[0]
    assert unassigned.reason == "no_organ_identified"
    assert any("8" in m.raw_str for m in unassigned.measurements)
