import json

# Single state-bearing message replaces HEARTBEAT + GRID_UPDATE + ZONE_ASSIGN.
# It carries everything peers need: position, target, path, grid clean-set.
ANNOUNCE = "ANNOUNCE"
STATE    = "STATE"
RESET    = "RESET"
GOODBYE  = "GOODBYE"


def encode(msg_type: str, payload: dict, sender_id: str) -> bytes:
    return json.dumps({"type": msg_type, "sender": sender_id, "payload": payload}).encode()


def decode(data: bytes) -> dict:
    return json.loads(data.decode())
