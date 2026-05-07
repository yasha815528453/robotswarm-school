"""
Multi-Roomba simulator
Usage: python main.py <robot_id> [--row R] [--col C]

Each robot ID must be unique across the fleet. IDs are sorted lexicographically
to elect a leader — higher ID wins (e.g. "C" leads "A" and "B").
"""
import argparse
import logging
import queue
import threading
import time

import pygame

from cluster import Cluster
from config import HEARTBEAT_INTERVAL, RESET_DELAY, TICK_INTERVAL
from coordinator import Coordinator
from grid import Grid
from gui import Gui
from network import Network
from protocol import (
    ANNOUNCE, GOODBYE, GRID_UPDATE, HEARTBEAT, RESET, ZONE_ASSIGN,
    decode, encode,
)
from robot import Robot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("main")


def main():
    parser = argparse.ArgumentParser(description="Multi-Roomba simulator")
    parser.add_argument("robot_id", help="Unique robot ID, e.g. A, B, C")
    parser.add_argument("--row", type=int, default=0, help="Start row (default 0)")
    parser.add_argument("--col", type=int, default=0, help="Start col (default 0)")
    args = parser.parse_args()

    robot_id = args.robot_id

    # ── shared state ──────────────────────────────────────────────────────
    grid        = Grid()
    robot       = Robot(robot_id, start_row=args.row, start_col=args.col)
    cluster     = Cluster(robot_id)
    coordinator = Coordinator()
    incoming: queue.Queue = queue.Queue()

    net = Network(incoming)
    gui = Gui(grid, robot, cluster, coordinator)

    net.start()
    gui.init()

    # Used to serialize re-election calls from multiple threads
    _reelect_lock = threading.Lock()

    # ── helpers ───────────────────────────────────────────────────────────

    def reelect_and_assign():
        """Recompute leader and, if we are it, broadcast all zone assignments."""
        if not _reelect_lock.acquire(blocking=False):
            return
        try:
            leader = cluster.elect_leader()
            logger.info("leader: %s%s", leader, " (me)" if cluster.am_i_leader() else "")
            if cluster.am_i_leader():
                members = cluster.all_member_ids()
                zones = coordinator.assign_zones(members)
                # Apply our own zone locally
                if robot_id in zones:
                    robot.zone = zones[robot_id]
                # Broadcast all assignments in one packet — every peer reads its own
                payload = {rid: list(z) for rid, z in zones.items()}
                net.send_broadcast(encode(ZONE_ASSIGN, payload, robot_id))
        finally:
            _reelect_lock.release()

    def broadcast_grid():
        # Bundle our live state with the grid so peers track our position at tick rate, not heartbeat rate.
        payload = {"cells": grid.to_list(), "state": my_state()}
        net.send_broadcast(encode(GRID_UPDATE, payload, robot_id))

    def my_state() -> dict:
        s = robot.snapshot()
        return {
            "ip":     cluster.my_ip,
            "row":    s["row"],
            "col":    s["col"],
            "zone":   list(s["zone"]) if s["zone"] else None,
            "rstate": s["state"],
        }

    # ── threads ───────────────────────────────────────────────────────────

    def heartbeat_loop():
        while True:
            time.sleep(HEARTBEAT_INTERVAL)
            net.send_broadcast(encode(HEARTBEAT, my_state(), robot_id))
            dead = cluster.expire_dead_peers()
            if dead:
                logger.info("peers timed out: %s", dead)
                reelect_and_assign()

    def tick_loop():
        reset_at: float | None = None
        while True:
            time.sleep(TICK_INTERVAL)

            changed = robot.step(grid)

            # Every robot broadcasts its (monotonic) clean-set on change.
            # Receivers union-merge — no overwrite, so no race-condition wipes.
            if changed:
                broadcast_grid()

            if grid.all_clean():
                if reset_at is None:
                    reset_at = time.monotonic()
                elif time.monotonic() - reset_at >= RESET_DELAY:
                    if cluster.am_i_leader():
                        logger.info("grid fully clean — broadcasting RESET")
                        grid.reset()
                        net.send_broadcast(encode(RESET, {}, robot_id))
                    reset_at = None
            else:
                reset_at = None

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
                continue  # own echo

            if msg_type == ANNOUNCE:
                cluster.update_peer(sender, payload["ip"])
                # Catch the new peer up on our current clean set
                broadcast_grid()
                reelect_and_assign()

            elif msg_type == HEARTBEAT:
                # Heartbeat carries live peer state (position, zone, etc.)
                cluster.update_peer(sender, payload.get("ip", src_ip), state=payload)
                if cluster.get_leader() is None:
                    reelect_and_assign()

            elif msg_type == ZONE_ASSIGN:
                # Payload is {robot_id: [col_start, col_end], ...} — read our own
                if robot_id in payload:
                    zone = tuple(payload[robot_id])
                    robot.zone = zone
                    logger.info("zone assigned: cols %s–%s", zone[0], zone[1])
                # Reflect everyone's zones in the local coordinator view (for GUI)
                coordinator.assign_zones(list(payload.keys()))

            elif msg_type == GRID_UPDATE:
                # Always merge — cleaning is monotonic, so union is the safe op.
                grid.merge(payload["cells"])
                # Update peer's live position from the bundled state, if present
                peer_state = payload.get("state")
                if peer_state:
                    cluster.update_peer(sender, peer_state.get("ip", src_ip), state=peer_state)

            elif msg_type == RESET:
                logger.info("RESET received from %s", sender)
                grid.reset()

            elif msg_type == GOODBYE:
                cluster.remove_peer(sender)
                reelect_and_assign()

    # ── startup ───────────────────────────────────────────────────────────

    net.send_broadcast(encode(ANNOUNCE, {"ip": cluster.my_ip}, robot_id))
    reelect_and_assign()  # boot as sole member

    threading.Thread(target=heartbeat_loop, daemon=True, name="heartbeat").start()
    threading.Thread(target=tick_loop,      daemon=True, name="tick").start()
    threading.Thread(target=dispatch_loop,  daemon=True, name="dispatch").start()

    # GUI runs on the main thread (pygame requirement)
    try:
        while gui.handle_events():
            gui.draw()
    finally:
        net.send_broadcast(encode(GOODBYE, {}, robot_id))
        net.stop()
        pygame.quit()


if __name__ == "__main__":
    main()
