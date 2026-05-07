"""
Multi-Roomba simulator — fully decentralized, peer-to-peer.

Usage: python main.py <robot_id> [--row R] [--col C]

There is no leader and no zone assignment. Each robot:
  • broadcasts its STATE (position, target, path, clean-set) at BROADCAST_INTERVAL
  • steps its own logic at TICK_INTERVAL, wall-clock-synced across laptops
  • picks the nearest dirty cell that no higher-priority peer has claimed
  • routes around higher-priority peers' positions/targets/paths via BFS

Priority is purely alphabetical: lower ID == higher priority.
So among {A, B, C}, A wins all ties, then B, then C.
"""
import argparse
import logging
import queue
import threading
import time

import pygame

from cluster import Cluster
from config import BROADCAST_INTERVAL, RESET_DELAY, TICK_INTERVAL
from grid import Grid
from gui import Gui
from network import Network
from protocol import ANNOUNCE, GOODBYE, RESET, STATE, decode, encode
from robot import Robot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("main")


def main():
    parser = argparse.ArgumentParser(description="Multi-Roomba simulator")
    parser.add_argument("robot_id", help="Unique robot ID, e.g. A, B, C")
    parser.add_argument("--row", type=int, default=0)
    parser.add_argument("--col", type=int, default=0)
    args = parser.parse_args()

    robot_id = args.robot_id

    grid     = Grid()
    robot    = Robot(robot_id, start_row=args.row, start_col=args.col)
    cluster  = Cluster(robot_id)
    incoming: queue.Queue = queue.Queue()

    net = Network(incoming)
    gui = Gui(grid, robot, cluster)

    net.start()
    gui.init()

    # ── helpers ───────────────────────────────────────────────────────────

    def my_state() -> dict:
        s = robot.snapshot()
        return {
            "ip":     cluster.my_ip,
            "row":    s["row"],
            "col":    s["col"],
            "target": list(s["target"]) if s["target"] else None,
            "path":   [list(p) for p in s["path"]],
            "rstate": s["state"],
            "cells":  grid.to_list(),
        }

    def broadcast_state():
        net.send_broadcast(encode(STATE, my_state(), robot_id))

    def claimed_cells() -> set[tuple[int, int]]:
        """
        Cells we must avoid when picking targets / planning paths:
          • every other peer's current position (no two robots share a cell)
          • every higher-priority peer's target and remaining path
        """
        blocked: set[tuple[int, int]] = set()
        for pid, st in cluster.get_peer_states().items():
            row, col = st.get("row"), st.get("col")
            if row is not None and col is not None:
                blocked.add((row, col))                  # peer occupancy
            if pid < robot_id:                            # higher priority than us
                if st.get("target"):
                    blocked.add(tuple(st["target"]))
                for cell in st.get("path") or []:
                    blocked.add(tuple(cell))
        return blocked

    # ── threads ───────────────────────────────────────────────────────────

    def broadcast_loop():
        """High-frequency state broadcast keeps peer views smooth + dropout-tolerant."""
        while True:
            time.sleep(BROADCAST_INTERVAL)
            broadcast_state()

    def tick_loop():
        """Wall-clock-synced movement tick. Every robot fires at the same instant."""
        reset_at: float | None = None
        while True:
            now = time.time()
            next_tick = (int(now / TICK_INTERVAL) + 1) * TICK_INTERVAL
            time.sleep(max(0.0, next_tick - now))

            robot.step(grid, blocked=claimed_cells())
            broadcast_state()

            # Idempotent reset: only the highest-priority live robot triggers it.
            if grid.all_clean():
                if reset_at is None:
                    reset_at = time.monotonic()
                elif time.monotonic() - reset_at >= RESET_DELAY:
                    if cluster.is_highest_priority():
                        logger.info("grid clean — broadcasting RESET")
                        grid.reset()
                        net.send_broadcast(encode(RESET, {}, robot_id))
                    reset_at = None
            else:
                reset_at = None

    def membership_loop():
        """Periodic peer-timeout sweep. No leader election — just drop stale peers."""
        while True:
            time.sleep(BROADCAST_INTERVAL * 2)
            dead = cluster.expire_dead_peers()
            for d in dead:
                logger.info("peer %s timed out", d)

    def dispatch_loop():
        while True:
            try:
                data, (src_ip, _) = incoming.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                msg = decode(data)
            except Exception:
                continue

            msg_type = msg["type"]
            sender   = msg["sender"]
            payload  = msg["payload"]
            if sender == robot_id:
                continue

            if msg_type == STATE:
                cluster.update_peer(sender, payload.get("ip", src_ip), state=payload)
                if "cells" in payload:
                    grid.merge(payload["cells"])

            elif msg_type == ANNOUNCE:
                cluster.update_peer(sender, payload.get("ip", src_ip))
                broadcast_state()                          # catch the new peer up

            elif msg_type == RESET:
                logger.info("RESET received from %s", sender)
                grid.reset()

            elif msg_type == GOODBYE:
                cluster.remove_peer(sender)

    # ── startup ───────────────────────────────────────────────────────────

    net.send_broadcast(encode(ANNOUNCE, {"ip": cluster.my_ip}, robot_id))

    threading.Thread(target=broadcast_loop,  daemon=True, name="broadcast").start()
    threading.Thread(target=tick_loop,       daemon=True, name="tick").start()
    threading.Thread(target=membership_loop, daemon=True, name="membership").start()
    threading.Thread(target=dispatch_loop,   daemon=True, name="dispatch").start()

    try:
        while gui.handle_events():
            gui.draw()
    finally:
        net.send_broadcast(encode(GOODBYE, {}, robot_id))
        net.stop()
        pygame.quit()


if __name__ == "__main__":
    main()
