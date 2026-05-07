import threading
from collections import deque
from config import ROWS, COLS

IDLE     = "idle"
MOVING   = "moving"
CLEANING = "cleaning"


class Robot:
    def __init__(self, robot_id: str, start_row: int = 0, start_col: int = 0):
        self.id = robot_id
        self._lock = threading.Lock()
        self._row = start_row
        self._col = start_col
        self._target: tuple[int, int] | None = None
        self._zone: tuple[int, int] | None = None   # (col_start, col_end) inclusive
        self._state = IDLE
        self._path: list[tuple[int, int]] = []

    # ── read-only properties ──────────────────────────────────────────────

    @property
    def position(self) -> tuple[int, int]:
        with self._lock:
            return (self._row, self._col)

    @property
    def zone(self) -> tuple[int, int] | None:
        with self._lock:
            return self._zone

    @zone.setter
    def zone(self, z: tuple[int, int] | None):
        with self._lock:
            self._zone = z
            self._target = None
            self._path = []
            self._state = IDLE

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    # ── movement ──────────────────────────────────────────────────────────

    def step(self, grid) -> bool:
        """
        Advance robot by one tick. Two-phase cleaning:
          tick A — arrive on dirty cell → state = CLEANING, cell stays dirty
          tick B — finish cleaning AND move to next dirty cell in the same atomic step
        This way a cell only flips to CLEAN at the moment the robot leaves it.
        """
        with self._lock:
            pos = (self._row, self._col)

            # Phase B: complete cleaning, then move on the same tick
            if self._state == CLEANING:
                grid.mark_clean(self._row, self._col)
                self._target = self._pick_target(grid)
                self._path = []
                if self._target is None:
                    self._state = IDLE
                    return True
                self._state = MOVING
                self._path = self._bfs(pos, self._target)
                if self._path:
                    next_r, next_c = self._path.pop(0)
                    self._row, self._col = next_r, next_c
                return True

            # Phase A: on a dirty cell — start cleaning (cell stays dirty this tick)
            if grid.is_dirty(self._row, self._col):
                self._state = CLEANING
                return True

            # On a clean cell — keep heading toward target
            if self._target is None or self._target == pos:
                self._target = self._pick_target(grid)
                self._path = []
                if self._target is None:
                    self._state = IDLE
                    return False
                self._state = MOVING

            if not self._path:
                self._path = self._bfs(pos, self._target)
                if not self._path:
                    self._target = None
                    self._state = IDLE
                    return False

            next_r, next_c = self._path.pop(0)
            self._row, self._col = next_r, next_c
            return True

    def _pick_target(self, grid) -> tuple[int, int] | None:
        """Nearest dirty cell inside the assigned zone (or anywhere if no zone)."""
        if self._zone is None:
            candidates = grid.dirty_cells()
        else:
            col_start, col_end = self._zone
            candidates = [(r, c) for r, c in grid.dirty_cells() if col_start <= c <= col_end]
        if not candidates:
            return None
        return min(candidates, key=lambda rc: abs(rc[0] - self._row) + abs(rc[1] - self._col))

    @staticmethod
    def _bfs(start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
        if start == goal:
            return []
        queue: deque[list] = deque([[start]])
        visited = {start}
        while queue:
            path = queue.popleft()
            r, c = path[-1]
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in visited:
                    new_path = path + [(nr, nc)]
                    if (nr, nc) == goal:
                        return new_path[1:]
                    visited.add((nr, nc))
                    queue.append(new_path)
        return []

    # ── snapshot for GUI ──────────────────────────────────────────────────

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id":     self.id,
                "row":    self._row,
                "col":    self._col,
                "target": self._target,
                "zone":   self._zone,
                "state":  self._state,
            }
