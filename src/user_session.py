from typing import Any, Dict, Optional


class UserSessionManager:
    """Manage temporary per-user state for receipt workflows."""

    def __init__(self):
        self._sessions: Dict[int, Dict[str, Any]] = {}

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self._sessions.get(user_id)

    def get_or_create(
        self, user_id: int, defaults: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if user_id not in self._sessions:
            self._sessions[user_id] = dict(defaults or {})
        return self._sessions[user_id]

    def set(self, user_id: int, session: Dict[str, Any]) -> None:
        self._sessions[user_id] = session

    def update(self, user_id: int, **values: Any) -> Dict[str, Any]:
        session = self.get_or_create(user_id)
        session.update(values)
        return session

    def remove(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self._sessions.pop(user_id, None)

    def contains(self, user_id: int) -> bool:
        return user_id in self._sessions
