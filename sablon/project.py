"""Proje dosyası: seçilen şablon + parametreler + değişiklik geçmişi (JSON)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .templates import Template, get


@dataclass
class Change:
    param: str
    old: float
    new: float
    reason: str = ""


@dataclass
class Project:
    template: str
    params: dict[str, float] = field(default_factory=dict)
    name: str = ""
    notes: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)

    # --- G/Ç ---------------------------------------------------------------
    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    # --- şablon --------------------------------------------------------------
    @property
    def cls(self) -> type[Template]:
        return get(self.template)

    def instance(self) -> Template:
        return self.cls(self.params)

    def resolved(self) -> dict[str, float]:
        return self.cls.resolve(self.params)

    def apply(self, changes: list[Change], source: str, request: str = "") -> list[Change]:
        """Değişiklikleri sınırlar içinde uygular; gerçekten uygulananları döndürür."""
        cur = self.resolved()
        applied: list[Change] = []
        for ch in changes:
            p = self.cls.param(ch.param)
            new = p.clamp(ch.new)
            if abs(new - cur[ch.param]) < 1e-9:
                continue
            note = ch.reason
            if new != ch.new:
                note = (note + " " if note else "") + f"(istenen {ch.new} → izin verilen aralık {p.min}–{p.max})"
            applied.append(Change(ch.param, cur[ch.param], new, note))
            cur[ch.param] = new
        if applied:
            self.params = cur
            self.history.append({
                "time": datetime.now().isoformat(timespec="seconds"),
                "source": source,
                "request": request,
                "changes": [asdict(c) for c in applied],
            })
        return applied
