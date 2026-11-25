import os
import subprocess

fixtures_dir = os.path.abspath("D:/sovoice/tests/fixtures")
os.makedirs(fixtures_dir, exist_ok=True)

test_cases = {
    "test_a_basic": "Liver is normal in size. Spleen measures eleven centimeters. Right kidney measures ten point two centimeters.",
    "test_b_correction": "Right kidney measures ten point two centimeters. Liver is normal in size. Correction: right kidney measures ten point eight centimeters.",
    "test_c_negation": "No gallstones are seen. No hydronephrosis is noted in the left kidney.",
    "test_d_female": "Uterus measures seven point two by three point five by four point one centimeters. Endometrium measures six millimeters. Both ovaries are normal in size.",
    "test_e_complex": "Both kidneys demonstrate preserved corticomedullary differentiation. No calculus or hydroureter is noted.",
    "test_f_ambiguous": "A small cyst measuring eight millimeters is noted."
}

print(f"=== GENERATING TEST AUDIO FIXTURES IN {fixtures_dir} ===")

for key, text in test_cases.items():
    wav_path = os.path.join(fixtures_dir, f"{key}.wav")
    escaped_text = text.replace('"', '`"')
    ps_cmd = f"""
    Add-Type -AssemblyName System.Speech;
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;
    $synth.Rate = 0;
    $synth.SetOutputToWaveFile('{wav_path}');
    $synth.Speak('{escaped_text}');
    $synth.Dispose();
    """
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(wav_path):
        sz = os.path.getsize(wav_path)
        print(f"Generated {key}.wav: {sz} bytes")
    else:
        print(f"Failed to generate {key}.wav: {res.stderr}")
