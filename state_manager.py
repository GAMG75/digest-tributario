"""
StateManager — persiste el estado entre ejecuciones para detectar SOLO novedades.

Guarda en state.json los IDs/fechas de los documentos ya procesados.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


class StateManager:
    def __init__(self, path: str = "state.json"):
        self.path = Path(path)
        self._state: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                log.info(f"Estado cargado desde {self.path} (última ejecución: {data.get('last_run', 'desconocida')})")
                return data
            except Exception as e:
                log.warning(f"No se pudo leer state.json: {e}. Iniciando desde cero.")
        return {"last_run": None, "seen": {}}

    def save(self):
        self._state["last_run"] = datetime.now().isoformat()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)
        log.info(f"Estado guardado en {self.path}")

    def is_seen(self, source: str, doc_id: str) -> bool:
        """Retorna True si el documento ya fue procesado."""
        return doc_id in self._state["seen"].get(source, set())

    def mark_seen(self, source: str, doc_id: str):
        """Marca un documento como procesado."""
        if source not in self._state["seen"]:
            self._state["seen"][source] = []
        if doc_id not in self._state["seen"][source]:
            self._state["seen"][source].append(doc_id)

    def get_last_run(self) -> datetime | None:
        lr = self._state.get("last_run")
        return datetime.fromisoformat(lr) if lr else None

    def reset(self, source: str | None = None):
        """Resetea el estado (útil con --force)."""
        if source:
            self._state["seen"].pop(source, None)
        else:
            self._state["seen"] = {}
        log.info(f"Estado reseteado {'para ' + source if source else 'completamente'}")
