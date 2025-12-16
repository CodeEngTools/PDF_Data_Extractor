import re
from typing import Optional, List, Dict, Any

from .base import BaseParser
from app.models import Invoice, Party, InvoiceLine, InvoiceTotals


class LearInvoiceParser(BaseParser):
    # Palabras clave para identificar este modelo
    KEYWORDS = ["Lear", "Invoice Number"]

    # --------- helpers internos ---------

    _NUM_CLEAN_RE = re.compile(r"[^\d,\.\-]+")

    @staticmethod
    def _extract_first(pattern: str, text: str, flags=re.IGNORECASE) -> Optional[str]:
        m = re.search(pattern, text, flags)
        if not m:
            return None
        return m.group(1) if m.groups() else m.group(0)

    @classmethod
    def _normalize_number_str(cls, raw: str) -> Optional[str]:
        """
        Normaliza un número que puede venir en formato EU/US y/o con separadores de miles.
        Devuelve string con '.' como separador decimal y sin separadores de miles.

        Ejemplos:
          - "1.202.938" -> "1202938"
          - "74.058"    -> "74058"
          - "196.4845"  -> "196.4845"
          - "15.768,74" -> "15768.74"
          - "20,435.60" -> "20435.60"
        """
        if raw is None:
            return None
        s = raw.strip().replace(" ", "")
        if not s:
            return None

        s = cls._NUM_CLEAN_RE.sub("", s)

        if not s or s in ("-", ".", ","):
            return None

        if "." in s and "," in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
            return s

        if "," in s and "." not in s:
            if s.count(",") > 1:
                return s.replace(",", "")
            left, right = s.split(",", 1)
            if 1 <= len(right) <= 4:
                left = left.replace(".", "")
                return f"{left}.{right}"
            return (left + right).replace(".", "")

        if "." in s and "," not in s:
            if s.count(".") > 1:
                return s.replace(".", "")
            left, right = s.split(".", 1)
            if len(right) == 3 and len(left) <= 3:
                return left + right
            return s

        return s

    @classmethod
    def _parse_amount_str(cls, raw: str) -> Optional[float]:
        norm = cls._normalize_number_str(raw)
        if not norm:
            return None
        try:
            return float(norm)
        except ValueError:
            return None

    @classmethod
    def _extract_amount(cls, pattern: str, text: str) -> Optional[float]:
        raw = cls._extract_first(pattern, text)
        if not raw:
            return None
        return cls._parse_amount_str(raw)

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
        header = self._extract_first(
            r"Invoice Number:\s*(DM\d+)",
            text,
        )

        body_matches = re.findall(r"\b(DM\d{6})\b", text)
        body = body_matches[0] if body_matches else None

        if header and re.fullmatch(r"DM\d{6}", header):
            return header

        if body:
            return body

        if header:
            return header

        return "UNKNOWN"

    # --------- método principal ---------

    def parse(self, text: str) -> Invoice:
        invoice_number = self._extract_invoice_number(text)
        issue_date = self._extract_first(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text) or "UNKNOWN"

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

        lines: List[InvoiceLine] = []

        line_pattern = re.compile(
            r"""^\s*
                 (?P<idx>\d+)\s+
                 (?P<date>\d{2}/\d{2}/\d{2})\s+
                 DM\d+\s+
                 \S+\s+
                 \S+\s+
                 \S+\s+
                 \S+\s+
                 (?P<vend>\S+)\s+
                 (?P<qty>\d+)\s+
                 P\s+
                 (?P<unit>[\d\.,]+)\s+
                 \d+\s+
                 (?P<total>[\d\.,]+)\s+
                 \d+
            """,
            re.IGNORECASE | re.MULTILINE | re.VERBOSE,
        )

        for m in line_pattern.finditer(text):
            desc = m.group("vend")
            qty = float(m.group("qty"))
            unit_price = self._parse_amount_str(m.group("unit")) or 0.0
            line_total = self._parse_amount_str(m.group("total")) or 0.0

            lines.append(
                InvoiceLine(
                    description=desc,
                    quantity=qty,
                    unit_price=unit_price,
                    total=line_total,
                )
            )

        line_total_sum = sum(line.total for line in lines) if lines else 0.0
        total_invoices_reported = self._extract_amount(r"Total Invoices\s+([\d\.,]+)", text)

        if line_total_sum > 0:
            total = line_total_sum
        elif total_invoices_reported is not None:
            total = total_invoices_reported
        else:
            total = 0.0

        totals = InvoiceTotals(
            subtotal=total,
            tax=0.0,
            total=total,
            currency="EUR",
        )

        extra: Dict[str, Any] = {}

        vendor_code = self._extract_first(r"Vendor Code:\s*(\S+)", text)
        customer_code = self._extract_first(r"Customer Code:\s*(\S+)", text)
        if vendor_code:
            extra["vendor_code"] = vendor_code
        if customer_code:
            extra["customer_code"] = customer_code

        number_of_pages = self._extract_int(r"Number Of Pages:\s*([\d\.,]+)", text)
        number_of_lines = self._extract_int(r"Number of Lines:\s*([\d\.,]+)", text)
        if number_of_pages is not None:
            extra["number_of_pages"] = number_of_pages
        if number_of_lines is not None:
            extra["number_of_lines"] = number_of_lines
        extra["parsed_lines_count"] = len(lines)

        taxable_amount = self._extract_amount(r"Taxable Amount\s+([\d\.,]+)", text)
        if taxable_amount is not None:
            extra["taxable_amount_reported"] = taxable_amount
        if total_invoices_reported is not None:
            extra["total_invoices_reported"] = total_invoices_reported

        currency_reported = self._extract_first(r"Curency\s+([A-Z]{3})", text)
        if currency_reported:
            extra["currency_reported"] = currency_reported

        net_weight = self._extract_amount(r"Net Weight:\s*([\d\.,]+)", text)
        gross_weight = self._extract_amount(r"Gros Weight:\s*([\d\.,]+)", text)
        pallets = self._extract_int(r"Palets:\s*([\d\.,]+)", text)

        if net_weight is not None:
            extra["net_weight"] = net_weight
        if gross_weight is not None:
            extra["gross_weight"] = gross_weight
        if pallets is not None:
            extra["pallets"] = pallets

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
