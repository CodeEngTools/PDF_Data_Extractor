import json
import csv
from dataclasses import asdict
from pathlib import Path
from typing import List, Dict, Any, Union

from app.pdf_extractor import extract_pdf_text
from app.normalizer import normalize_text
from app.parsers.lear_parser import LearInvoiceParser


def parse_invoice_pdf(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    pdf_path = Path(pdf_path)
    raw_text = extract_pdf_text(str(pdf_path))
    text = normalize_text(raw_text)

    parser = LearInvoiceParser()
    invoice = parser.parse(text)
    return asdict(invoice)


def parse_invoices_in_folder(folder_path: Union[str, Path]) -> List[Dict[str, Any]]:
    folder = Path(folder_path)
    if not folder.is_dir():
        raise NotADirectoryError(f"{folder} no es un directorio")

    results: List[Dict[str, Any]] = []
    for pdf in sorted(folder.glob("*.pdf")):
        try:
            inv = parse_invoice_pdf(pdf)
            results.append(inv)
        except Exception as e:
            print(f"[WARN] Error procesando {pdf.name}: {e}")

    return results


def build_summary(invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for inv in invoices:
        extra = inv.get("extra") or {}
        summary.append(
            {
                "invoice_number": inv.get("invoice_number"),
                "issue_date": inv.get("issue_date"),
                "pallets": extra.get("pallets"),
                "gross_weight": extra.get("gross_weight"),
                "total_invoices_reported": extra.get("total_invoices_reported"),
            }
        )
    return summary


def write_outputs(
    invoices: List[Dict[str, Any]],
    out_dir: Union[str, Path],
    base_name: str = "lear_invoices",
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    merged_json = out_dir / f"{base_name}_merged.json"
    summary_json = out_dir / f"{base_name}_summary.json"
    summary_csv = out_dir / f"{base_name}_summary.csv"

    # 1) JSON completo
    merged_json.write_text(json.dumps(invoices, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2) JSON resumido
    summary = build_summary(invoices)
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3) CSV + fila de totales
    fieldnames = [
        "invoice_number",
        "issue_date",
        "pallets",
        "gross_weight",
        "total_invoices_reported",
    ]

    total_pallets = 0.0
    total_gross_weight = 0.0
    total_invoices_value = 0.0

    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in summary:
            # acumular totales (ignorando None)
            p = row.get("pallets")
            gw = row.get("gross_weight")
            tiv = row.get("total_invoices_reported")

            if p is not None:
                total_pallets += float(p)
            if gw is not None:
                total_gross_weight += float(gw)
            if tiv is not None:
                total_invoices_value += float(tiv)

            writer.writerow(row)

        # Fila de totales
        totals_row = {
            "invoice_number": "TOTAL",
            "issue_date": "",
            "pallets": f"{total_pallets:.2f}",
            "gross_weight": f"{total_gross_weight:.2f}",
            "total_invoices_reported": f"{total_invoices_value:.2f}",
        }
        writer.writerow(totals_row)

    print(f"JSON completo   → {merged_json}")
    print(f"JSON resumen    → {summary_json}")
    print(f"CSV resumen     → {summary_csv}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Pipeline Lear: PDFs → JSON completo + JSON resumen + CSV con totales"
    )
    parser.add_argument("input_folder", help="Carpeta con los PDFs de factura Lear")
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Carpeta de salida para los JSON/CSV",
        default=".",
    )
    parser.add_argument(
        "--base-name",
        help="Prefijo de los ficheros de salida",
        default="lear_invoices",
    )

    args = parser.parse_args()

    invoices = parse_invoices_in_folder(args.input_folder)
    print(f"Facturas procesadas: {len(invoices)}")
    write_outputs(invoices, args.output_dir, base_name=args.base_name)


if __name__ == "__main__":
    main()