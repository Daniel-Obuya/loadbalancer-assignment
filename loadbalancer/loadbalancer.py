from flask import Flask, jsonify, request
import os
import random
import string
import threading
import time
import requests as http

from consistent_hash import ConsistentHashMap

app = Flask(__name__)

# Config
DOCKER_NETWORK = "loadbalancer-assignment_net1"
SERVER_IMAGE = "server:latest"
N = int(os.environ.get("N", 3))

hash_map = ConsistentHashMap(num_slots=512)
lock = threading.Lock()


def _rand_name():
    return "S_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _start_container(name):
    cmd = "sudo docker run --name " + name + " --network " + DOCKER_NETWORK + " --network-alias " + name + " -e SERVER_ID=" + name + " -d server:latest"
    print("[start_container] Running: " + cmd)
    result = os.popen(cmd).read().strip()
    print("[start_container] Result: " + result)
    return len(result) > 0


def _stop_container(name):
    os.system("sudo docker stop " + name + " > /dev/null 2>&1")
    os.system("sudo docker rm " + name + " > /dev/null 2>&1")


def _container_alive(name):
    try:
        r = http.get("http://" + name + ":5000/heartbeat", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _bootstrap():
    time.sleep(2)
    for i in range(1, N + 1):
        name = "Server_" + str(i)
        with lock:
            hash_map.add_server(name)
        _start_container(name)


threading.Thread(target=_bootstrap, daemon=True).start()


def _watchdog():
    while True:
        time.sleep(5)
        with lock:
            current = hash_map.get_all_servers()[:]
        for name in current:
            if not _container_alive(name):
                print("[watchdog] " + name + " is down, replacing")
                with lock:
                    hash_map.remove_server(name)
                _stop_container(name)
                new_name = _rand_name()
                with lock:
                    hash_map.add_server(new_name)
                _start_container(new_name)


threading.Thread(target=_watchdog, daemon=True).start()


@app.route("/rep", methods=["GET"])
def rep():
    with lock:
        servers = hash_map.get_all_servers()
    return jsonify({
        "message": {"N": len(servers), "replicas": servers},
        "status": "successful"
    }), 200


@app.route("/add", methods=["POST"])
def add():
    data = request.get_json()
    n = data.get("n", 0)
    hostnames = data.get("hostnames", [])

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than newly added instances",
            "status": "failure"
        }), 400

    names = hostnames + [_rand_name() for _ in range(n - len(hostnames))]

    for name in names:
        with lock:
            hash_map.add_server(name)
        ok = _start_container(name)
        if not ok:
            with lock:
                hash_map.remove_server(name)

    with lock:
        all_servers = hash_map.get_all_servers()

    return jsonify({
        "message": {"N": len(all_servers), "replicas": all_servers},
        "status": "successful"
    }), 200

@app.route("/rm", methods=["DELETE"])
def rm():
    data = request.get_json()
    n = data.get("n", 0)
    hostnames = data.get("hostnames", [])

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than removable instances",
            "status": "failure"
        }), 400

    with lock:
        current = hash_map.get_all_servers()[:]

    # Only keep hostnames that actually exist
    valid_hostnames = [h for h in hostnames if h in current]
    to_remove = list(valid_hostnames)
    remaining = [s for s in current if s not in to_remove]

    # Fill the rest randomly
    extra_needed = n - len(to_remove)
    if extra_needed > len(remaining):
        return jsonify({
            "message": "<Error> Not enough servers to remove",
            "status": "failure"
        }), 400

    to_remove += random.sample(remaining, extra_needed)

    for name in to_remove:
        with lock:
            hash_map.remove_server(name)
        _stop_container(name)

    with lock:
        all_servers = hash_map.get_all_servers()

    return jsonify({
        "message": {"N": len(all_servers), "replicas": all_servers},
        "status": "successful"
    }), 200

@app.route("/<path:path>", methods=["GET"])
def route_request(path):
    request_id = random.randint(100000, 999999)
    with lock:
        server = hash_map.get_server(request_id)

    if server is None:
        return jsonify({
            "message": "<Error> No servers available",
            "status": "failure"
        }), 503

    try:
        resp = http.get("http://" + server + ":5000/" + path, timeout=5)
        return jsonify(resp.json()), resp.status_code
    except Exception:
        return jsonify({
            "message": "<Error> '/" + path + "' endpoint does not exist in server replicas",
            "status": "failure"
        }), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)