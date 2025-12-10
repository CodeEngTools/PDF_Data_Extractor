import json
import csv
from pathlib import Path

INPUT = Path("samples/lear_invoices_merged.json")
SUMMARY_JSON = Path("samples/lear_invoices_summary.json")
SUMMARY_CSV = Path("samples/lear_invoices_summary.csv")

def main() -> None:
    # 1) Leer JSON completo
    with INPUT.open("r", encoding="utf-8") as f:
        invoices = json.load(f)

    # 2) Construir lista filtrada
    summary = []
    for inv in invoices:
        extra = inv.get("extra", {}) or {}

        item = {
            "invoice_number": inv.get("invoice_number"),
            "issue_date": inv.get("issue_date"),
            "total_invoices_reported": extra.get("total_invoices_reported"),
            "gross_weight": extra.get("gross_weight"),
            "pallets": extra.get("pallets"),
        }
        summary.append(item)

    # 3) Guardar JSON filtrado
    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # 4) Guardar CSV (estilo tabla)
    # Puedes ajustar el orden/columnas a tu gusto
    fieldnames = [
        "invoice_number",
        "issue_date",
        "pallets",
        "gross_weight",
        "total_invoices_reported",
    ]

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary:
            writer.writerow(row)

    print(f"Resumen JSON → {SUMMARY_JSON}")
    print(f"Resumen CSV  → {SUMMARY_CSV}")


if __name__ == "__main__":
    main()