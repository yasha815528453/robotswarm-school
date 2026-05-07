import socket
import threading
import queue
import logging
from config import UDP_PORT, BROADCAST_ADDR

logger = logging.getLogger(__name__)


class Network:
    def __init__(self, incoming: queue.Queue):
        self._queue = incoming
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.bind(("", UDP_PORT))
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._listen, daemon=True, name="net-listener").start()

    def stop(self):
        self._running = False
        try:
            self._sock.close()
        except OSError:
            pass

    def send_broadcast(self, msg: bytes):
        try:
            self._sock.sendto(msg, (BROADCAST_ADDR, UDP_PORT))
        except OSError as e:
            logger.debug("broadcast failed: %s", e)

    def send_unicast(self, ip: str, msg: bytes):
        try:
            self._sock.sendto(msg, (ip, UDP_PORT))
        except OSError as e:
            logger.debug("unicast to %s failed: %s", ip, e)

    def _listen(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(65536)
                self._queue.put((data, addr))
            except OSError:
                break
