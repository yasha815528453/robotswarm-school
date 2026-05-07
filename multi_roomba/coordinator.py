import threading
from config import COLS


class Coordinator:
    """Zone assignment logic. Only meaningful when this node is the leader."""

    def __init__(self):
        self._lock = threading.Lock()
        self._assignments: dict[str, tuple[int, int]] = {}  # robot_id -> (col_start, col_end)

    def assign_zones(self, member_ids: list[str]) -> dict[str, tuple[int, int]]:
        """Divide columns evenly among sorted member IDs."""
        n = len(member_ids)
        if n == 0:
            return {}
        sorted_ids = sorted(member_ids)
        base, remainder = divmod(COLS, n)
        assignments: dict[str, tuple[int, int]] = {}
        col = 0
        for i, rid in enumerate(sorted_ids):
            width = base + (1 if i < remainder else 0)
            assignments[rid] = (col, col + width - 1)
            col += width
        with self._lock:
            self._assignments = assignments
        return assignments

    def get_zone(self, robot_id: str) -> tuple[int, int] | None:
        with self._lock:
            return self._assignments.get(robot_id)

    def get_all_zones(self) -> dict[str, tuple[int, int]]:
        with self._lock:
            return dict(self._assignments)
