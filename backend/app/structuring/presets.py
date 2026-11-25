from typing import Dict, Any, List, Optional

NORMAL_PRESETS_CATALOG: Dict[str, Dict[str, Any]] = {
    # Abdominal Presets
    "liver": {
        "id": "preset-liver-normal",
        "section_key": "liver",
        "name": "Normal Liver",
        "category": "abdomen_pelvis",
        "text": "Liver is normal in size, smooth in contour and homogeneous in parenchymal echotexture. No focal hepatic mass, cyst, or intrahepatic biliary radicle dilatation.",
        "clinical_rationale": "Standard institutional negative description of hepatic parenchyma and biliary tree."
    },
    "gall_bladder": {
        "id": "preset-gb-normal",
        "section_key": "gall_bladder",
        "name": "Normal Gall Bladder & CBD",
        "category": "abdomen_pelvis",
        "text": "Gall bladder is well distended. Lumen is clear without calculus, sludge, or mass lesion. Gallbladder wall thickness is within normal physiological limits (<3 mm). No pericholecystic fluid or Murphy's sign.",
        "clinical_rationale": "Standard institutional negative description of gallbladder and biliary lumen."
    },
    "cbd": {
        "id": "preset-cbd-normal",
        "section_key": "cbd",
        "name": "Normal CBD",
        "category": "abdomen_pelvis",
        "text": "Common bile duct is normal in calibre, measuring within physiological limits (<6 mm). No intraductal calculus or proximal dilatation.",
        "clinical_rationale": "Standard institutional negative description of common bile duct."
    },
    "pancreas": {
        "id": "preset-pancreas-normal",
        "section_key": "pancreas",
        "name": "Normal Pancreas",
        "category": "abdomen_pelvis",
        "text": "Pancreas is normal in size, contours, and parenchymal echogenicity. Main pancreatic duct is not dilated. No focal pancreatic mass, calcification, or peripancreatic fluid collection.",
        "clinical_rationale": "Standard institutional negative description of pancreas."
    },
    "spleen": {
        "id": "preset-spleen-normal",
        "section_key": "spleen",
        "name": "Normal Spleen",
        "category": "abdomen_pelvis",
        "text": "Spleen is normal in size and contours, measuring within normal limits (<12 cm span). Splenic parenchymal echotexture is homogeneous without focal lesion or splenic hilar varices.",
        "clinical_rationale": "Standard institutional negative description of splenic parenchyma."
    },
    "right_kidney": {
        "id": "preset-rk-normal",
        "section_key": "right_kidney",
        "name": "Normal Right Kidney",
        "category": "abdomen_pelvis",
        "text": "Right kidney is normal in size, location, and cortical echogenicity. Corticomedullary differentiation is well preserved. No calculus, hydronephrosis, or focal solid/cystic mass.",
        "clinical_rationale": "Standard institutional negative description of right renal parenchyma and collecting system."
    },
    "left_kidney": {
        "id": "preset-lk-normal",
        "section_key": "left_kidney",
        "name": "Normal Left Kidney",
        "category": "abdomen_pelvis",
        "text": "Left kidney is normal in size, location, and cortical echogenicity. Corticomedullary differentiation is well preserved. No calculus, hydronephrosis, or focal solid/cystic mass.",
        "clinical_rationale": "Standard institutional negative description of left renal parenchyma and collecting system."
    },
    "urinary_bladder": {
        "id": "preset-ub-normal",
        "section_key": "urinary_bladder",
        "name": "Normal Urinary Bladder",
        "category": "abdomen_pelvis",
        "text": "Urinary bladder is well distended with smooth, uniform wall thickness. Lumen is free of calculus, sediment, or intraluminal proliferative lesion.",
        "clinical_rationale": "Standard institutional negative description of distended bladder."
    },
    "prostate": {
        "id": "preset-prostate-normal",
        "section_key": "prostate",
        "name": "Normal Prostate",
        "category": "abdomen_pelvis",
        "text": "Prostate is normal in size and contours with homogeneous parenchymal echotexture. Prostatic capsule is intact without median lobe intravesical protrusion.",
        "clinical_rationale": "Standard institutional negative description of prostate."
    },
    "uterus": {
        "id": "preset-uterus-normal",
        "section_key": "uterus",
        "name": "Normal Uterus",
        "category": "abdomen_pelvis",
        "text": "Uterus is anteverted, normal in size, contours, and myometrial echogenicity. Endometrial cavity is regular and central without focal thickening. No focal myoma or adenomyosis.",
        "clinical_rationale": "Standard institutional negative description of uterus."
    },
    "endometrium": {
        "id": "preset-endo-normal",
        "section_key": "endometrium",
        "name": "Normal Endometrium",
        "category": "abdomen_pelvis",
        "text": "Endometrial stripe is uniform, central, and well defined, measuring within normal physiological limits for age. No polypoid lesion or fluid collection.",
        "clinical_rationale": "Standard institutional negative description of endometrium."
    },
    "right_ovary": {
        "id": "preset-ro-normal",
        "section_key": "right_ovary",
        "name": "Normal Right Ovary",
        "category": "abdomen_pelvis",
        "text": "Right ovary is normal in size and sonographic morphology with physiological peripheral follicles. No ovarian cyst, complex mass, or adnexal mass.",
        "clinical_rationale": "Standard institutional negative description of right adnexa."
    },
    "left_ovary": {
        "id": "preset-lo-normal",
        "section_key": "left_ovary",
        "name": "Normal Left Ovary",
        "category": "abdomen_pelvis",
        "text": "Left ovary is normal in size and sonographic morphology with physiological peripheral follicles. No ovarian cyst, complex mass, or adnexal mass.",
        "clinical_rationale": "Standard institutional negative description of left adnexa."
    },

    # Venous Doppler Presets
    "deep_venous_thigh": {
        "id": "preset-deep-veins-normal",
        "section_key": "deep_venous_thigh",
        "name": "Normal Deep Veins (Thigh & Popliteal)",
        "category": "venous_doppler",
        "text": "Common femoral, superficial femoral, and popliteal veins demonstrate normal wall compliance, complete luminal compressibility, and normal spontaneous phasic respiratory flow without evidence of deep venous thrombosis (DVT).",
        "clinical_rationale": "Standard institutional negative description of proximal deep veins."
    },
    "deep_venous_calf": {
        "id": "preset-calf-veins-normal",
        "section_key": "deep_venous_calf",
        "name": "Normal Deep Veins (Calf)",
        "category": "venous_doppler",
        "text": "Peroneal, anterior tibial, and posterior tibial veins demonstrate normal luminal compressibility, patent color filling, and normal distal augmentation without calf vein thrombosis.",
        "clinical_rationale": "Standard institutional negative description of infrapopliteal deep veins."
    },
    "junctions": {
        "id": "preset-junctions-normal",
        "section_key": "junctions",
        "name": "Competent Saphenous Junctions",
        "category": "venous_doppler",
        "text": "Saphenofemoral junction (SFJ) and saphenopopliteal junction (SPJ) are competent with prompt valvular closure and no pathological retrograde reflux (<0.5 sec) upon Valsalva maneuver or distal augmentation.",
        "clinical_rationale": "Standard institutional negative description of superficial venous junctions."
    },
    "gsv": {
        "id": "preset-gsv-normal",
        "section_key": "gsv",
        "name": "Normal Great Saphenous Vein",
        "category": "venous_doppler",
        "text": "Great saphenous vein (GSV) demonstrates normal caliber throughout thigh and calf segments with competent valves and no evidence of significant reflux or superficial thrombophlebitis.",
        "clinical_rationale": "Standard institutional negative description of great saphenous vein."
    },
    "perforators": {
        "id": "preset-perforators-normal",
        "section_key": "perforators",
        "name": "No Incompetent Perforators",
        "category": "venous_doppler",
        "text": "No dilated or incompetent fascial perforating veins identified in thigh, calf, or medial ankle regions.",
        "clinical_rationale": "Standard institutional negative description of perforators."
    },

    # Arterial Doppler Presets
    "arterial_findings": {
        "id": "preset-arterial-tree-normal",
        "section_key": "arterial_findings",
        "name": "Normal Triphasic Arterial Flow",
        "category": "arterial_doppler",
        "text": "Common femoral, superficial femoral, deep femoral, popliteal, anterior tibial, posterior tibial, and dorsalis pedis arteries demonstrate patent lumens with smooth intimal margins and normal high-resistance triphasic Doppler flow waveforms without hemodynamically significant stenosis or occlusion.",
        "clinical_rationale": "Standard institutional negative description of lower extremity arterial tree."
    }
}

def get_presets_for_category(category: str) -> List[Dict[str, Any]]:
    """Returns available normal presets for an examination category."""
    results = []
    for item in NORMAL_PRESETS_CATALOG.values():
        if item.get("category") == category or category == "all":
            results.append(item)
    return results

def get_preset_for_section(section_key: str) -> Optional[Dict[str, Any]]:
    """Retrieves specific normal preset by section key."""
    return NORMAL_PRESETS_CATALOG.get(section_key)
