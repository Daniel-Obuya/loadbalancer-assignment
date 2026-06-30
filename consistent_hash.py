 consistent_hash.py

class ConsistentHashMap:
    """
    Implements a consistent hash ring with virtual servers.
    
    Parameters (from assignment):
        N = 3       → number of real server containers
        M = 512     → total slots in the ring
        K = 9       → virtual servers per real server (log2(512) = 9)
    
    Hash functions:
        H(i)    = i^2 + 2i + 17         → maps a REQUEST id to a slot
        Phi(i,j)= i^2 + j^2 + 2j + 25  → maps a SERVER (i) + virtual replica (j) to a slot
    """

    def __init__(self, num_slots=512):
        self.M = num_slots                   # Total slots in the ring
        self.ring = [None] * self.M          # The actual ring (array of M slots)
        self.servers = {}                    # Maps server_name → server_id (integer)
        self.next_id = 1                     # Auto-increment server IDs

    # ── Hash functions ──────────────────────────────────────────────────────

    def _H(self, i):
        """Request hash: maps request ID i to a slot."""
        return (i * i + 2 * i + 17) % self.M

    def _Phi(self, i, j):
        """Virtual server hash: maps server i, replica j to a slot."""
        return (i * i + j * j + 2 * j + 25) % self.M

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _K(self):
        """Number of virtual servers per container = log2(M)."""
        import math
        return int(math.log2(self.M))       # = 9 when M = 512

    def _place_server(self, server_id):
        """
        Place K virtual replicas of server_id onto the ring.
        Uses linear probing if a slot is already taken.
        """
        K = self._K()
        for j in range(K):
            slot = self._Phi(server_id, j) % self.M
            # Linear probing: find next empty slot
            probes = 0
            while self.ring[slot] is not None and probes < self.M:
                slot = (slot + 1) % self.M
                probes += 1
            if probes < self.M:
                self.ring[slot] = server_id

    def _remove_server(self, server_id):
        """Remove all virtual replicas of server_id from the ring."""
        for slot in range(self.M):
            if self.ring[slot] == server_id:
                self.ring[slot] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def add_server(self, server_name):
        """
        Add a new server to the ring.
        Assigns it a unique integer ID, places K virtual nodes.
        Returns the assigned server_id.
        """
        server_id = self.next_id
        self.next_id += 1
        self.servers[server_name] = server_id
        self._place_server(server_id)
        return server_id

    def remove_server(self, server_name):
        """Remove a server and all its virtual nodes from the ring."""
        if server_name not in self.servers:
            return False
        server_id = self.servers.pop(server_name)
        self._remove_server(server_id)
        return True

    def get_server(self, request_id):
        """
        Given a request_id, find which server should handle it.
        Maps request → slot via H(), then walks clockwise to find 
        the nearest occupied slot.
        Returns the server_name, or None if ring is empty.
        """
        if not self.servers:
            return None

        # Reverse lookup: server_id → server_name
        id_to_name = {v: k for k, v in self.servers.items()}

        slot = self._H(request_id) % self.M

        # Walk clockwise until we hit an occupied slot
        for i in range(self.M):
            check = (slot + i) % self.M
            if self.ring[check] is not None:
                server_id = self.ring[check]
                return id_to_name.get(server_id)

        return None   # Ring is completely empty

    def get_all_servers(self):
        """Return list of all server names currently in the ring."""
        return list(self.servers.keys())