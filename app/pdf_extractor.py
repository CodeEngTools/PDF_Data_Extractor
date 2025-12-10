# app/pdf_extractor.py

import pdfplumber

# Intentamos importar pypdf para el fallback
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


def extract_pdf_text(path: str) -> str:
    """
    Extrae texto de un PDF con pdfplumber (pdfminer) y, si falla,
    hace fallback a pypdf si está disponible.

    Si ambos fallan o no hay texto útil, lanza RuntimeError.
    """

    # 1) Primer intento: pdfplumber
    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(pages)
        if text.strip():
            return text
    except Exception as e:
        print(f"[WARN] pdfplumber falló en {path}: {e}")

    # 2) Fallback: pypdf si está disponible
    if PdfReader is not None:
        try:
            reader = PdfReader(path)
            chunks = []
            for page in reader.pages:
                t = page.extract_text() or ""
                chunks.append(t)
            text = "\n".join(chunks)
            if text.strip():
                return text
        except Exception as e:
            raise RuntimeError(
                f"Todos los extractores fallaron para {path}: {e}"
            )

    # Si llegamos aquí, o no hay PdfReader o no hemos sacado texto útil
    if PdfReader is None:
        raise RuntimeError(
            f"pdfplumber falló y pypdf no está disponible para {path} "
            "(instala 'pypdf' en el venv)"
        )
    raise RuntimeError(f"No se pudo extraer texto de {path} (vacío tras ambos extractores)")