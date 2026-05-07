import pygame, random, socket, threading, pickle, sys, time
from collections import defaultdict

# ========== SETTINGS ==========
R, C, S = 5, 7, 80
PORT = 5555
DIRTY, CLEAN = "DIRTY", "CLEANED"

# ========== ROBOT CLASS ==========
class Robot:
    def __init__(self, rid, pos):
        self.id = rid
        self.pos = pos
        self.target = None
        self.wait = 0
        self.grid = [[DIRTY]*C for _ in range(R)]
        self.robots = {rid: {'pos': pos, 'target': None}}  # Start with just itself
        self.sock = None
    
    def find_target(self, claimed):
        """Find nearest dirty cell not claimed"""
        targets = [(r,c) for r in range(R) for c in range(C) 
                  if self.grid[r][c]==DIRTY and (r,c) not in claimed]
        return min(targets, key=lambda t: abs(t[0]-self.pos[0])+abs(t[1]-self.pos[1])) if targets else None
    
    def move_toward(self):
        if not self.target: return self.pos
        r,c = self.pos
        tr,tc = self.target
        if r < tr: return (r+1, c)
        if r > tr: return (r-1, c)
        if c < tc: return (r, c+1)
        if c > tc: return (r, c-1)
        return self.pos
    
    def update(self):
        """Update robot - works whether alone or with peers"""
        # Find target if needed
        if not self.target and not self.wait:
            claimed = set()
            # Only check other robots' targets (not self)
            for rid, rdata in self.robots.items():
                if rid != self.id and rdata.get('target'):
                    claimed.add(tuple(rdata['target']))
            self.target = self.find_target(claimed)
        
        # Move toward target
        if self.wait:
            self.wait -= 1
        elif self.target:
            next_pos = self.move_toward()
            # Only check other robots for collision (not self)
            occupied = [rdata['pos'] for rid, rdata in self.robots.items() if rid != self.id]
            if next_pos in occupied:
                self.wait = 3
            else:
                self.pos = next_pos
                # Check if reached target
                if self.pos == self.target:
                    if self.grid[self.pos[0]][self.pos[1]] == DIRTY:
                        self.grid[self.pos[0]][self.pos[1]] = CLEAN
                    self.target = None
        
        # Update own info
        self.robots[self.id] = {'pos': self.pos, 'target': self.target}

# ========== NETWORK FUNCTIONS ==========
def discover_peers():
    """Find other robots on the network"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(1)
    
    sock.sendto(b"ROBOT_HERE", ('<broadcast>', PORT))
    
    peers = []
    start = time.time()
    while time.time() - start < 2:
        try:
            data, addr = sock.recvfrom(1024)
            if data == b"ROBOT_HERE":
                peers.append(addr[0])
        except: pass
    sock.close()
    return list(set(peers))

def start_network(robot):
    """Start network threads"""
    robot.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    robot.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    robot.sock.bind(('', PORT))
    robot.sock.settimeout(0.1)
    
    def announce():
        """Broadcast presence"""
        broadcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            try:
                msg = pickle.dumps({'type': 'announce', 'id': robot.id, 'pos': robot.pos})
                broadcast.sendto(msg, ('<broadcast>', PORT))
            except: pass
            time.sleep(2)
    
    def listen():
        """Listen for other robots"""
        while True:
            try:
                data, addr = robot.sock.recvfrom(4096)
                msg = pickle.loads(data)
                
                if msg['type'] == 'announce':
                    # Add or update peer robot
                    if msg['id'] != robot.id:  # Don't add self
                        robot.robots[msg['id']] = {'pos': msg['pos'], 'target': None}
                elif msg['type'] == 'state':
                    robot.grid = msg['grid']
                    for rid, rdata in msg['robots'].items():
                        if rid != robot.id:
                            robot.robots[rid] = rdata
            except: pass
    
    def broadcast_state():
        """Share state with peers"""
        while True:
            time.sleep(1)
            peers = discover_peers()
            if peers:
                msg = pickle.dumps({
                    'type': 'state',
                    'grid': robot.grid,
                    'robots': {rid: {'pos': r['pos'], 'target': r.get('target')} 
                              for rid, r in robot.robots.items()}
                })
                for peer in peers:
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.sendto(msg, (peer, PORT))
                        s.close()
                    except: pass
    
    threading.Thread(target=announce, daemon=True).start()
    threading.Thread(target=listen, daemon=True).start()
    threading.Thread(target=broadcast_state, daemon=True).start()

# ========== VISUALIZATION ==========
def run_gui(robot):
    pygame.init()
    screen = pygame.display.set_mode((C*S, R*S))
    pygame.display.set_caption(f"Robot {robot.id}")
    font = pygame.font.Font(None, 36)
    small = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()
    move_timer = 0
    running = True
    
    while running:
        move_timer += clock.tick(60)
        if move_timer > 200:
            robot.update()
            move_timer = 0
        
        screen.fill((0,0,0))
        
        # Draw grid
        for r in range(R):
            for c in range(C):
                color = (139,69,19) if robot.grid[r][c]==DIRTY else (144,238,144)
                pygame.draw.rect(screen, color, (c*S, r*S, S-2, S-2))
        
        # Draw all robots
        for rid, rdata in robot.robots.items():
            r,c = rdata['pos']
            x,y = c*S + S//2, r*S + S//2
            color = (0,255,0) if rid == robot.id else (0,100,255)
            pygame.draw.circle(screen, color, (x,y), 18)
            txt = small.render(rid[-3:] if len(rid)>3 else rid, 1, (255,255,255))
            screen.blit(txt, (x-10, y-8))
        
        # Draw target
        if robot.target:
            tr,tc = robot.target
            x,y = tc*S + S//2, tr*S + S//2
            pygame.draw.circle(screen, (255,100,100), (x,y), 12, 2)
        
        # Draw waiting indicator
        if robot.wait:
            r,c = robot.pos
            x,y = c*S + S//2 + 15, r*S + S//2 - 15
            pygame.draw.circle(screen, (255,0,0), (x,y), 5)
        
        # Stats
        dirty = sum(row.count(DIRTY) for row in robot.grid)
        peer_count = len([rid for rid in robot.robots.keys() if rid != robot.id])
        screen.blit(font.render(f"Dirty: {dirty} | Peers: {peer_count}", 1, (255,255,255)), (10,10))
        
        # Reset when clean
        if dirty == 0:
            screen.blit(font.render("CLEAN!", 1, (0,255,0)), (C*S//2-50, R*S//2))
            pygame.display.flip()
            pygame.time.wait(3000)
            robot.grid = [[DIRTY]*C for _ in range(R)]
            robot.target = None
            robot.wait = 0
        
        pygame.display.flip()
        
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
    
    pygame.quit()

# ========== MAIN ==========
if __name__ == "__main__":
    # Get unique ID
    if len(sys.argv) > 1:
        robot_id = sys.argv[1]
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        robot_id = s.getsockname()[0].replace('.', '_')
        s.close()
    
    # Random start position
    all_cells = [(r,c) for r in range(R) for c in range(C)]
    start_pos = random.choice(all_cells)
    
    # Create robot
    robot = Robot(robot_id, start_pos)
    start_network(robot)
    run_gui(robot)