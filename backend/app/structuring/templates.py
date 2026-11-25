from typing import Dict, Any, List

# Standard Arterial Segments for Doppler Tables
STANDARD_ARTERIAL_SEGMENTS: List[Dict[str, str]] = [
    {"key": "cfa", "name": "Common femoral artery"},
    {"key": "sfa", "name": "Superficial femoral artery"},
    {"key": "dfa", "name": "Deep femoral artery"},
    {"key": "popliteal", "name": "Popliteal artery"},
    {"key": "ata", "name": "Anterior tibial artery"},
    {"key": "pta", "name": "Posterior tibial artery"},
    {"key": "dpa", "name": "Dorsalis pedis artery"}
]

MALE_CANONICAL_SECTIONS: List[Dict[str, Any]] = [
    {"order": 1, "key": "liver", "label": "Liver", "heading": "Liver: "},
    {"order": 2, "key": "gall_bladder", "label": "Gall Bladder", "heading": "Gall Bladder: "},
    {"order": 3, "key": "cbd", "label": "CBD", "heading": ""},
    {"order": 4, "key": "pancreas", "label": "Pancreas", "heading": "Pancreas: "},
    {"order": 5, "key": "retroperitoneum", "label": "Retroperitoneum", "heading": "Retroperitoneum: "},
    {"order": 6, "key": "spleen", "label": "Spleen", "heading": "Spleen: "},
    {"order": 7, "key": "right_kidney", "label": "Right Kidney", "heading": "Right Kidney: "},
    {"order": 8, "key": "left_kidney", "label": "Left Kidney", "heading": "Left Kidney: "},
    {"order": 9, "key": "kidneys_common", "label": "Kidneys (Summary)", "heading": ""},
    {"order": 10, "key": "urinary_bladder", "label": "Urinary Bladder", "heading": "Urinary Bladder: "},
    {"order": 11, "key": "prostate", "label": "Prostate", "heading": "Prostate: "},
    {"order": 12, "key": "bowel", "label": "Bowel Loops", "heading": ""},
    {"order": 13, "key": "peritoneal_cavity", "label": "Peritoneal Cavity", "heading": ""},
    {"order": 14, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "}
]

FEMALE_CANONICAL_SECTIONS: List[Dict[str, Any]] = [
    {"order": 1, "key": "liver", "label": "Liver", "heading": "Liver: "},
    {"order": 2, "key": "gall_bladder", "label": "Gall Bladder", "heading": "Gall Bladder: "},
    {"order": 3, "key": "cbd", "label": "CBD", "heading": ""},
    {"order": 4, "key": "pancreas", "label": "Pancreas", "heading": "Pancreas: "},
    {"order": 5, "key": "retroperitoneum", "label": "Retroperitoneum", "heading": "Retroperitoneum: "},
    {"order": 6, "key": "spleen", "label": "Spleen", "heading": "Spleen: "},
    {"order": 7, "key": "right_kidney", "label": "Right Kidney", "heading": "Right Kidney: "},
    {"order": 8, "key": "left_kidney", "label": "Left Kidney", "heading": "Left Kidney: "},
    {"order": 9, "key": "kidneys_common", "label": "Kidneys (Summary)", "heading": ""},
    {"order": 10, "key": "urinary_bladder", "label": "Urinary Bladder", "heading": "Urinary Bladder: "},
    {"order": 11, "key": "uterus", "label": "Uterus", "heading": "Uterus: "},
    {"order": 12, "key": "endometrium", "label": "Endometrium", "heading": ""},
    {"order": 13, "key": "right_ovary", "label": "Right Ovary", "heading": "Right Ovary: "},
    {"order": 14, "key": "left_ovary", "label": "Left Ovary", "heading": "Left Ovary: "},
    {"order": 15, "key": "ovaries_bilateral", "label": "Bilateral Ovaries", "heading": ""},
    {"order": 16, "key": "bowel", "label": "Bowel Loops", "heading": ""},
    {"order": 17, "key": "peritoneal_cavity", "label": "Peritoneal Cavity", "heading": ""},
    {"order": 18, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "}
]

VENOUS_UNILATERAL_SECTIONS: List[Dict[str, Any]] = [
    {"order": 1, "key": "clinical_profile", "label": "Clinical Profile", "heading": "Clinical Profile: "},
    {"order": 2, "key": "technique", "label": "Technique & Protocol", "heading": ""},
    {"order": 3, "key": "deep_venous_thigh", "label": "Femoral & Popliteal Veins", "heading": "Common femoral, superficial femoral and popliteal veins: "},
    {"order": 4, "key": "deep_venous_calf", "label": "Calf Veins", "heading": "Peroneal, anterior and posterior tibial veins: "},
    {"order": 5, "key": "compressibility_thrombosis", "label": "Thrombosis & Compressibility", "heading": "Deep Venous Thrombosis: "},
    {"order": 6, "key": "junctions", "label": "Saphenofemoral & Saphenopopliteal Junctions", "heading": "Saphenofemoral & Saphenopopliteal junctions: "},
    {"order": 7, "key": "gsv", "label": "Great Saphenous Vein (GSV)", "heading": "Great Saphenous Vein (GSV): "},
    {"order": 8, "key": "varicosities", "label": "Superficial Varicosities", "heading": "Varicosities: "},
    {"order": 9, "key": "perforators", "label": "Incompetent Perforators", "heading": "Incompetent Perforators: "},
    {"order": 10, "key": "ssv", "label": "Short Saphenous Vein (SSV)", "heading": "Short Saphenous Vein (SSV): "},
    {"order": 11, "key": "superficial_thrombosis", "label": "Superficial Vein Thrombosis", "heading": "Superficial Vein Thrombosis: "},
    {"order": 12, "key": "edema", "label": "Subcutaneous Edema", "heading": "Subcutaneous Edema: "},
    {"order": 13, "key": "lymph_nodes", "label": "Inguinal Lymph Nodes", "heading": "Inguinal Lymph Nodes: "},
    {"order": 14, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "},
    {"order": 15, "key": "recommendations", "label": "Recommendations", "heading": "ADV: "}
]

VENOUS_BILATERAL_SECTIONS: List[Dict[str, Any]] = [
    {"order": 1, "key": "clinical_profile", "label": "Clinical Profile", "heading": "Clinical Profile: "},
    {"order": 2, "key": "technique", "label": "Technique & Protocol", "heading": ""},
    {"order": 3, "key": "deep_venous_thigh", "label": "Bilateral Femoral & Popliteal Veins", "heading": "Common femoral, superficial femoral and popliteal veins: "},
    {"order": 4, "key": "deep_venous_calf", "label": "Bilateral Calf Veins", "heading": "Peroneal, anterior and posterior tibial veins: "},
    {"order": 5, "key": "compressibility_thrombosis", "label": "Thrombosis & Compressibility", "heading": "Deep Venous Thrombosis: "},
    {"order": 6, "key": "junctions", "label": "Saphenofemoral & Saphenopopliteal Junctions", "heading": "Saphenofemoral & Saphenopopliteal junctions: "},
    {"order": 7, "key": "gsv", "label": "Great Saphenous Vein (GSV)", "heading": "Great Saphenous Vein (GSV): "},
    {"order": 8, "key": "varicosities", "label": "Superficial Varicosities", "heading": "Varicosities: "},
    {"order": 9, "key": "perforators", "label": "Incompetent Perforators", "heading": "Incompetent Perforators: "},
    {"order": 10, "key": "ssv", "label": "Short Saphenous Vein (SSV)", "heading": "Short Saphenous Vein (SSV): "},
    {"order": 11, "key": "superficial_thrombosis", "label": "Superficial Vein Thrombosis", "heading": "Superficial Vein Thrombosis: "},
    {"order": 12, "key": "edema", "label": "Subcutaneous Edema", "heading": "Subcutaneous Edema: "},
    {"order": 13, "key": "lymph_nodes", "label": "Inguinal Lymph Nodes", "heading": "Inguinal Lymph Nodes: "},
    {"order": 14, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "},
    {"order": 15, "key": "recommendations", "label": "Recommendations", "heading": "ADV: "}
]

ARTERIAL_UNILATERAL_SECTIONS: List[Dict[str, Any]] = [
    {"order": 1, "key": "clinical_profile", "label": "Clinical Profile", "heading": "Clinical Profile: "},
    {"order": 2, "key": "technique", "label": "Examination Protocol", "heading": ""},
    {"order": 3, "key": "atherosclerosis", "label": "Atherosclerotic Changes / Plaque", "heading": "Atherosclerotic Changes: "},
    {"order": 4, "key": "arterial_findings", "label": "Arterial Findings", "heading": "Arterial Flow & Waveforms: "},
    {"order": 5, "key": "measurement_table", "label": "Arterial Measurement Table", "heading": "ARTERY  PSV (cm/sec)  FLOW PATTERN"},
    {"order": 6, "key": "thrombosis", "label": "Thrombus / Occlusion", "heading": "Arterial Thrombus: "},
    {"order": 7, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "},
    {"order": 8, "key": "recommendations", "label": "Recommendations", "heading": "ADV: "}
]

ARTERIAL_BILATERAL_SECTIONS: List[Dict[str, Any]] = [
    {"order": 1, "key": "clinical_profile", "label": "Clinical Profile", "heading": "Clinical Profile: "},
    {"order": 2, "key": "technique", "label": "Examination Protocol", "heading": ""},
    {"order": 3, "key": "atherosclerosis", "label": "Atherosclerotic Changes / Plaque", "heading": "Atherosclerotic Changes: "},
    {"order": 4, "key": "arterial_findings", "label": "Bilateral Arterial Findings", "heading": "Arterial Flow & Waveforms: "},
    {"order": 5, "key": "measurement_table", "label": "Bilateral Arterial Measurement Table", "heading": "ARTERY  PSV Right (cm/s)  PSV Left (cm/s)  Flow Right  Flow Left"},
    {"order": 6, "key": "thrombosis", "label": "Thrombus / Occlusion", "heading": "Arterial Thrombus: "},
    {"order": 7, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "},
    {"order": 8, "key": "recommendations", "label": "Recommendations", "heading": "ADV: "}
]

AV_UNILATERAL_SECTIONS: List[Dict[str, Any]] = [
    {"order": 1, "key": "clinical_profile", "label": "Clinical Profile", "heading": "Clinical Profile: "},
    {"order": 2, "key": "technique", "label": "Examination Protocol", "heading": ""},
    {"order": 3, "key": "measurement_table", "label": "Arterial Doppler Table", "heading": "ARTERY  PSV (cm/sec)  FLOW PATTERN"},
    {"order": 4, "key": "arterial_findings", "label": "Arterial System", "heading": "Arterial System: "},
    {"order": 5, "key": "deep_venous_thigh", "label": "Deep Venous System", "heading": "Deep Veins: "},
    {"order": 6, "key": "deep_venous_calf", "label": "Calf Venous System", "heading": "Calf Veins: "},
    {"order": 7, "key": "junctions", "label": "Superficial Venous & Junctions", "heading": "Superficial Veins: "},
    {"order": 8, "key": "thrombosis", "label": "Thrombosis Evaluation", "heading": "Thrombosis: "},
    {"order": 9, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "},
    {"order": 10, "key": "recommendations", "label": "Recommendations", "heading": "ADV: "}
]

AV_BILATERAL_SECTIONS: List[Dict[str, Any]] = [
    {"order": 1, "key": "clinical_profile", "label": "Clinical Profile", "heading": "Clinical Profile: "},
    {"order": 2, "key": "technique", "label": "Examination Protocol", "heading": ""},
    {"order": 3, "key": "arterial_findings", "label": "Bilateral Arterial System", "heading": "Arterial System: "},
    {"order": 4, "key": "measurement_table", "label": "Bilateral Arterial Doppler Table", "heading": "ARTERY  PSV Right (cm/s)  PSV Left (cm/s)  Flow Right  Flow Left"},
    {"order": 5, "key": "venous_findings", "label": "Bilateral Venous System", "heading": "Venous System: "},
    {"order": 6, "key": "thrombosis", "label": "Venous / Arterial Thrombosis", "heading": "Thrombosis: "},
    {"order": 7, "key": "impression", "label": "Impression", "heading": "IMPRESSION: "},
    {"order": 8, "key": "recommendations", "label": "Recommendations", "heading": "ADV: "}
]

TEMPLATES_CATALOG: Dict[str, Dict[str, Any]] = {
    # 1. Abdomen & Pelvis (Male)
    "usg-abdomen-pelvis-male": {
        "id": "usg-abdomen-pelvis-male",
        "name": "USG Abdomen & Pelvis (Male)",
        "category": "abdomen_pelvis",
        "laterality": "not_applicable",
        "gender": "Male",
        "file_name": "abd male-new.docx",
        "legacy_file_name": "male-abdomen-pelvis.docx",
        "table_type": "none",
        "sections": MALE_CANONICAL_SECTIONS,
        "incompatible_organs": ["uterus", "endometrium", "ovaries", "right_ovary", "left_ovary", "ovaries_bilateral", "adnexa"]
    },
    # 2. Abdomen & Pelvis (Female)
    "usg-abdomen-pelvis-female": {
        "id": "usg-abdomen-pelvis-female",
        "name": "USG Abdomen & Pelvis (Female)",
        "category": "abdomen_pelvis",
        "laterality": "not_applicable",
        "gender": "Female",
        "file_name": "abdo female1-new.docx",
        "legacy_file_name": "female-abdomen-pelvis.docx",
        "table_type": "none",
        "sections": FEMALE_CANONICAL_SECTIONS,
        "incompatible_organs": ["prostate"]
    },
    # 3. Left Venous Doppler with Varicosities
    "usg-doppler-venous-left-varicose": {
        "id": "usg-doppler-venous-left-varicose",
        "name": "USG Left Lower Limb Venous Doppler (Varicosities)",
        "category": "venous_doppler",
        "laterality": "left",
        "gender": "Any",
        "file_name": "Varicosities doppler study.docx",
        "table_type": "none",
        "sections": VENOUS_UNILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 4. Right Venous Doppler with Varicosities
    "usg-doppler-venous-right-varicose": {
        "id": "usg-doppler-venous-right-varicose",
        "name": "USG Right Lower Limb Venous Doppler (Varicosities)",
        "category": "venous_doppler",
        "laterality": "right",
        "gender": "Any",
        "file_name": "varicose veins VENOUS (1).docx",
        "table_type": "none",
        "sections": VENOUS_UNILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 5. Left Venous Thrombosis
    "usg-doppler-venous-left-thrombosis": {
        "id": "usg-doppler-venous-left-thrombosis",
        "name": "USG Left Lower Limb Venous Doppler (Thrombosis)",
        "category": "venous_doppler",
        "laterality": "left",
        "gender": "Any",
        "file_name": "venous thrombosis..docx",
        "table_type": "none",
        "sections": VENOUS_UNILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 6. Bilateral Normal Venous Doppler
    "usg-doppler-venous-bilateral-normal": {
        "id": "usg-doppler-venous-bilateral-normal",
        "name": "USG Bilateral Lower Limb Venous Doppler (Normal)",
        "category": "venous_doppler",
        "laterality": "bilateral",
        "gender": "Any",
        "file_name": "Bilateral LL venous doppler normal.docx",
        "table_type": "none",
        "sections": VENOUS_BILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 7. Bilateral Venous Doppler with Varicosities
    "usg-doppler-venous-bilateral-varicose": {
        "id": "usg-doppler-venous-bilateral-varicose",
        "name": "USG Bilateral Lower Limb Venous Doppler (Varicosities)",
        "category": "venous_doppler",
        "laterality": "bilateral",
        "gender": "Any",
        "file_name": "Bilateral LL venous with varicosities.docx",
        "table_type": "none",
        "sections": VENOUS_BILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 8. Detailed Bilateral Varicose Venous Doppler
    "usg-doppler-venous-bilateral-detailed": {
        "id": "usg-doppler-venous-bilateral-detailed",
        "name": "USG Bilateral Lower Limb Venous Doppler (Detailed Varicose)",
        "category": "venous_doppler",
        "laterality": "bilateral",
        "gender": "Any",
        "file_name": "bilateral lower limb varicose venous doppler.docx",
        "table_type": "none",
        "sections": VENOUS_BILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 9. Right Venous DVT Follow-up
    "usg-doppler-venous-right-dvt": {
        "id": "usg-doppler-venous-right-dvt",
        "name": "USG Right Lower Limb Venous Doppler (DVT Follow-up)",
        "category": "venous_doppler",
        "laterality": "right",
        "gender": "Any",
        "file_name": "LL venous doppler- DVT.docx",
        "table_type": "none",
        "sections": VENOUS_UNILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 10. Right Normal Venous Doppler
    "usg-doppler-venous-right-normal": {
        "id": "usg-doppler-venous-right-normal",
        "name": "USG Right Lower Limb Venous Doppler (Normal)",
        "category": "venous_doppler",
        "laterality": "right",
        "gender": "Any",
        "file_name": "Right LL Venous doppler study Normal - Copy.docx",
        "table_type": "none",
        "sections": VENOUS_UNILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 11. Right Normal Arterial Doppler
    "usg-doppler-arterial-right-normal": {
        "id": "usg-doppler-arterial-right-normal",
        "name": "USG Right Lower Limb Arterial Doppler (Normal)",
        "category": "arterial_doppler",
        "laterality": "right",
        "gender": "Any",
        "file_name": "Right LL arterial doppler.docx",
        "table_type": "arterial_3col_table",
        "sections": ARTERIAL_UNILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 12. Bilateral Normal Arterial Doppler
    "usg-doppler-arterial-bilateral-normal": {
        "id": "usg-doppler-arterial-bilateral-normal",
        "name": "USG Bilateral Lower Limb Arterial Doppler (Normal)",
        "category": "arterial_doppler",
        "laterality": "bilateral",
        "gender": "Any",
        "file_name": "BILATERAL LOWER LIMB ARTERIO DOPPLER STUDY.docx",
        "table_type": "arterial_5col_table",
        "sections": ARTERIAL_BILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 13. Bilateral Arterial Doppler (Thrombus)
    "usg-doppler-arterial-bilateral-thrombus": {
        "id": "usg-doppler-arterial-bilateral-thrombus",
        "name": "USG Bilateral Lower Limb Arterial Doppler (Thrombus)",
        "category": "arterial_doppler",
        "laterality": "bilateral",
        "gender": "Any",
        "file_name": "compete thrombus ARTERIAL  LL.docx",
        "table_type": "arterial_5col_tabs",
        "sections": ARTERIAL_BILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 14. Right Arterial Doppler (PVD)
    "usg-doppler-arterial-right-pvd": {
        "id": "usg-doppler-arterial-right-pvd",
        "name": "USG Right Lower Limb Arterial Doppler (PVD)",
        "category": "arterial_doppler",
        "laterality": "right",
        "gender": "Any",
        "file_name": "LOWER LIMB ARTERIALperipheral vascular disease.docx",
        "table_type": "arterial_3col_tabs",
        "sections": ARTERIAL_UNILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 15. Right Arteriovenous Doppler
    "usg-doppler-av-right": {
        "id": "usg-doppler-av-right",
        "name": "USG Right Lower Limb Arteriovenous Doppler",
        "category": "arteriovenous_doppler",
        "laterality": "right",
        "gender": "Any",
        "file_name": "Right LL arterialvenos doppler.docx",
        "table_type": "arterial_3col_tabs",
        "sections": AV_UNILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    },
    # 16. Bilateral Arteriovenous Doppler (Thrombosis)
    "usg-doppler-av-bilateral-thrombosis": {
        "id": "usg-doppler-av-bilateral-thrombosis",
        "name": "USG Bilateral Lower Limb Arteriovenous Doppler (Thrombosis)",
        "category": "arteriovenous_doppler",
        "laterality": "bilateral",
        "gender": "Any",
        "file_name": "partial thrombosis.docx",
        "table_type": "none",
        "sections": AV_BILATERAL_SECTIONS,
        "incompatible_organs": ["liver", "gall_bladder", "pancreas", "spleen", "prostate", "uterus", "ovaries"]
    }
}

def get_template_def(template_id: str) -> Dict[str, Any]:
    if template_id in TEMPLATES_CATALOG:
        t = dict(TEMPLATES_CATALOG[template_id])
        if "status" not in t:
            t["status"] = "APPROVED"
        return t

    # Dynamic SQLite database lookup for imported and custom templates
    try:
        import json
        from backend.app.db.connection import get_db
        with get_db() as conn:
            row = conn.execute("SELECT * FROM examination_templates WHERE id = ?", (template_id,)).fetchone()
            if row:
                sections = json.loads(row["canonical_sections"]) if row["canonical_sections"] else []
                table_config = json.loads(row["table_config_json"]) if row["table_config_json"] else None
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "gender": row["gender"] or "Any",
                    "category": row["category"] or "custom",
                    "laterality": row["laterality"] or "not_applicable",
                    "file_name": row["file_name"],
                    "file_path": row["file_path"],
                    "table_type": row["table_type"] or "none",
                    "sections": sections,
                    "table_config": table_config,
                    "status": row["status"] or "APPROVED",
                    "version": row["version"] or 1,
                    "incompatible_organs": []
                }
    except Exception:
        pass

    return TEMPLATES_CATALOG["usg-abdomen-pelvis-male"]
