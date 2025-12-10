from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any  # <--- añade Dict, Any


@dataclass
class Party:
    name: str
    vat: Optional[str] = None
    address: Optional[str] = None


@dataclass
class InvoiceLine:
    description: str
    quantity: float
    unit_price: float
    total: float


@dataclass
class InvoiceTotals:
    subtotal: float
    tax: float
    total: float
    currency: str = "EUR"


@dataclass
class Invoice:
    invoice_number: str
    issue_date: str          # luego si quieres lo cambiamos a date
    supplier: Party
    customer: Party
    lines: List[InvoiceLine] = field(default_factory=list)
    totals: Optional[InvoiceTotals] = None
    raw_text: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)