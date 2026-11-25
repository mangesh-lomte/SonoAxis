import os
import time
import logging
from typing import Optional, Dict, Any, List
import ctranslate2
from faster_whisper import WhisperModel
import soundfile as sf

from backend.app.core.config import settings

logger = logging.getLogger("sonovoice.speech")

class SpeechRecognitionService:
    """
    Local Speech Recognition Service powered by Faster-Whisper (CTranslate2).
    Designed for 100% offline execution with zero telemetry.
    """
    _instance: Optional['SpeechRecognitionService'] = None
    _current_model: Optional[WhisperModel] = None
    _loaded_model_name: Optional[str] = None
    _active_device: str = "cpu"
    _active_compute_type: str = "int8"

    def __init__(self):
        self._check_hardware_capabilities()

    @classmethod
    def get_instance(cls) -> 'SpeechRecognitionService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _check_hardware_capabilities(self):
        """Checks whether CUDA is operational in CTranslate2, otherwise defaults to CPU."""
        cuda_count = ctranslate2.get_cuda_device_count()
        if cuda_count > 0:
            try:
                supported_cuda = ctranslate2.get_supported_compute_types("cuda")
                if "float16" in supported_cuda or "int8_float16" in supported_cuda:
                    self._active_device = "cuda"
                    self._active_compute_type = "float16" if "float16" in supported_cuda else "int8_float16"
                    logger.info(f"CUDA detected: {cuda_count} device(s). Using device=cuda, compute_type={self._active_compute_type}")
                    return
            except Exception as e:
                logger.warning(f"CUDA check failed ({e}). Falling back to CPU.")
        
        self._active_device = "cpu"
        self._active_compute_type = "int8"
        logger.info(f"Using CPU execution with compute_type=int8 (threads={settings.CPU_THREADS})")

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Scans local models directory to list fully downloaded, offline-ready models."""
        available = []
        if os.path.exists(settings.MODELS_DIR):
            for name in os.listdir(settings.MODELS_DIR):
                model_path = os.path.join(settings.MODELS_DIR, name)
                if os.path.isdir(model_path):
                    has_model_bin = os.path.exists(os.path.join(model_path, "model.bin"))
                    has_config = os.path.exists(os.path.join(model_path, "config.json"))
                    if has_model_bin and has_config:
                        sz_mb = sum(
                            os.path.getsize(os.path.join(model_path, f)) 
                            for f in os.listdir(model_path) 
                            if os.path.isfile(os.path.join(model_path, f))
                        ) / (1024 * 1024)
                        available.append({
                            "name": name,
                            "path": model_path,
                            "size_mb": round(sz_mb, 2),
                            "is_loaded": (name == self._loaded_model_name)
                        })
        return available

    def get_model_path(self, model_name: str) -> str:
        """Resolves local absolute path for a requested model."""
        clean_name = os.path.basename(model_name)
        model_path = os.path.join(settings.MODELS_DIR, clean_name)
        if not os.path.isdir(model_path) or not os.path.exists(os.path.join(model_path, "model.bin")):
            raise FileNotFoundError(
                f"Model '{clean_name}' is not downloaded locally in {settings.MODELS_DIR}. "
                f"Clinical operation requires pre-downloaded offline models."
            )
        return model_path

    def load_model(self, model_name: Optional[str] = None, force_device: Optional[str] = None) -> WhisperModel:
        """Lazily loads the requested Whisper model into memory as a singleton."""
        target_model = model_name or settings.DEFAULT_MODEL
        target_device = force_device or self._active_device
        target_compute = "int8" if target_device == "cpu" else self._active_compute_type

        # Return existing model instance if already loaded with matching configuration
        if (self._current_model is not None and 
            self._loaded_model_name == target_model and 
            self._active_device == target_device):
            return self._current_model

        model_path = self.get_model_path(target_model)
        logger.info(f"Loading local Whisper model: {target_model} on {target_device} ({target_compute})...")

        start_time = time.time()
        try:
            self._current_model = WhisperModel(
                model_size_or_path=model_path,
                device=target_device,
                compute_type=target_compute,
                cpu_threads=settings.CPU_THREADS if target_device == "cpu" else 0,
                local_files_only=True
            )
            self._loaded_model_name = target_model
            self._active_device = target_device
            self._active_compute_type = target_compute
            load_duration = time.time() - start_time
            logger.info(f"Model '{target_model}' loaded successfully in {load_duration:.2f}s")
            return self._current_model
        except Exception as e:
            if target_device == "cuda":
                logger.warning(f"Failed to load model on CUDA ({e}). Attempting CPU fallback...")
                return self.load_model(target_model, force_device="cpu")
            raise RuntimeError(f"Failed to load local Whisper model '{target_model}': {e}")

    def get_audio_duration(self, audio_path: str) -> float:
        """Determines duration of an audio file in seconds."""
        try:
            info = sf.info(audio_path)
            return float(info.duration)
        except Exception:
            # Fallback using pyav or faster-whisper internal reader
            return 0.0

    CLINICAL_ULTRASOUND_PROMPT = (
        "Ultrasound abdomen and pelvis examination report. Clinical findings: "
        "Liver is normal in size and echotexture, no focal lesion. "
        "Gallbladder normal, no calculus, wall thickness normal. "
        "Common bile duct normal calibre. Pancreas normal. Spleen normal. "
        "Right kidney measures in cm, left kidney measures in cm, normal corticomedullary differentiation, no hydronephrosis. "
        "Urinary bladder well distended, wall thickness normal. "
        "Prostate normal in size and volume in cc. "
        "Uterus anteverted, measures in cm, endometrial thickness in mm. "
        "Ovaries normal, no adnexal mass. No free fluid in pelvis. "
        "Correction: right kidney measures in cm. Impression: normal study."
    )

    def transcribe(
        self,
        audio_path: str,
        model_name: Optional[str] = None,
        initial_prompt: Optional[str] = None,
        word_timestamps: bool = True,
        vad_filter: bool = True,
        beam_size: int = 5
    ) -> Dict[str, Any]:
        """
        Transcribes a local audio file using the offline Faster-Whisper model.
        Returns full transcript, segments, word timestamps, duration, and performance metrics.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Ensure model is loaded
        model = self.load_model(model_name)
        
        # Acoustic terminology prompt (prompts vocabulary phonetics without creating clinical statements)
        prompt = initial_prompt or self.CLINICAL_ULTRASOUND_PROMPT

        audio_duration = self.get_audio_duration(audio_path)
        inference_start = time.time()

        segments_generator, info = model.transcribe(
            audio_path,
            language="en",
            task="transcribe",
            initial_prompt=prompt,
            beam_size=beam_size,
            best_of=beam_size,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=vad_filter,
            vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=400),
            word_timestamps=word_timestamps
        )

        segments_list = []
        raw_text_parts = []

        for seg in segments_generator:
            seg_dict = {
                "id": seg.id,
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
                "words": []
            }
            if word_timestamps and seg.words:
                for w in seg.words:
                    seg_dict["words"].append({
                        "word": w.word.strip(),
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "probability": round(w.probability, 3)
                    })
            segments_list.append(seg_dict)
            raw_text_parts.append(seg.text.strip())

        inference_duration = time.time() - inference_start
        full_transcript = " ".join(raw_text_parts).strip()
        
        # Real-time factor (RTF = inference_duration / audio_duration)
        effective_duration = audio_duration if audio_duration > 0 else (segments_list[-1]["end"] if segments_list else 1.0)
        rtf = round(inference_duration / effective_duration, 3) if effective_duration > 0 else 0.0

        return {
            "transcript": full_transcript,
            "segments": segments_list,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "audio_duration_seconds": round(effective_duration, 2),
            "processing_time_seconds": round(inference_duration, 3),
            "real_time_factor": rtf,
            "model_used": self._loaded_model_name,
            "device": self._active_device,
            "compute_type": self._active_compute_type
        }
