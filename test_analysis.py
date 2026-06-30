import asyncio
import aiohttp
import requests
from collections import defaultdict

async def send_request(session, url, counts):
    try:
        async with session.get(url) as resp:
            data = await resp.json()
            msg = data.get("message", "")
            if isinstance(msg, dict):
                return
            if "Hello from Server:" in msg:
                server = msg.split("Hello from Server:")[1].strip()
                counts[server] += 1
    except Exception:
        pass

async def run_requests(n_requests=10000):
    url = "http://localhost:5000/home"
    counts = defaultdict(int)
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, url, counts) for _ in range(n_requests)]
        await asyncio.gather(*tasks)
    return counts

def set_servers(target_n):
    """Add or remove servers to reach target N."""
    resp = requests.get("http://localhost:5000/rep").json()
    current = resp["message"]["replicas"]
    current_n = len(current)

    if target_n > current_n:
        diff = target_n - current_n
        requests.post("http://localhost:5000/add",
            json={"n": diff, "hostnames": []})
    elif target_n < current_n:
        diff = current_n - target_n
        requests.delete("http://localhost:5000/rm",
            json={"n": diff, "hostnames": []})

    import time
    time.sleep(3)  # wait for containers to start

print("\n=== A-1: Request Distribution (N=3) ===")
counts_a1 = asyncio.run(run_requests(10000))
for server, count in sorted(counts_a1.items()):
    print(f"  {server}: {count} requests")
print(f"  Total: {sum(counts_a1.values())}")

print("\n=== A-2: Average Load vs N ===")
for n in range(2, 7):
    set_servers(n)
    counts = asyncio.run(run_requests(10000))
    total = sum(counts.values())
    avg = total / n if n > 0 else 0
    print(f"  N={n}: avg load per server = {avg:.1f} requests")