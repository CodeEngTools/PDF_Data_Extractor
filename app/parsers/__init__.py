# app/parsers/__init__.py
from typing import List, Type
from .base import BaseParser
from .lear_parser import LearInvoiceParser

# Aquí irás añadiendo más parsers en el futuro
_PARSERS: List[Type[BaseParser]] = [
    LearInvoiceParser,
]


def get_parser(text: str) -> BaseParser:
    for parser_cls in _PARSERS:
        if parser_cls.can_handle(text):
            return parser_cls()
    raise ValueError("Ningún parser soporta este documento (sin coincidencia de KEYWORDS)")