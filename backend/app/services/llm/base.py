from abc import ABC, abstractmethod
from typing import Optional


class LLMEngine(ABC):
    @abstractmethod
    def load(self) -> None:
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
    ) -> str:
        ...
