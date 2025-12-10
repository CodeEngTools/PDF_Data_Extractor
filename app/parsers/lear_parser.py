import re
from typing import Optional, List, Dict, Any

from .base import BaseParser
from app.models import Invoice, Party, InvoiceLine, InvoiceTotals


class LearInvoiceParser(BaseParser):
    # Palabras clave para identificar este modelo
    KEYWORDS = ["Lear", "Invoice Number"]

    # --------- helpers internos ---------

    @staticmethod
    def _extract_first(pattern: str, text: str, flags=re.IGNORECASE) -> Optional[str]:
        m = re.search(pattern, text, flags)
        if not m:
            return None
        return m.group(1) if m.groups() else m.group(0)

    @classmethod
    def _extract_amount(cls, pattern: str, text: str) -> Optional[float]:
        raw = cls._extract_first(pattern, text)
        if not raw:
            return None
        cleaned = raw.replace(",", "").replace(" ", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @classmethod
    def _extract_int(cls, pattern: str, text: str) -> Optional[int]:
        val = cls._extract_amount(pattern, text)
        if val is None:
            return None
        try:
            return int(round(val))
        except ValueError:
            return None


    def _extract_invoice_number(self, text: str) -> str:
        """
        Intenta sacar el invoice number de forma robusta:
        1) Cabecera: 'Invoice Number: DMxxxxxx'
        2) Cuerpo: cualquier 'DM' + 6 dígitos en el texto
        3) Si cabecera no cuadra en longitud/formato, preferimos el del cuerpo.
        """

        # 1) Cabecera
        header = self._extract_first(
            r"Invoice Number:\s*(DM\d+)",  # DM seguido de N dígitos
            text,
        )

        # 2) Candidatos en el cuerpo: DM + 6 dígitos (formato esperado)
        body_matches = re.findall(r"\b(DM\d{6})\b", text)
        body = body_matches[0] if body_matches else None

        # 3) Si la cabecera existe y tiene el formato correcto DM + 6 dígitos, la usamos
        if header and re.fullmatch(r"DM\d{6}", header):
            return header

        # 4) Si la cabecera está rara (p.ej. DM03949) pero el cuerpo tiene un DMxxxxxx válido,
        # usamos el del cuerpo (esto arregla DM03949 -> DM039449, DM03941 -> DM039411, etc.)
        if body:
            return body

        # 5) Fallbacks
        if header:
            return header

        return "UNKNOWN"
    # --------- método principal ---------

    def parse(self, text: str) -> Invoice:
        # 1) Número de factura + fecha
        invoice_number = self._extract_invoice_number(text)
        issue_date = self._extract_first(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text) or "UNKNOWN"

        # 2) Supplier / Customer (para Lear este modelo es estable)
        supplier = Party(
            name="Lear Automotive Morocco SAS",
            vat=None,
            address="Lot 102B/2 Zone Franche, Tanger, Morocco",
        )

        customer = Party(
            name="Lear Automotive Morocco SAS",
            vat="ESN204102A",
            address="Zone Franche d Exportation C/ Futers, 54, Valls 43800 (Tarragona)",
        )

        # 3) Líneas: TODAS las líneas de detalle
        lines: List[InvoiceLine] = []

        line_pattern = re.compile(
            r"""^\s*
                 (?P<idx>\d+)\s+                 # Nº línea
                 (?P<date>\d{2}/\d{2}/\d{2})\s+  # fecha
                 DM\d+\s+                        # nº factura
                 \S+\s+                          # planta / FD3C
                 \S+\s+                          # plataforma (NX6T…)
                 \S+\s+                          # subcódigo
                 \S+\s+                          # customer part number
                 (?P<vend>\S+)\s+                # vendor part (desc)
                 (?P<qty>\d+)\s+                 # cantidad
                 P\s+
                 (?P<unit>[\d\.]+)\s+            # unit price
                 \d+\s+                          # descuento
                 (?P<total>[\d\.]+)\s+           # net amount
                 \d+                             # IVA
            """,
            re.IGNORECASE | re.MULTILINE | re.VERBOSE,
        )

        for m in line_pattern.finditer(text):
            desc = m.group("vend")
            qty = float(m.group("qty"))
            unit_price = float(m.group("unit"))
            line_total = float(m.group("total"))

            lines.append(
                InvoiceLine(
                    description=desc,
                    quantity=qty,
                    unit_price=unit_price,
                    total=line_total,
                )
            )

        # 4) Totales: usamos suma de líneas como fuente principal
        line_total_sum = sum(line.total for line in lines) if lines else 0.0
        total_invoices_reported = self._extract_amount(
            r"Total Invoices\s+([\d\.]+)", text
        )

        if line_total_sum > 0:
            total = line_total_sum
        elif total_invoices_reported is not None:
            total = total_invoices_reported
        else:
            total = 0.0

        subtotal = total
        tax = 0.0

        totals = InvoiceTotals(
            subtotal=subtotal,
            tax=tax,
            total=total,
            currency="EUR",
        )

        # 5) EXTRA: info adicional útil para el resumen y checks
        extra: Dict[str, Any] = {}

        vendor_code = self._extract_first(r"Vendor Code:\s*(\S+)", text)
        customer_code = self._extract_first(r"Customer Code:\s*(\S+)", text)
        if vendor_code:
            extra["vendor_code"] = vendor_code
        if customer_code:
            extra["customer_code"] = customer_code

        number_of_pages = self._extract_int(r"Number Of Pages:\s*([\d\.]+)", text)
        number_of_lines = self._extract_int(r"Number of Lines:\s*([\d\.]+)", text)
        if number_of_pages is not None:
            extra["number_of_pages"] = number_of_pages
        if number_of_lines is not None:
            extra["number_of_lines"] = number_of_lines
        extra["parsed_lines_count"] = len(lines)

        taxable_amount = self._extract_amount(r"Taxable Amount\s+([\d\.]+)", text)
        if taxable_amount is not None:
            extra["taxable_amount_reported"] = taxable_amount
        if total_invoices_reported is not None:
            extra["total_invoices_reported"] = total_invoices_reported

        currency_reported = self._extract_first(r"Curency\s+([A-Z]{3})", text)
        if currency_reported:
            extra["currency_reported"] = currency_reported

        net_weight = self._extract_amount(r"Net Weight:\s*([\d\.]+)", text)
        gross_weight = self._extract_amount(r"Gros Weight:\s*([\d\.]+)", text)
        pallets = self._extract_int(r"Palets:\s*([\d\.]+)", text)

        if net_weight is not None:
            extra["net_weight"] = net_weight
        if gross_weight is not None:
            extra["gross_weight"] = gross_weight
        if pallets is not None:
            extra["pallets"] = pallets

        # checks de totales
        if line_total_sum > 0 and total_invoices_reported is not None:
            diff = abs(line_total_sum - total_invoices_reported)
            ratio = diff / total_invoices_reported if total_invoices_reported else None
            extra["total_lines_sum"] = line_total_sum
            extra["total_reported_diff"] = diff
            extra["total_reported_ratio"] = ratio
            if ratio is not None and ratio > 0.01:
                extra["total_mismatch_flag"] = True

        # 6) Construir Invoice
        invoice = Invoice(
            invoice_number=invoice_number,
            issue_date=issue_date,
            supplier=supplier,
            customer=customer,
            lines=lines,
            totals=totals,
            raw_text=text,
            extra=extra,
        )

        return invoice