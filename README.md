school project:

multi-roomba mrs

Run:

python main.py A

python main.py B  # on a second computer
...

###
Decentralized: every node runs identical code.

Gossip protocol: Every robot broadcasts its full state.

Priority ordering by robot ID: higher-id robots avoid lower-id robots' current cell.

uses BFS to look for dirty squares, avoids blocked squares (by other robots), passes over clean squares.
