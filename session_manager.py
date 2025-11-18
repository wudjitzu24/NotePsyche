import os
import json
import datetime
from typing import Any, Dict, Optional

try:
    import langgraph as _langgraph  # optional integration
    _HAS_LANGGRAPH = True
except Exception:
    _langgraph = None
    _HAS_LANGGRAPH = False


class SessionManager:
    """Manage sessions and checkpoints.

    - Stores per-session checkpoint JSON files in a `checkpoints_dir`.
    - Keeps `sessions_metadata.json` with overview of sessions.
    - If `langgraph` is available, exposes the module on `self.langgraph` for further use.
    """

    def __init__(self, checkpoints_dir: Optional[str] = None):
        base = checkpoints_dir or os.path.join(os.path.dirname(__file__), "checkpoints")
        self.checkpoints_dir = os.path.abspath(base)
        os.makedirs(self.checkpoints_dir, exist_ok=True)
        self.metadata_path = os.path.join(self.checkpoints_dir, "sessions_metadata.json")
        if not os.path.exists(self.metadata_path):
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)

        self.langgraph = _langgraph if _HAS_LANGGRAPH else None

    def _session_path(self, session_id: str) -> str:
        safe = session_id.replace("/", "_")
        return os.path.join(self.checkpoints_dir, f"{safe}.json")

    def _load_metadata(self) -> Dict[str, Any]:
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_metadata(self, meta: Dict[str, Any]):
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    def create_session(self, session_id: str, meta: Optional[Dict[str, Any]] = None) -> bool:
        """Create a new session record.

        Returns True if the session was newly created, False if it already existed.
        """
        meta = meta or {}
        metadata = self._load_metadata()
        if session_id in metadata:
            return False
        now = datetime.datetime.now().isoformat()
        metadata[session_id] = {"created": now, "last_updated": now, "info": meta}
        self._save_metadata(metadata)
        # create empty checkpoint file
        path = self._session_path(session_id)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
        return True

    def list_sessions(self):
        return list(self._load_metadata().keys())

    def load_session(self, session_id: str) -> Dict[str, Any]:
        path = self._session_path(session_id)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_checkpoint(self, session_id: str, checkpoint: Dict[str, Any]) -> None:
        # ensure session exists
        self.create_session(session_id)
        # attach timestamp
        checkpoint_copy = dict(checkpoint)
        checkpoint_copy["last_saved_at"] = datetime.datetime.now().isoformat()
        path = self._session_path(session_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_copy, f, indent=2, ensure_ascii=False)
        except Exception:
            # best-effort write
            pass

        # update metadata
        metadata = self._load_metadata()
        if session_id not in metadata:
            metadata[session_id] = {"created": datetime.datetime.now().isoformat(), "info": {}}
        metadata[session_id]["last_updated"] = datetime.datetime.now().isoformat()
        self._save_metadata(metadata)

    def get_checkpoint(self, session_id: str) -> Dict[str, Any]:
        return self.load_session(session_id)

    def delete_session(self, session_id: str) -> None:
        metadata = self._load_metadata()
        if session_id in metadata:
            metadata.pop(session_id, None)
            self._save_metadata(metadata)
        path = self._session_path(session_id)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


__all__ = ["SessionManager"]
