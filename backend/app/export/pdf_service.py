import os
import shutil
import tempfile
import subprocess
import logging
from typing import Dict, Any, Optional

from backend.app.export.preview_service import PreviewService

logger = logging.getLogger("sonovoice.export.pdf")

EDGE_SEARCH_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    shutil.which("msedge") or ""
]

class PDFExportService:
    @classmethod
    def get_edge_path(cls) -> Optional[str]:
        for p in EDGE_SEARCH_PATHS:
            if p and os.path.exists(p) and os.path.isfile(p):
                return p
        return None

    @classmethod
    def is_available(cls) -> bool:
        return cls.get_edge_path() is not None

    @classmethod
    def generate_pdf(cls, report_data: Dict[str, Any], timeout_seconds: int = 45) -> bytes:
        """
        Converts the canonical report HTML to high-fidelity PDF using headless Microsoft Edge.
        Ensures exact US Letter geometry and zero cost / zero external dependency.
        """
        edge_exe = cls.get_edge_path()
        if not edge_exe:
            raise RuntimeError(
                "Microsoft Edge executable not found. Headless PDF generation requires Microsoft Edge."
            )

        html_content = PreviewService.render_html(report_data)

        # Temporary files for HTML source and PDF output
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f_html:
            f_html.write(html_content)
            html_temp_path = f_html.name

        pdf_temp_path = html_temp_path.replace(".html", ".pdf")

        try:
            cmd = [
                edge_exe,
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_temp_path}",
                html_temp_path
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout_seconds,
                check=False
            )

            if res.returncode != 0:
                err_msg = res.stderr.decode("utf-8", errors="replace")
                logger.error(f"Edge headless PDF conversion failed (code {res.returncode}): {err_msg}")
                raise RuntimeError(f"Edge PDF generation failed with exit code {res.returncode}")

            if not os.path.exists(pdf_temp_path) or os.path.getsize(pdf_temp_path) == 0:
                raise RuntimeError("Edge produced empty or missing PDF output.")

            with open(pdf_temp_path, "rb") as f_pdf:
                pdf_bytes = f_pdf.read()

            return pdf_bytes

        finally:
            if os.path.exists(html_temp_path):
                try:
                    os.remove(html_temp_path)
                except Exception:
                    pass
            if os.path.exists(pdf_temp_path):
                try:
                    os.remove(pdf_temp_path)
                except Exception:
                    pass
