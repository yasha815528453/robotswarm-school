import threading
from collections import deque
from config import ROWS, COLS

IDLE     = "idle"
MOVING   = "moving"
CLEANING = "cleaning"
WAITING  = "waiting"     # path blocked by a higher-priority peer's claim


class Robot:
    def __init__(self, robot_id: str, start_row: int = 0, start_col: int = 0):
        self.id = robot_id
        self._lock = threading.Lock()
        self._row = start_row
        self._col = start_col
        self._target: tuple[int, int] | None = None
        self._path: list[tuple[int, int]] = []
        self._state = IDLE

    @property
    def position(self) -> tuple[int, int]:
        with self._lock:
            return (self._row, self._col)

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    # ── stepping ──────────────────────────────────────────────────────────

    def step(self, grid, blocked: set[tuple[int, int]] | None = None) -> bool:
        """
        Advance one tick. `blocked` = cells claimed by higher-priority peers
        plus other peers' current positions. The robot avoids these.

        Two-phase cleaning:
          tick A: arrive on dirty cell  → state = CLEANING, cell stays dirty
          tick B: cell flips to CLEAN   → robot moves to next dirty cell on the same tick
        """
        blocked = blocked or set()
        with self._lock:
            pos = (self._row, self._col)

            # Phase B: complete cleaning, then move on the same tick
            if self._state == CLEANING:
                grid.mark_clean(self._row, self._col)
                self._target = self._pick_target(grid, blocked)
                self._path = []
                if self._target is None:
                    self._state = IDLE
                    return True
                self._path = self._bfs(pos, self._target, blocked)
                if not self._path:
                    self._state = WAITING
                    return True
                self._row, self._col = self._path.pop(0)
                self._state = MOVING
                return True

            # Phase A: on a dirty cell — start cleaning, BUT only if no higher-priority
            # peer has claimed this cell (target/path) or is sitting on it. Otherwise yield
            # and move off so they can clean it.
            if grid.is_dirty(self._row, self._col) and pos not in blocked:
                self._state = CLEANING
                return True

            # Otherwise: pick a new target and head there.
            # Re-pick if our target is gone, reached, or already cleaned by a peer.
            if (self._target is None
                    or self._target == pos
                    or not grid.is_dirty(*self._target)):
                self._target = self._pick_target(grid, blocked)
                self._path = []
                if self._target is None:
                    self._state = IDLE
                    return False

            if not self._path:
                self._path = self._bfs(pos, self._target, blocked)
                if not self._path:
                    self._state = WAITING
                    return False

            # If the next step got blocked since we planned, replan next tick
            next_cell = self._path[0]
            if next_cell in blocked:
                self._path = []
                self._state = WAITING
                return False

            self._row, self._col = self._path.pop(0)
            self._state = MOVING
            return True

    # ── target / path selection ───────────────────────────────────────────

    def _pick_target(self, grid, blocked: set[tuple[int, int]]) -> tuple[int, int] | None:
        """Nearest dirty cell that no higher-priority peer has claimed."""
        candidates = [c for c in grid.dirty_cells() if c not in blocked]
        if not candidates:
            return None
        return min(candidates,
                   key=lambda rc: abs(rc[0] - self._row) + abs(rc[1] - self._col))

    @staticmethod
    def _bfs(start, goal, blocked: set[tuple[int, int]]) -> list[tuple[int, int]]:
        """Shortest path from start to goal; refuses to step on `blocked` cells (start excluded)."""
        if start == goal:
            return []
        q: deque[list] = deque([[start]])
        visited = {start}
        while q:
            path = q.popleft()
            r, c = path[-1]
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < ROWS and 0 <= nc < COLS):
                    continue
                if (nr, nc) in visited:
                    continue
                # Allow the goal even if it sits in `blocked` — caller filtered the goal already
                if (nr, nc) in blocked and (nr, nc) != goal:
                    continue
                new_path = path + [(nr, nc)]
                if (nr, nc) == goal:
                    return new_path[1:]
                visited.add((nr, nc))
                q.append(new_path)
        return []

    # ── snapshot ──────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id":     self.id,
                "row":    self._row,
                "col":    self._col,
                "target": self._target,
                "path":   list(self._path),
                "state":  self._state,
            }
