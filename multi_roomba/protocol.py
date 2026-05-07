import json

ANNOUNCE    = "ANNOUNCE"
HEARTBEAT   = "HEARTBEAT"
ZONE_ASSIGN = "ZONE_ASSIGN"
GRID_UPDATE = "GRID_UPDATE"
RESET       = "RESET"
GOODBYE     = "GOODBYE"


def encode(msg_type: str, payload: dict, sender_id: str) -> bytes:
    return json.dumps({"type": msg_type, "sender": sender_id, "payload": payload}).encode()


def decode(data: bytes) -> dict:
    return json.loads(data.decode())
