import pygame
from config import (
    ROWS, COLS, CELL_SIZE, MARGIN,
    COLOR_DIRTY, COLOR_CLEAN, COLOR_ROBOT, COLOR_TARGET,
    COLOR_BG, COLOR_STATUS_BG, COLOR_TEXT,
    WINDOW_WIDTH, WINDOW_HEIGHT, STATUS_BAR_HEIGHT,
)


class Gui:
    def __init__(self, grid, robot, cluster):
        self._grid = grid
        self._robot = robot
        self._cluster = cluster
        self._screen = None
        self._clock = None

    def init(self):
        pygame.init()
        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(f"Roomba — {self._robot.id}")
        self._font     = pygame.font.SysFont("monospace", 13)
        self._big_font = pygame.font.SysFont("monospace", 15, bold=True)
        self._clock = pygame.time.Clock()

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
        return True

    def draw(self):
        self._screen.fill(COLOR_BG)
        cells   = self._grid.snapshot()
        robot_s = self._robot.snapshot()
        peers   = self._cluster.get_peer_states()

        self._draw_cells(cells)
        self._draw_paths(robot_s, peers)
        self._draw_targets(robot_s, peers)
        self._draw_peers(peers)
        self._draw_robot(robot_s)
        self._draw_status(robot_s, peers)

        pygame.display.flip()
        self._clock.tick(30)

    # ── geometry ──────────────────────────────────────────────────────────

    def _cell_rect(self, r, c):
        x = MARGIN + c * (CELL_SIZE + MARGIN)
        y = MARGIN + r * (CELL_SIZE + MARGIN)
        return (x, y, CELL_SIZE, CELL_SIZE)

    def _cell_center(self, r, c):
        x = MARGIN + c * (CELL_SIZE + MARGIN) + CELL_SIZE // 2
        y = MARGIN + r * (CELL_SIZE + MARGIN) + CELL_SIZE // 2
        return (x, y)

    # ── colors per robot ──────────────────────────────────────────────────

    _PEER_COLORS = [
        (220,  60,  60), ( 60, 180,  75), (245, 180,  40),
        (160,  80, 200), ( 50, 200, 200),
    ]

    def _peer_color(self, peer_id: str):
        return self._PEER_COLORS[hash(peer_id) % len(self._PEER_COLORS)]

    # ── cells, paths, targets ─────────────────────────────────────────────

    def _draw_cells(self, cells):
        for r in range(ROWS):
            for c in range(COLS):
                color = COLOR_CLEAN if cells[r][c] == 1 else COLOR_DIRTY
                pygame.draw.rect(self._screen, color, self._cell_rect(r, c))

    def _draw_paths(self, robot_s, peers):
        # My own planned path in blue
        self._draw_path(robot_s.get("row"), robot_s.get("col"),
                        robot_s.get("path") or [], COLOR_ROBOT)
        for pid, st in peers.items():
            if "row" in st and "col" in st:
                self._draw_path(st["row"], st["col"],
                                st.get("path") or [], self._peer_color(pid))

    def _draw_path(self, start_r, start_c, path, color):
        if not path:
            return
        prev = self._cell_center(start_r, start_c)
        for cell in path:
            r, c = cell if isinstance(cell, (list, tuple)) else (cell[0], cell[1])
            curr = self._cell_center(r, c)
            pygame.draw.line(self._screen, color, prev, curr, 2)
            prev = curr

    def _draw_targets(self, robot_s, peers):
        if robot_s.get("target"):
            tr, tc = robot_s["target"]
            pygame.draw.circle(self._screen, COLOR_TARGET, self._cell_center(tr, tc), 8, 2)
        for pid, st in peers.items():
            if st.get("target"):
                tr, tc = st["target"]
                pygame.draw.circle(self._screen, self._peer_color(pid),
                                   self._cell_center(tr, tc), 8, 2)

    # ── robot bodies ──────────────────────────────────────────────────────

    def _draw_peers(self, peers):
        radius = CELL_SIZE // 3
        for pid, st in peers.items():
            if "row" not in st or "col" not in st:
                continue
            cx, cy = self._cell_center(st["row"], st["col"])
            color = self._peer_color(pid)
            pygame.draw.circle(self._screen, color, (cx, cy), radius)
            if st.get("rstate") == "cleaning":
                pygame.draw.circle(self._screen, (255, 255, 255), (cx, cy), radius + 4, 2)
            elif st.get("rstate") == "waiting":
                pygame.draw.circle(self._screen, (120, 120, 120), (cx, cy), radius + 4, 2)
            label = self._big_font.render(pid[-1].upper(), True, (255, 255, 255))
            self._screen.blit(label, label.get_rect(center=(cx, cy)))

    def _draw_robot(self, robot_s):
        cx, cy = self._cell_center(robot_s["row"], robot_s["col"])
        radius = CELL_SIZE // 3
        # white halo distinguishes "me" from peers
        pygame.draw.circle(self._screen, (255, 255, 255), (cx, cy), radius + 3)
        pygame.draw.circle(self._screen, COLOR_ROBOT, (cx, cy), radius)
        if robot_s["state"] == "cleaning":
            pygame.draw.circle(self._screen, COLOR_TARGET, (cx, cy), radius + 5, 2)
        elif robot_s["state"] == "waiting":
            pygame.draw.circle(self._screen, (120, 120, 120), (cx, cy), radius + 5, 2)
        label = self._big_font.render(robot_s["id"][-1].upper(), True, (255, 255, 255))
        self._screen.blit(label, label.get_rect(center=(cx, cy)))

    # ── status bar ────────────────────────────────────────────────────────

    def _draw_status(self, robot_s, peers):
        bar_y = WINDOW_HEIGHT - STATUS_BAR_HEIGHT
        pygame.draw.rect(self._screen, COLOR_STATUS_BG, (0, bar_y, WINDOW_WIDTH, STATUS_BAR_HEIGHT))

        members = sorted([robot_s["id"]] + list(peers.keys()))
        priority_str = " > ".join(members)  # leftmost = highest priority
        dirty = len(self._grid.dirty_cells())
        total = ROWS * COLS

        line1 = f"ID: {robot_s['id']}   state: {robot_s['state']}   target: {robot_s['target'] or '—'}"
        line2 = f"priority: {priority_str}   clean: {total - dirty}/{total}"

        self._screen.blit(self._font.render(line1, True, COLOR_TEXT), (8, bar_y + 8))
        self._screen.blit(self._font.render(line2, True, COLOR_TEXT), (8, bar_y + 30))
