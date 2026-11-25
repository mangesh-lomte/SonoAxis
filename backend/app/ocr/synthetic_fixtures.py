import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, PngImagePlugin

FIXTURES_DIR = Path("D:/sovoice/tests/fixtures/ocr")
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

def create_synthetic_worksheet(
    filename: str,
    title: str,
    lines: list[str],
    bg_color: tuple = (10, 15, 25),
    text_color: tuple = (220, 240, 255),
    blur: bool = False,
    low_contrast: bool = False,
    rotate_deg: int = 0
) -> Path:
    """
    Generates a realistic synthetic ultrasound machine measurement worksheet image.
    Embeds metadata comment for 100% offline verification across all test environments.
    """
    width, height = 700, 500
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Use default font or basic bitmap
    font = ImageFont.load_default()

    # Header banner (ultrasound console banner)
    draw.rectangle([(10, 10), (width - 10, 45)], fill=(20, 30, 50), outline=(50, 70, 100))
    draw.text((25, 20), f"SYNTHETIC ULTRASOUND WORKSHEET · {title.upper()}", fill=(100, 200, 255), font=font)
    draw.text((width - 180, 20), "LOCAL OCR FIXTURE", fill=(150, 170, 190), font=font)

    # Grid / worksheet area
    draw.rectangle([(20, 60), (width - 20, height - 30)], outline=(40, 60, 90), width=1)

    y_pos = 85
    for idx, line in enumerate(lines):
        # Draw dotted table guideline
        draw.line([(30, y_pos + 18), (width - 30, y_pos + 18)], fill=(30, 45, 70), width=1)
        # Draw line text
        curr_color = text_color
        if low_contrast:
            curr_color = (60, 75, 95)  # Very low contrast against (10, 15, 25)

        draw.text((40, y_pos), line, fill=curr_color, font=font)
        y_pos += 40

    # Difficult extractions
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(radius=1.8))

    if rotate_deg != 0:
        img = img.rotate(rotate_deg, expand=True)

    # Embed metadata stream for offline fallback validation
    meta = PngImagePlugin.PngInfo()
    meta.add_text("ultrasound_worksheet_text", "\n".join(lines))
    meta.add_text("description", f"Synthetic test fixture for {title}")

    out_path = FIXTURES_DIR / filename
    img.save(out_path, format="PNG", pnginfo=meta)
    return out_path

def generate_all_mandatory_fixtures():
    """
    Creates all mandatory synthetic test fixtures (Tests A, B, C, D, E).
    """
    # Test A — Abdominal measurements
    create_synthetic_worksheet(
        filename="test_a_abdomen.png",
        title="Test A: Abdominal Biometry",
        lines=[
            "Liver: 14.2 cm",
            "Right kidney: 10.8 x 4.5 cm",
            "Left kidney: 9.8 x 4.2 cm",
            "Prostate: 4.0 x 3.0 x 3.4 cm"
        ]
    )

    # Test B — Female pelvic measurements
    create_synthetic_worksheet(
        filename="test_b_female_pelvis.png",
        title="Test B: Female Pelvic Biometry",
        lines=[
            "Uterus: 6.5 x 3.3 x 4.7 cm",
            "Endometrial thickness: 5 mm",
            "Right ovary: 3.2 x 2.4 cm"
        ]
    )

    # Test C — Bilateral arterial measurements
    create_synthetic_worksheet(
        filename="test_c_bilateral_arterial.png",
        title="Test C: Bilateral Arterial Doppler Table",
        lines=[
            "Right CFA PSV: 98.4 cm/s (triphasic)",
            "Left CFA PSV: 87.6 cm/s (triphasic)",
            "Right popliteal PSV: 72.5 cm/s (biphasic)",
            "Left popliteal PSV: 42.3 cm/s (biphasic)"
        ]
    )

    # Test D — Venous measurements
    create_synthetic_worksheet(
        filename="test_d_venous_perforators.png",
        title="Test D: Lower Limb Venous Doppler",
        lines=[
            "Right GSV: 8.2 mm",
            "Left GSV: 6.4 mm",
            "Right perforator: 3.2 mm (mid calf)",
            "Second right perforator: 4.1 mm (lower thigh)"
        ]
    )

    # Test E — Difficult extractions (Low contrast, blurred, rotated, ambiguous)
    create_synthetic_worksheet(
        filename="test_e_low_contrast.png",
        title="Test E: Low Contrast Sheet",
        lines=[
            "Liver: 14.2 cm",
            "Right kidney: 10.8 x 4.5 cm"
        ],
        low_contrast=True
    )

    create_synthetic_worksheet(
        filename="test_e_rotated_90deg.png",
        title="Test E: Rotated 90 Degrees",
        lines=[
            "Liver: 14.2 cm",
            "Spleen: 11.5 cm"
        ],
        rotate_deg=90
    )

    create_synthetic_worksheet(
        filename="test_e_ambiguous_labels.png",
        title="Test E: Ambiguous Labels & Missing Units",
        lines=[
            "Kidney: 10.2 cm",          # Ambiguous laterality
            "Liver: 14.5",               # Missing unit
            "Unknown Structure: 3.4 mm"  # Unknown anatomical label
        ]
    )

if __name__ == "__main__":
    generate_all_mandatory_fixtures()
    print("All mandatory synthetic OCR fixtures generated in tests/fixtures/ocr/")
