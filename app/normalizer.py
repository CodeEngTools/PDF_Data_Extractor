# app/normalizer.py
import re


def normalize_text(raw: str) -> str:
    """
    Normaliza texto extraído de PDFs:
    - Colapsa caracteres repetidos (LLLL -> L, eeee -> e).
    - Limpia espacios repetidos y líneas vacías.
    - Quita caracteres no imprimibles.
    """

    # 1) Colapsar caracteres repetidos >= 3 veces
    def _collapse(match: re.Match) -> str:
        char = match.group(1)
        return char  # si quisieras permitir doble letra: return char * 2

    text = re.sub(r"(.)\1{2,}", _collapse, raw)

    # 2) Normalizar espacios
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)

    # 3) Quitar no imprimibles
    text = "".join(c for c in text if c.isprintable() or c in "\n\t")

    return text