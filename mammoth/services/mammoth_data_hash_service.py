"""MD5-based change detection – mirrors MammothDataHashService."""
import hashlib
import json
from typing import Any


class MammothDataHashService:
    def hash(self, data: list[Any] | dict[str, Any]) -> str:
        serialised = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(serialised.encode()).hexdigest()

    def has_changed(self, stored_hash: str, current_hash: str) -> bool:
        return stored_hash != current_hash
