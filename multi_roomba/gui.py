import pygame
from config import (
    ROWS, COLS, CELL_SIZE, MARGIN,
    COLOR_DIRTY, COLOR_CLEAN, COLOR_ROBOT, COLOR_TARGET,
    COLOR_BG, COLOR_STATUS_BG, COLOR_TEXT,
    ZONE_COLORS, WINDOW_WIDTH, WINDOW_HEIGHT, STATUS_BAR_HEIGHT,
)


class Gui:
    def __init__(self, grid, robot, cluster, coordinator):
        self._grid = grid
        self._robot = robot
        self._cluster = cluster
        self._coordinator = coordinator
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
        """Return False when the user closes the window."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
        return True

    def draw(self):
        self._screen.fill(COLOR_BG)
        cells     = self._grid.snapshot()
        zones     = self._coordinator.get_all_zones()
        robot_s   = self._robot.snapshot()
        peers     = self._cluster.get_peer_states()

        self._draw_zone_overlays(zones)
        self._draw_cells(cells)
        self._draw_target(robot_s)
        self._draw_peers(peers)
        self._draw_robot(robot_s)
        self._draw_status(robot_s, zones, peers)

        pygame.display.flip()
        self._clock.tick(30)

    # ── private draw helpers ──────────────────────────────────────────────

    def _cell_rect(self, r: int, c: int) -> tuple[int, int, int, int]:
        x = MARGIN + c * (CELL_SIZE + MARGIN)
        y = MARGIN + r * (CELL_SIZE + MARGIN)
        return (x, y, CELL_SIZE, CELL_SIZE)

    def _cell_center(self, r: int, c: int) -> tuple[int, int]:
        x = MARGIN + c * (CELL_SIZE + MARGIN) + CELL_SIZE // 2
        y = MARGIN + r * (CELL_SIZE + MARGIN) + CELL_SIZE // 2
        return (x, y)

    def _draw_zone_overlays(self, zones: dict):
        sorted_ids = sorted(zones.keys())
        for rid, (col_start, col_end) in zones.items():
            idx = sorted_ids.index(rid) % len(ZONE_COLORS)
            r, g, b, a = ZONE_COLORS[idx]
            w = (col_end - col_start + 1) * (CELL_SIZE + MARGIN)
            h = ROWS * (CELL_SIZE + MARGIN) + MARGIN
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            surf.fill((r, g, b, a))
            x = MARGIN + col_start * (CELL_SIZE + MARGIN)
            self._screen.blit(surf, (x, 0))

    def _draw_cells(self, cells: list[list[int]]):
        for r in range(ROWS):
            for c in range(COLS):
                color = COLOR_CLEAN if cells[r][c] == 1 else COLOR_DIRTY
                pygame.draw.rect(self._screen, color, self._cell_rect(r, c))

    def _draw_target(self, robot_s: dict):
        if robot_s["target"]:
            tr, tc = robot_s["target"]
            pygame.draw.circle(self._screen, COLOR_TARGET, self._cell_center(tr, tc), 7)

    _PEER_COLORS = [
        (220,  60,  60),   # red
        ( 60, 180,  75),   # green
        (245, 180,  40),   # amber
        (160,  80, 200),   # purple
        ( 50, 200, 200),   # teal
    ]

    def _peer_color(self, peer_id: str):
        return self._PEER_COLORS[hash(peer_id) % len(self._PEER_COLORS)]

    def _draw_robot(self, robot_s: dict):
        cx, cy = self._cell_center(robot_s["row"], robot_s["col"])
        radius = CELL_SIZE // 3
        # Outer white ring distinguishes "me" from peers
        pygame.draw.circle(self._screen, (255, 255, 255), (cx, cy), radius + 3)
        pygame.draw.circle(self._screen, COLOR_ROBOT, (cx, cy), radius)
        label_ch = robot_s["id"][-1].upper()
        label = self._big_font.render(label_ch, True, (255, 255, 255))
        self._screen.blit(label, label.get_rect(center=(cx, cy)))

    def _draw_peers(self, peers: dict):
        radius = CELL_SIZE // 3
        for pid, st in peers.items():
            if "row" not in st or "col" not in st:
                continue
            cx, cy = self._cell_center(st["row"], st["col"])
            color = self._peer_color(pid)
            pygame.draw.circle(self._screen, color, (cx, cy), radius)
            label_ch = pid[-1].upper()
            label = self._big_font.render(label_ch, True, (255, 255, 255))
            self._screen.blit(label, label.get_rect(center=(cx, cy)))

    def _draw_status(self, robot_s: dict, zones: dict, peers: dict):
        bar_y = WINDOW_HEIGHT - STATUS_BAR_HEIGHT
        pygame.draw.rect(self._screen, COLOR_STATUS_BG, (0, bar_y, WINDOW_WIDTH, STATUS_BAR_HEIGHT))

        leader   = self._cluster.get_leader() or "?"
        is_me    = self._cluster.am_i_leader()
        n_peers  = len(self._cluster.get_peers())
        dirty    = len(self._grid.dirty_cells())
        total    = ROWS * COLS
        zone_str = str(robot_s["zone"]) if robot_s["zone"] else "—"

        line1 = f"ID: {robot_s['id']}   state: {robot_s['state']}   zone cols: {zone_str}"
        line2 = (f"leader: {leader}{'  ★' if is_me else ''}   "
                 f"peers: {n_peers} ({','.join(sorted(peers.keys())) or '-'})   "
                 f"clean: {total - dirty}/{total}")

        self._screen.blit(self._font.render(line1, True, COLOR_TEXT), (8, bar_y + 8))
        self._screen.blit(self._font.render(line2, True, COLOR_TEXT), (8, bar_y + 30))
