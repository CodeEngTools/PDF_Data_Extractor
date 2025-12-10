# app/main.py
import json
from dataclasses import asdict
from pathlib import Path
from typing import Union, List

from app.pdf_extractor import extract_pdf_text
from app.normalizer import normalize_text
from app.parsers import get_parser


def parse_invoice_pdf(pdf_path: Union[str, Path]) -> dict:
    pdf_path = Path(pdf_path)
    raw_text = extract_pdf_text(str(pdf_path))
    text = normalize_text(raw_text)

    parser = get_parser(text)
    invoice = parser.parse(text)

    # dict ordenado según definición de la dataclass
    return asdict(invoice)


def parse_invoices_in_folder(folder_path: Union[str, Path]) -> List[dict]:
    folder = Path(folder_path)
    if not folder.is_dir():
        raise NotADirectoryError(f"{folder} no es un directorio")

    results: List[dict] = []
    for pdf in sorted(folder.glob("*.pdf")):
        try:
            invoice = parse_invoice_pdf(pdf)
            results.append(invoice)
        except Exception as e:
            # aquí luego puedes meter logging en serio
            print(f"[WARN] Error procesando {pdf.name}: {e}")

    return results

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parsear facturas PDF → JSON")
    parser.add_argument("path", help="Ruta a un PDF o a una carpeta con PDFs")
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Si path es archivo: JSON de salida. "
            "Si path es carpeta: JSON con lista de facturas."
        ),
        default=None,
    )
    args = parser.parse_args()

    p = Path(args.path)

    if p.is_file():
        # Modo single invoice
        invoice_dict = parse_invoice_pdf(p)
        json_str = json.dumps(invoice_dict, indent=2, ensure_ascii=False)

        if args.output:
            out = Path(args.output)
            out.write_text(json_str, encoding="utf-8")
            print(f"Factura parseada → {out}")
        else:
            print(json_str)

    elif p.is_dir():
        # Modo folder → lista de facturas
        invoices = parse_invoices_in_folder(p)
        json_str = json.dumps(invoices, indent=2, ensure_ascii=False)

        if args.output:
            out = Path(args.output)
            out.write_text(json_str, encoding="utf-8")
            print(f"{len(invoices)} facturas parseadas → {out}")
        else:
            print(json_str)

    else:
        raise FileNotFoundError(f"No existe ruta: {p}")