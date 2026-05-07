import socket
import threading
import time
from config import LEADER_TIMEOUT


class Cluster:
    def __init__(self, my_id: str):
        self.my_id = my_id
        self.my_ip = _local_ip()
        self._lock = threading.Lock()
        # peer_id -> {"ip": str, "last_seen": float}
        self._peers: dict[str, dict] = {}
        self._leader_id: str | None = None

    # ── peer tracking ─────────────────────────────────────────────────────

    def update_peer(self, peer_id: str, peer_ip: str):
        with self._lock:
            self._peers[peer_id] = {"ip": peer_ip, "last_seen": time.monotonic()}

    def remove_peer(self, peer_id: str):
        with self._lock:
            self._peers.pop(peer_id, None)

    def expire_dead_peers(self) -> list[str]:
        """Drop peers silent for longer than LEADER_TIMEOUT. Returns removed IDs."""
        now = time.monotonic()
        removed = []
        with self._lock:
            dead = [pid for pid, info in self._peers.items()
                    if now - info["last_seen"] > LEADER_TIMEOUT]
            for pid in dead:
                del self._peers[pid]
                removed.append(pid)
        return removed

    def get_peers(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._peers)

    def all_member_ids(self) -> list[str]:
        with self._lock:
            return [self.my_id] + list(self._peers.keys())

    # ── leader election ───────────────────────────────────────────────────

    def elect_leader(self) -> str:
        """Each node independently picks max(member_ids). Converges when membership is consistent."""
        members = self.all_member_ids()
        leader = max(members)
        with self._lock:
            self._leader_id = leader
        return leader

    def am_i_leader(self) -> bool:
        with self._lock:
            return self._leader_id == self.my_id

    def get_leader(self) -> str | None:
        with self._lock:
            return self._leader_id

    def peer_ip(self, peer_id: str) -> str | None:
        with self._lock:
            info = self._peers.get(peer_id)
            return info["ip"] if info else None


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
