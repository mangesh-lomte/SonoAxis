import re
from typing import Optional, Tuple, List

# Organ and Vascular anatomical patterns with strict priority order
ORGAN_PATTERNS = [
    # Explicit Clinical Metadata & Recommendations
    ("clinical_profile", re.compile(r"\b(clinical\s+profile|indication|chief\s+complaint|history\s+of|h/o)\b", re.IGNORECASE)),
    ("recommendations", re.compile(r"\b(adv|advice|advise|recommendations?|further\s+work\s*up|clinical\s+correlation)\b", re.IGNORECASE)),
    ("impression", re.compile(r"\b(impression|conclusions?|opinions?|summary)\b", re.IGNORECASE)),
    ("technique", re.compile(r"\b(real\s+time\s+scan|colour\s+flow\s+mapping|pulsed\s+doppler\s+analysis|examined\s+from\s+the\s+groin)\b", re.IGNORECASE)),

    # Venous Doppler Anatomy
    ("perforators", re.compile(r"\b(incompetent\s+perforators?|perforators?|perforating\s+veins?)\b", re.IGNORECASE)),
    ("varicosities", re.compile(r"\b(varicosities|varicosity|varicose\s+veins?|dilated\s+superficial\s+veins?|tortuous\s+veins?)\b", re.IGNORECASE)),
    ("junctions", re.compile(r"\b(sapheno-?femoral|sapheno-?popliteal|sfj|spj|valsalva)\b", re.IGNORECASE)),
    ("gsv", re.compile(r"\b(great\s+saphenous\s+vein|great\s+saphenous|gsv|long\s+saphenous\s+vein)\b", re.IGNORECASE)),
    ("ssv", re.compile(r"\b(short\s+saphenous\s+vein|small\s+saphenous\s+vein|short\s+saphenous|ssv)\b", re.IGNORECASE)),
    ("superficial_thrombosis", re.compile(r"\b(superficial\s+(?:vein\s+)?thrombosis|superficial\s+thrombophlebitis|svt)\b", re.IGNORECASE)),
    ("compressibility_thrombosis", re.compile(r"\b(deep\s+venous\s+thrombosis|dvt|venous\s+thrombosis|compressibility|flow\s+accentuation|calf\s+pressure)\b", re.IGNORECASE)),
    ("deep_venous_thigh", re.compile(r"\b(common\s+femoral(?:\s+veins?)?|cfv|superficial\s+femoral(?:\s+veins?)?|sfv|femoral\s+veins?|popliteal\s+veins?)\b", re.IGNORECASE)),
    ("deep_venous_calf", re.compile(r"\b(peroneal(?:\s+veins?)?|anterior\s+tibial(?:\s+veins?)?|posterior\s+tibial(?:\s+veins?)?|calf\s+veins?|atv|ptv)\b", re.IGNORECASE)),
    ("edema", re.compile(r"\b(subcutaneous\s+(?:tissue\s+)?edema|limb\s+edema|tissue\s+edema)\b", re.IGNORECASE)),
    ("lymph_nodes", re.compile(r"\b(inguinal\s+lymph\s+nodes?|groin\s+nodes?|inguinal\s+lymphadenopathy)\b", re.IGNORECASE)),

    # Arterial Doppler Anatomy & Findings
    ("atherosclerosis", re.compile(r"\b(atherosclerotic|calcification|atheroma|plaque|luminal\s+narrowing|luminal\s+compromise|stenosis|pre-?stenotic)\b", re.IGNORECASE)),
    ("thrombosis", re.compile(r"\b(complete\s+thrombus|arterial\s+thrombus|thrombus|occluded|occlusion|absent\s+color\s+flow|attenuated\s+flow)\b", re.IGNORECASE)),
    ("arterial_findings", re.compile(r"\b(triphasic|biphasic|monophasic|aliasing|waveforms?|spectral\s+analysis|pulsed\s+doppler|psv|peak\s+systolic\s+velocity|cfa|sfa|dfa|popliteal\s+artery|anterior\s+tibial\s+artery|posterior\s+tibial\s+artery|dorsalis\s+pedis)\b", re.IGNORECASE)),

    # Abdomen & Pelvis Organs
    ("right_kidney", re.compile(r"\b(right\s+kidney|rt\s+kidney|right\s+renal|rt\s+renal)\b", re.IGNORECASE)),
    ("left_kidney", re.compile(r"\b(left\s+kidney|lt\s+kidney|left\s+renal|lt\s+renal)\b", re.IGNORECASE)),
    ("kidneys_common", re.compile(r"\b(both\s+kidneys|bilateral\s+kidneys|either\s+kidney|kidneys|corticomedullary(?:\s+differentiation)?|hydronephrosis|hydroureteronephrosis|pelvicalyceal)\b", re.IGNORECASE)),
    ("liver", re.compile(r"\b(liver|hepatic|portal\s+vein|intrahepatic)\b", re.IGNORECASE)),
    ("gall_bladder", re.compile(r"\b(gall\s*bladder|gb|cholecyst|gallstones?|gall\s+stones?|pericholecystic|cholelithiasis)\b", re.IGNORECASE)),
    ("cbd", re.compile(r"\b(cbd|common\s+bile\s+duct|biliary\s+duct)\b", re.IGNORECASE)),
    ("pancreas", re.compile(r"\b(pancreas|pancreatic|pancreatic\s+duct)\b", re.IGNORECASE)),
    ("retroperitoneum", re.compile(r"\b(retroperitoneum|retroperitoneal(?:\s+lymph\s*nodes?|\s+lymphadenopathy)?|aorta|ivc|inferior\s+vena\s+cava|lymphadenopathy|para-?aortic)\b", re.IGNORECASE)),
    ("spleen", re.compile(r"\b(spleen|splenic|splenic\s+vein)\b", re.IGNORECASE)),
    ("urinary_bladder", re.compile(r"\b(urinary\s+bladder|bladder|ub|post\s+void\s+residual)\b", re.IGNORECASE)),
    ("prostate", re.compile(r"\b(prostate|prostatic|prostate\s+gland)\b", re.IGNORECASE)),
    ("endometrium", re.compile(r"\b(endometrium|endometrial|endometrial\s+thickness|et)\b", re.IGNORECASE)),
    ("uterus", re.compile(r"\b(uterus|uterine|myometrium|myometrial|cervix)\b", re.IGNORECASE)),
    ("right_ovary", re.compile(r"\b(right\s+ovary|rt\s+ovary|right\s+adnexa|rt\s+adnexa)\b", re.IGNORECASE)),
    ("left_ovary", re.compile(r"\b(left\s+ovary|lt\s+ovary|left\s+adnexa|lt\s+adnexa)\b", re.IGNORECASE)),
    ("ovaries_bilateral", re.compile(r"\b(both\s+ovaries|bilateral\s+ovaries|either\s+ovary|ovaries|adnexa|adnexal)\b", re.IGNORECASE)),
    ("bowel", re.compile(r"\b(bowel\s+loops?|bowel|gut|appendix|iliac\s+fossa)\b", re.IGNORECASE)),
    ("peritoneal_cavity", re.compile(r"\b(free\s+fluid|peritoneal\s+cavity|pelvic\s+fluid|ascites|pouch\s+of\s+douglas)\b", re.IGNORECASE))
]

VENOUS_ONLY_KEYS = {
    "perforators", "varicosities", "junctions", "gsv", "ssv",
    "superficial_thrombosis", "compressibility_thrombosis",
    "deep_venous_thigh", "deep_venous_calf", "edema", "lymph_nodes",
}
ARTERIAL_ONLY_KEYS = {
    "atherosclerosis", "thrombosis", "arterial_findings",
}
VASCULAR_ONLY_KEYS = VENOUS_ONLY_KEYS | ARTERIAL_ONLY_KEYS


def identify_organ(text: str, template_category: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Identifies the primary organ or vascular section key from text.
    Returns (organ_key, matched_term) or (None, None).
    """
    text_lower = text.lower()
    cat = (template_category or "").lower()
    for organ_key, pattern in ORGAN_PATTERNS:
        if cat == "abdomen_pelvis" and organ_key in VASCULAR_ONLY_KEYS:
            continue
        if cat == "arterial_doppler" and organ_key in VENOUS_ONLY_KEYS:
            continue
        if cat == "venous_doppler" and organ_key in {"arterial_findings"}:
            continue
        # Guard: never match generic 'common femoral' / 'superficial femoral' as veins when 'artery'/'arteries' appears
        if organ_key in {"deep_venous_thigh", "deep_venous_calf"} and re.search(r"\barter(?:y|ies)\b", text_lower) and not re.search(r"\bveins?\b", text_lower):
            continue
        match = pattern.search(text_lower)
        if match:
            # Special check: If "kidney" alone is matched but text contains "right" or "left"
            if organ_key == "kidneys_common":
                if re.search(r"\b(?:either|both|bilateral)\b", text_lower):
                    return "kidneys_common", match.group(0)
                if re.search(r"\bright\b", text_lower):
                    return "right_kidney", "right kidney"
                if re.search(r"\bleft\b", text_lower):
                    return "left_kidney", "left kidney"
            # Special check: If "ovaries" alone is matched but text has "right" or "left"
            if organ_key == "ovaries_bilateral":
                if re.search(r"\b(?:either|both|bilateral)\b", text_lower):
                    return "ovaries_bilateral", match.group(0)
                if re.search(r"\bright\b", text_lower):
                    return "right_ovary", "right ovary"
                if re.search(r"\bleft\b", text_lower):
                    return "left_ovary", "left ovary"
            return organ_key, match.group(0)
    return None, None

def check_incompatible_anatomy(
    organ_key: str,
    template_gender: str,
    template_category: Optional[str] = "abdomen_pelvis"
) -> bool:
    """
    Checks if an anatomical finding is biologically or clinically incompatible with the template.
    e.g., prostate in female, uterus in male, or liver/prostate in vascular doppler.
    """
    category = (template_category or "abdomen_pelvis").lower()

    # In vascular studies, abdominal visceral organs are incompatible
    if category in ["venous_doppler", "arterial_doppler", "arteriovenous_doppler"]:
        visceral_abdominal = [
            "liver", "gall_bladder", "cbd", "pancreas", "spleen",
            "right_kidney", "left_kidney", "kidneys_common",
            "urinary_bladder", "prostate", "uterus", "endometrium",
            "right_ovary", "left_ovary", "ovaries_bilateral", "bowel", "peritoneal_cavity"
        ]
        if organ_key in visceral_abdominal:
            return True

    # In abdominal studies, gender rules apply
    if category == "abdomen_pelvis":
        if template_gender.lower() == "male":
            if organ_key in ["uterus", "endometrium", "right_ovary", "left_ovary", "ovaries_bilateral"]:
                return True
        elif template_gender.lower() == "female":
            if organ_key in ["prostate"]:
                return True

    return False
