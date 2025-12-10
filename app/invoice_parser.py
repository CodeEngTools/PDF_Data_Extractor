from __future__ import annotations

import re
from typing import List, Optional

from models import Invoice, Party, InvoiceLine, InvoiceTotals


def _extract_first(pattern: str, text: str, flags=re.IGNORECASE) -> Optional[str]:
    m = re.search(pattern, text, flags)
    if not m:
        return None
    return m.group(1) if m.groups() else m.group(0)


def _extract_block_between(text: str, start: str, end: str) -> str:
    """
    Devuelve el texto entre la primera aparición de `start`
    y la primera aparición de `end` después de eso.
    """
    try:
        start_idx = text.index(start) + len(start)
        end_idx = text.index(end, start_idx)
        block = text[start_idx:end_idx]
        return block.strip()
    except ValueError:
        return ""


def _clean_lines(block: str) -> list[str]:
    """
    Separa por líneas, limpia espacios, y filtra vacías.
    """
    lines = [l.strip() for l in block.splitlines()]
    return [l for l in lines if l]


def parse_invoice_from_text(text: str) -> Invoice:
    # ------------------------------------------------------------------
    # 1) Número de factura y fecha
    # ------------------------------------------------------------------
    invoice_number = _extract_first(
        r"Invoice Number\s+([A-Z0-9\-]+)", text, flags=re.IGNORECASE
    ) or "UNKNOWN"

    # Ej: "Invoice Date January 25, 2016"
    issue_date = _extract_first(
        r"Invoice Date\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, flags=re.IGNORECASE
    ) or "UNKNOWN"

    # ------------------------------------------------------------------
    # 2) Supplier (From: ... To:)
    # ------------------------------------------------------------------
    from_to_block = _extract_block_between(text, "From:", "To:")
    from_lines = _clean_lines(from_to_block)

    # En tu PDF, el bloque queda algo tipo:
    # DEMO - Sliced Invoices Order Number 12345
    # Suite 5A-1204 Invoice Date January 25, 2016
    # 123 Somewhere Street
    # Due Date January 31, 2016
    # Your City AZ 12345
    # Total Due $93.50
    # admin@slicedinvoices.com

    supplier_name = "SUPPLIER"
    supplier_address_lines: list[str] = []
    supplier_email: Optional[str] = None

    if from_lines:
        # 1ª línea: nombre + quizá "Order Number 12345"
        first = from_lines[0]
        # cortamos por "Order Number" si existe
        supplier_name = re.split(r"\bOrder Number\b", first, flags=re.IGNORECASE)[0].strip()

        # El resto de líneas hasta la línea del email y/o líneas claramente de fechas/total
        for line in from_lines[1:]:
            # línea con email
            if "@" in line:
                supplier_email = line
                continue

            # líneas que son claramente de fechas/totales del invoice, no parte de dirección
            if re.search(r"(Invoice Date|Due Date|Total Due)", line, re.IGNORECASE):
                continue

            supplier_address_lines.append(line)

    supplier_address = "\n".join(supplier_address_lines) if supplier_address_lines else None
    if supplier_email and supplier_address:
        supplier_address = supplier_address + f"\n{supplier_email}"
    elif supplier_email and not supplier_address:
        supplier_address = supplier_email

    supplier = Party(
        name=supplier_name or "SUPPLIER",
        vat=None,
        address=supplier_address,
    )

    # ------------------------------------------------------------------
    # 3) Customer (To: ... Hrs/Qty)
    # ------------------------------------------------------------------
    to_block = _extract_block_between(text, "To:", "Hrs/Qty")
    to_lines = _clean_lines(to_block)

    # En el PDF:
    # Test Business
    # 123 Somewhere St
    # d
    # Melbourne, VIC 3000
    # test@test.com
    # i

    customer_name = "CUSTOMER"
    customer_address_lines: list[str] = []
    customer_email: Optional[str] = None

    if to_lines:
        customer_name = to_lines[0]
        for line in to_lines[1:]:
            # quita las líneas "ruido" de una sola letra (d, i, etc.)
            if len(line) == 1:
                continue

            if "@" in line:
                customer_email = line
                continue

            customer_address_lines.append(line)

    customer_address = "\n".join(customer_address_lines) if customer_address_lines else None
    if customer_email and customer_address:
        customer_address = customer_address + f"\n{customer_email}"
    elif customer_email and not customer_address:
        customer_address = customer_email

    customer = Party(
        name=customer_name or "CUSTOMER",
        vat=None,
        address=customer_address,
    )

    # ------------------------------------------------------------------
    # 4) Totales
    # ------------------------------------------------------------------
    def _extract_amount(pattern: str) -> Optional[float]:
        raw = _extract_first(pattern, text, flags=re.IGNORECASE)
        if not raw:
            return None
        # aquí los números vienen como 85.00, 8.50, etc.
        cleaned = raw.replace(",", "")  # por si acaso
        try:
            return float(cleaned)
        except ValueError:
            return None

    subtotal = _extract_amount(r"Sub Total\s*\$([\d\.]+)")
    tax = _extract_amount(r"Tax\s*\$([\d\.]+)")
    total = _extract_amount(r"Total\s*\$([\d\.]+)")

    totals = None
    if subtotal is not None and total is not None:
        totals = InvoiceTotals(
            subtotal=subtotal,
            tax=tax or 0.0,
            total=total,
            currency="USD",  # o "EUR" si quieres forzarlo
        )

    # ------------------------------------------------------------------
    # 5) Línea de detalle
    # ------------------------------------------------------------------
    # El texto relevante:
    # Web Design
    # 1.00 $85.00 0.00% $85.00
    # This is a sample description...
    #
    # Vamos a buscar la línea de qty/precio con regex y usar la línea
    # anterior como descripción base, y la siguiente para extenderla.

    lines: List[InvoiceLine] = []

    all_lines = text.splitlines()
    # Creamos un índice → línea para poder mirar alrededor.
    # Buscamos patrones tipo: "1.00 $85.00 0.00% $85.00"
    line_pattern = re.compile(
        r"^\s*(?P<qty>\d+(?:\.\d+)?)\s+\$(?P<unit>[\d\.]+)\s+[0-9\.]+%?\s+\$(?P<total>[\d\.]+)\s*$",
        re.IGNORECASE,
    )

    for idx, line in enumerate(all_lines):
        match = line_pattern.match(line)
        if not match:
            continue

        qty = float(match.group("qty"))
        unit_price = float(match.group("unit"))
        line_total = float(match.group("total"))

        # descripción = línea anterior + posible línea posterior si no es un campo de resumen
        desc_parts: list[str] = []

        # línea anterior
        if idx > 0:
            prev_line = all_lines[idx - 1].strip()
            if prev_line and not prev_line.lower().startswith("hrs/qty"):
                desc_parts.append(prev_line)

        # línea posterior
        if idx + 1 < len(all_lines):
            next_line = all_lines[idx + 1].strip()
            # evitamos pillar "Sub Total", "Tax", etc.
            if next_line and not re.match(r"(Sub Total|Tax|Total)\b", next_line, re.IGNORECASE):
                desc_parts.append(next_line)

        description = " – ".join(desc_parts) if desc_parts else "Item"

        lines.append(
            InvoiceLine(
                description=description,
                quantity=qty,
                unit_price=unit_price,
                total=line_total,
            )
        )

    invoice = Invoice(
        invoice_number=invoice_number,
        issue_date=issue_date,
        supplier=supplier,
        customer=customer,
        lines=lines,
        totals=totals,
        raw_text=text,
    )

    return invoice