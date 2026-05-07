import threading
from config import ROWS, COLS

DIRTY = 0
CLEAN = 1


class Grid:
    def __init__(self):
        self._lock = threading.Lock()
        self._cells = [[DIRTY] * COLS for _ in range(ROWS)]

    def mark_clean(self, r: int, c: int):
        with self._lock:
            self._cells[r][c] = CLEAN

    def is_dirty(self, r: int, c: int) -> bool:
        with self._lock:
            return self._cells[r][c] == DIRTY

    def dirty_cells(self) -> list[tuple[int, int]]:
        with self._lock:
            return [(r, c) for r in range(ROWS) for c in range(COLS) if self._cells[r][c] == DIRTY]

    def all_clean(self) -> bool:
        with self._lock:
            return all(self._cells[r][c] == CLEAN for r in range(ROWS) for c in range(COLS))

    def reset(self):
        with self._lock:
            self._cells = [[DIRTY] * COLS for _ in range(ROWS)]

    def merge(self, other: list[list[int]]):
        """Union: any cell clean in other becomes clean locally."""
        with self._lock:
            for r in range(ROWS):
                for c in range(COLS):
                    if other[r][c] == CLEAN:
                        self._cells[r][c] = CLEAN

    def to_list(self) -> list[list[int]]:
        with self._lock:
            return [row[:] for row in self._cells]

    def from_list(self, cells: list[list[int]]):
        with self._lock:
            self._cells = [row[:] for row in cells]

    def snapshot(self) -> list[list[int]]:
        return self.to_list()
