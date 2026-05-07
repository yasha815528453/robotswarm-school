import socket
import threading
import time
from config import PEER_TIMEOUT


class Cluster:
    """
    Pure peer-to-peer membership. No leader, no election.
    Priority is implicit and alphabetical: lower ID == higher priority (A > B > C).
    """

    def __init__(self, my_id: str):
        self.my_id = my_id
        self.my_ip = _local_ip()
        self._lock = threading.Lock()
        # peer_id -> {"ip": str, "last_seen": float, "state": dict}
        self._peers: dict[str, dict] = {}

    def update_peer(self, peer_id: str, peer_ip: str, state: dict | None = None):
        with self._lock:
            entry = self._peers.get(peer_id, {})
            entry["ip"] = peer_ip
            entry["last_seen"] = time.monotonic()
            if state is not None:
                entry["state"] = state
            self._peers[peer_id] = entry

    def remove_peer(self, peer_id: str):
        with self._lock:
            self._peers.pop(peer_id, None)

    def expire_dead_peers(self) -> list[str]:
        now = time.monotonic()
        removed = []
        with self._lock:
            dead = [pid for pid, info in self._peers.items()
                    if now - info["last_seen"] > PEER_TIMEOUT]
            for pid in dead:
                del self._peers[pid]
                removed.append(pid)
        return removed

    def get_peers(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._peers)

    def get_peer_states(self) -> dict[str, dict]:
        with self._lock:
            return {pid: info["state"] for pid, info in self._peers.items() if "state" in info}

    def all_member_ids(self) -> list[str]:
        with self._lock:
            return [self.my_id] + list(self._peers.keys())

    # ── priority helpers ──────────────────────────────────────────────────

    def higher_priority_peer_ids(self) -> list[str]:
        """Peer IDs that outrank us alphabetically (lower string == higher priority)."""
        with self._lock:
            return [pid for pid in self._peers.keys() if pid < self.my_id]

    def is_highest_priority(self) -> bool:
        """True iff we are the alphabetically-smallest live member."""
        return min(self.all_member_ids()) == self.my_id


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
