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
    ANNOUNCE, GOODBYE, GRID_UPDATE, HEARTBEAT, ZONE_ASSIGN,
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
        """Recompute leader and, if we are it, push zone assignments."""
        if not _reelect_lock.acquire(blocking=False):
            return
        try:
            leader = cluster.elect_leader()
            logger.info("leader: %s%s", leader, " (me)" if cluster.am_i_leader() else "")
            if cluster.am_i_leader():
                members = cluster.all_member_ids()
                zones = coordinator.assign_zones(members)
                for rid, zone in zones.items():
                    if rid == robot_id:
                        robot.zone = zone
                    else:
                        ip = cluster.peer_ip(rid)
                        if ip:
                            msg = encode(ZONE_ASSIGN, {"robot_id": rid, "zone": list(zone)}, robot_id)
                            net.send_unicast(ip, msg)
        finally:
            _reelect_lock.release()

    def broadcast_grid():
        net.send_broadcast(encode(GRID_UPDATE, {"cells": grid.to_list()}, robot_id))

    def push_grid_to_leader():
        leader_id = cluster.get_leader()
        if leader_id and leader_id != robot_id:
            ip = cluster.peer_ip(leader_id)
            if ip:
                net.send_unicast(ip, encode(GRID_UPDATE, {"cells": grid.to_list()}, robot_id))

    # ── threads ───────────────────────────────────────────────────────────

    def heartbeat_loop():
        while True:
            time.sleep(HEARTBEAT_INTERVAL)
            net.send_broadcast(encode(HEARTBEAT, {"ip": cluster.my_ip}, robot_id))
            dead = cluster.expire_dead_peers()
            if dead:
                logger.info("peers timed out: %s", dead)
                reelect_and_assign()

    def tick_loop():
        reset_at: float | None = None
        while True:
            time.sleep(TICK_INTERVAL)

            changed = robot.step(grid)

            if changed:
                if cluster.am_i_leader():
                    broadcast_grid()
                else:
                    push_grid_to_leader()

            if grid.all_clean():
                if reset_at is None:
                    reset_at = time.monotonic()
                elif time.monotonic() - reset_at >= RESET_DELAY:
                    logger.info("grid fully clean — resetting")
                    grid.reset()
                    reset_at = None
                    if cluster.am_i_leader():
                        broadcast_grid()
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
                # Send our current grid so the new peer can sync
                net.send_unicast(payload["ip"],
                                 encode(GRID_UPDATE, {"cells": grid.to_list()}, robot_id))
                reelect_and_assign()

            elif msg_type == HEARTBEAT:
                cluster.update_peer(sender, payload["ip"])
                if cluster.get_leader() is None:
                    reelect_and_assign()

            elif msg_type == ZONE_ASSIGN:
                if payload["robot_id"] == robot_id:
                    zone = tuple(payload["zone"])
                    robot.zone = zone
                    logger.info("zone assigned: cols %s–%s", zone[0], zone[1])

            elif msg_type == GRID_UPDATE:
                cells = payload["cells"]
                if cluster.am_i_leader():
                    # Merge non-leader updates into master grid, then rebroadcast
                    grid.merge(cells)
                    broadcast_grid()
                elif sender == cluster.get_leader():
                    # Accept authoritative state from leader
                    grid.from_list(cells)

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
