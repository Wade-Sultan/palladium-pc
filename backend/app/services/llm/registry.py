import os
from typing import Dict

from .base import LLMEngine
from .huggingface import HuggingFaceEngine


_DEFAULT_MODEL = os.getenv(
    "LLM_DEFAULT_MODEL",
    "mistralai/Mistral-7B-Instruct-v0.2",
)

_engines: Dict[str, LLMEngine] = {}


def get_engine(model_name: str | None) -> LLMEngine:
    name = model_name or _DEFAULT_MODEL

    if name not in _engines:
        _engines[name] = HuggingFaceEngine(name)
        _engines[name].load()

    return _engines[name]
