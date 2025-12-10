# app/parsers/base.py
from abc import ABC, abstractmethod
from typing import ClassVar
from app.models import Invoice


class BaseParser(ABC):
    KEYWORDS: ClassVar[list[str]] = []

    @classmethod
    def can_handle(cls, text: str) -> bool:
        text_lower = text.lower()
        return all(k.lower() in text_lower for k in cls.KEYWORDS)

    @abstractmethod
    def parse(self, text: str) -> Invoice:
        ...