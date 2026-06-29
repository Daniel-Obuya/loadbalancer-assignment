# ICS 4104: Distributed Systems
# Assignment 1: Customizable Load Balancer

## Group Members
| Name | Task |
|------|------|
| Daniel Obuya | Task 1: Server Implementation |
| Elvis Wafuke| Task 2: Consistent Hashing |
| Sam Macharia | Task 3: Load Balancer |
| Melissa Andeti | Task 4: Analysis & Documentation |

---

## Overview
This project implements a customizable load balancer that distributes 
incoming client requests across multiple server replicas using consistent 
hashing. The system is fully containerized using Docker and supports 
dynamic scaling — servers can be added or removed at runtime. The load 
balancer also monitors server health and automatically replaces failed 
instances to maintain the desired number of replicas.

---

## Project Structure
loadbalancer-assignment/

├── server/

│   ├── server.py           # Flask web server with /home and /heartbeat

│   └── Dockerfile          # Server container definition

├── loadbalancer/

│   ├── consistent_hash.py  # Consistent hash ring implementation

│   ├── loadbalancer.py     # Load balancer logic and API endpoints

│   └── Dockerfile          # Load balancer container definition

├── docker-compose.yml      # Orchestrates the full stack

├── Makefile                # Shortcuts for build and deploy

├── test_analysis.py        # Script for Task 4 performance analysis

└── README.md               # Project documentation

---

## Technologies Used
- **Language:** Python 3.10
- **Web Framework:** Flask
- **Containerization:** Docker & Docker Compose
- **Async Testing:** aiohttp
- **OS:** Ubuntu 20.04 (WSL2)

---

## Setup & Deployment

### Prerequisites
- Docker Desktop (v20.10.23 or above) with WSL2 integration enabled
- Ubuntu 20.04 or above
- Python 3.10 (for running analysis scripts locally)

### Deploy the Full Stack
```bash
# Build the server image and start the load balancer
make up
```

### Stop Everything
```bash
make down
```

### View Load Balancer Logs
```bash
make logs
```

### Run Tests
```bash
make test
```

---

## API Endpoints

### GET /rep
Returns the current number of server replicas and their hostnames.

**Example Response:**
```json
{
  "message": {
    "N": 3,
    "replicas": ["Server_1", "Server_2", "Server_3"]
  },
  "status": "successful"
}
```

### POST /add
Adds new server instances to the load balancer.

**Example Request:**
```json
{
  "n": 2,
  "hostnames": ["S4", "S5"]
}
```

**Example Response:**
```json
{
  "message": {
    "N": 5,
    "replicas": ["Server_1", "Server_2", "Server_3", "S4", "S5"]
  },
  "status": "successful"
}
```

**Error (hostnames > n):**
```json
{
  "message": "<Error> Length of hostname list is more than newly added instances",
  "status": "failure"
}
```

### DELETE /rm
Removes server instances from the load balancer.

**Example Request:**
```json
{
  "n": 1,
  "hostnames": ["S4"]
}
```

**Example Response:**
```json
{
  "message": {
    "N": 4,
    "replicas": ["Server_1", "Server_2", "Server_3", "S5"]
  },
  "status": "successful"
}
```

**Error (hostnames > n):**
```json
{
  "message": "<Error> Length of hostname list is more than removable instances",
  "status": "failure"
}
```

### GET /<path>
Routes the request to a server replica selected by the consistent 
hashing algorithm.

**Example Response (GET /home):**
```json
{
  "message": "Hello from Server: Server_1",
  "status": "successful"
}
```

**Error (invalid endpoint):**
```json
{
  "message": "<Error> '/other' endpoint does not exist in server replicas",
  "status": "failure"
}
```

---

## Design Choices

### 1. Consistent Hashing
We implemented a consistent hash ring with the following parameters 
as specified in the assignment:

| Parameter | Value |
|-----------|-------|
| Total slots (M) | 512 |
| Virtual servers per container (K) | log₂(512) = 9 |
| Request hash H(i) | i² + 2i + 17 |
| Server hash Φ(i, j) | i² + j² + 2j + 25 |

The hash ring is represented as an array of 512 slots. Each physical 
server is placed into the ring K=9 times using different virtual 
server replica IDs. Client requests are mapped to a slot using H(i) 
and then assigned to the nearest server in the clockwise direction.

### 2. Conflict Resolution
When two servers hash to the same slot, **linear probing** is used — 
the algorithm walks forward through the ring until an empty slot is 
found. This ensures all virtual nodes are placed without collision.

### 3. Load Balancer as a Privileged Container
The load balancer runs as a privileged Docker container with access 
to the host Docker socket (`/var/run/docker.sock`). This allows it 
to spawn and remove server containers dynamically at runtime without 
any external orchestration tool.

### 4. Failure Detection and Recovery
A background **watchdog thread** runs inside the load balancer and 
pings each server's `/heartbeat` endpoint every 5 seconds. If a 
server fails to respond, the watchdog:
1. Removes the server from the consistent hash ring
2. Stops and removes its Docker container
3. Spawns a new replacement container with a randomly generated name
4. Adds the new container to the hash ring

This ensures N replicas are always maintained even during failures.

### 5. Thread Safety
All operations on the shared consistent hash map are protected by a 
**threading lock** to prevent race conditions between the Flask 
request handlers and the watchdog thread.

---

## Assumptions
- Server containers communicate with the load balancer over the 
  internal Docker network `loadbalancer-assignment_net1`.
- Request IDs are randomly generated 6-digit integers for each 
  incoming request, as specified in the assignment.
- If a preferred hostname fails to start as a container, it is 
  rolled back from the hash ring automatically.
- The load balancer always maintains exactly N=3 server replicas 
  on startup unless modified via the /add or /rm endpoints.
- Hostnames in /add and /rm are treated as preferred, not mandatory — 
  if fewer hostnames than n are provided, the remainder are randomly named.

---

## Task 4: Performance Analysis

### A-1: Load Distribution with N=3, 10,000 Requests

We launched 10,000 asynchronous requests against the load balancer 
with N=3 server containers and recorded how many requests each 
server handled.

| Server | Requests Handled | Percentage |
|--------|-----------------|------------|
| Server_1 | 8,401 | 84.0% |
| Server_2 | 464 | 4.6% |
| Server_3 | 1,135 | 11.4% |
| **Total** | **10,000** | **100%** |

**Observation:**
The distribution is noticeably uneven. Server_1 handles the vast 
majority of requests (84%) while Server_2 handles very few (4.6%). 
This happens because the hash functions H(i) and Φ(i,j) place the 
9 virtual nodes of each server at specific positions in the 512-slot 
ring. Some servers end up covering larger arcs of the ring than 
others, meaning more request hashes fall within their range. With 
only K=9 virtual nodes per server, there is not enough spread to 
guarantee even distribution. Increasing K would improve balance but 
at the cost of more memory usage.

### A-2: Scalability — Average Load per Server (N=2 to 6)

We incremented N from 2 to 6 and launched 10,000 requests at each 
increment, recording the average load per server.

| N (Servers) | Total Requests | Avg Load Per Server |
|-------------|---------------|-------------------|
| 2 | 10,000 | 5,000.0 |
| 3 | 10,000 | 3,333.3 |
| 4 | 10,000 | 2,491.2 |
| 5 | 10,000 | 1,993.8 |
| 6 | 10,000 | 1,666.7 |

**Observation:**
As N increases, the average load per server decreases consistently, 
following an approximately inverse relationship (≈ 10,000 / N). 
This confirms the load balancer scales correctly with the number of 
server replicas. Adding more servers reliably reduces the burden on 
each individual server. This demonstrates good horizontal scalability 
— the system can handle increasing client load simply by adding more 
server containers via the /add endpoint without any downtime.

### A-3: Endpoint Testing and Failure Recovery

All endpoints were tested and verified to work correctly:

| Test | Expected | Result |
|------|----------|--------|
| GET /rep | Returns replica list | ✅ Pass |
| POST /add (valid) | Adds servers | ✅ Pass |
| POST /add (hostnames > n) | Returns error | ✅ Pass |
| DELETE /rm (valid) | Removes servers | ✅ Pass |
| DELETE /rm (hostnames > n) | Returns error | ✅ Pass |
| GET /home | Routes to server | ✅ Pass |
| GET /other | Returns error | ✅ Pass |
| Server failure recovery | Watchdog replaces server | ✅ Pass |

**Failure Recovery Test:**
We manually killed a server container using `docker kill Server_1`. 
After 10 seconds, the watchdog detected the failure and automatically 
spawned a replacement container with a randomly generated name. The 
replica count remained at N=3 throughout, confirming the failure 
recovery mechanism works correctly.

### A-4: Modified Hash Functions

We tested alternative hash functions to observe their effect on 
load distribution:

**Modified functions:**
- H(i) = i² + 3i + 11 (was i² + 2i + 17)
- Φ(i,j) = i² + j² + 3j + 17 (was i² + j² + 2j + 25)

**Observation:**
Different hash functions produce different virtual node placements 
on the ring, leading to different load distributions. The original 
functions produced an 84/4.6/11.4% split across 3 servers. Modified 
functions shift the arc sizes differently, which may improve or 
worsen balance depending on where the virtual nodes land relative 
to the request hash distribution. This highlights that the choice 
of hash function significantly impacts load balancer performance, 
and tuning these functions is an important consideration in 
production systems.

---
