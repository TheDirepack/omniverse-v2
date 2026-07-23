import json
from pathlib import Path
from datetime import datetime

from loop.loop_config import LOOP_BACKUP_DIR


class ImprovementTracker:
    def __init__(self):
        self.record_file = LOOP_BACKUP_DIR / "improvements.json"
        self.records: list[dict] = []
        self._load()

    def _load(self):
        if self.record_file.exists():
            try:
                self.records = json.loads(self.record_file.read_text())
            except (json.JSONDecodeError, ValueError):
                self.records = []

    def _save(self):
        self.record_file.parent.mkdir(parents=True, exist_ok=True)
        self.record_file.write_text(json.dumps(self.records, indent=2))

    def record_change(self, loop: int, world: str, change_type: str, description: str, files_changed: list[str], metrics_before: dict | None = None, metrics_after: dict | None = None):
        entry = {
            "loop": loop,
            "world": world,
            "timestamp": datetime.utcnow().isoformat(),
            "change_type": change_type,
            "description": description,
            "files_changed": files_changed,
            "metrics_before": metrics_before or {},
            "metrics_after": metrics_after or {},
        }
        self.records.append(entry)
        self._save()

    def get_summary(self) -> str:
        if not self.records:
            return "No improvements recorded yet."
        lines = ["=== IMPROVEMENT HISTORY ==="]
        for r in self.records:
            lines.append(f"Loop {r['loop']} ({r['world']}): [{r['change_type']}] {r['description']}")
            if r.get("files_changed"):
                for f in r["files_changed"]:
                    lines.append(f"  - {f}")
        return "\n".join(lines)

    def get_loop_count(self) -> int:
        return len(set(r["loop"] for r in self.records))

    def get_changes_for_loop(self, loop: int) -> list[dict]:
        return [r for r in self.records if r["loop"] == loop]
