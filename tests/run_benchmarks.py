import os
import sys
sys.path.insert(0, os.path.abspath("."))
import time
import json
import ctypes
from backend.app.services.speech_service import SpeechRecognitionService

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]

def get_avail_ram_mb():
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    return round(stat.ullAvailPhys / (1024 * 1024), 2)

service = SpeechRecognitionService.get_instance()
fixtures_dir = os.path.abspath("D:/sovoice/tests/fixtures")

test_cases = [
    {
        "id": "Test A (Basic)",
        "file": "test_a_basic.wav",
        "reference": "Liver is normal in size. Spleen measures eleven centimeters. Right kidney measures ten point two centimeters."
    },
    {
        "id": "Test B (Correction)",
        "file": "test_b_correction.wav",
        "reference": "Right kidney measures ten point two centimeters. Liver is normal in size. Correction: right kidney measures ten point eight centimeters."
    },
    {
        "id": "Test C (Negation & Laterality)",
        "file": "test_c_negation.wav",
        "reference": "No gallstones are seen. No hydronephrosis is noted in the left kidney."
    },
    {
        "id": "Test D (Female Pelvis & Decimals)",
        "file": "test_d_female.wav",
        "reference": "Uterus measures seven point two by three point five by four point one centimeters. Endometrium measures six millimeters. Both ovaries are normal in size."
    },
    {
        "id": "Test E (Complex Medical Eponyms)",
        "file": "test_e_complex.wav",
        "reference": "Both kidneys demonstrate preserved corticomedullary differentiation. No calculus or hydroureter is noted."
    },
    {
        "id": "Test F (Ambiguous Finding)",
        "file": "test_f_ambiguous.wav",
        "reference": "A small cyst measuring eight millimeters is noted."
    }
]

models_to_test = ["base.en", "small.en"]
all_results = {}

print("=== STARTING SPEECH RECOGNITION BENCHMARKS ===")
initial_ram = get_avail_ram_mb()
print(f"Initial Available RAM: {initial_ram} MB")

for model_name in models_to_test:
    print(f"\n========================================================")
    print(f"BENCHMARKING MODEL: {model_name} (CPU, INT8, 4 Threads)")
    print(f"========================================================")
    
    # Measure model loading time
    t0 = time.time()
    service.load_model(model_name, force_device="cpu")
    load_time = round(time.time() - t0, 3)
    post_load_ram = get_avail_ram_mb()
    print(f"Model Load Time: {load_time}s | Available RAM after load: {post_load_ram} MB")

    model_results = []
    for tc in test_cases:
        wav_path = os.path.join(fixtures_dir, tc["file"])
        ram_before = get_avail_ram_mb()
        
        res = service.transcribe(wav_path, model_name=model_name)
        ram_after = get_avail_ram_mb()
        
        tc_res = {
            "id": tc["id"],
            "reference": tc["reference"],
            "transcript": res["transcript"],
            "audio_duration_seconds": res["audio_duration_seconds"],
            "processing_time_seconds": res["processing_time_seconds"],
            "real_time_factor": res["real_time_factor"],
            "segment_count": len(res["segments"]),
            "word_count": sum(len(s.get("words", [])) for s in res["segments"]),
            "ram_used_mb": round(ram_before - ram_after, 2)
        }
        model_results.append(tc_res)
        
        print(f"\n[{tc['id']}] Audio: {res['audio_duration_seconds']}s | Time: {res['processing_time_seconds']}s | RTF: {res['real_time_factor']}x")
        print(f"  Ref : {tc['reference']}")
        print(f"  Hyp : {res['transcript']}")

    all_results[model_name] = {
        "load_time_seconds": load_time,
        "test_cases": model_results
    }

# Save results JSON
benchmark_json_path = os.path.join("D:/sovoice/research", "benchmark_results.json")
with open(benchmark_json_path, "w", encoding="utf-8") as fp:
    json.dump(all_results, fp, indent=2)

print(f"\nBenchmark suite complete. Results saved to {benchmark_json_path}")
