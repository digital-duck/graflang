"""Runs inside the container: sums the numbers it is given, then reports what the container lets it do."""
import json
import socket
import sys

inputs = json.load(sys.stdin)
total = sum(int(x) for x in inputs["numbers"].split(",") if x.strip())


def can(action) -> bool:
    try:
        action()
        return True
    except OSError:
        return False


network = can(lambda: socket.create_connection(("1.1.1.1", 53), timeout=2).close())
write_work = can(lambda: open("/work/new.txt", "w").close())       # the graph folder is mounted read-only
write_root = can(lambda: open("/etc/new.txt", "w").close())        # the image's root filesystem is read-only
print(json.dumps({"sum": total, "hostname": socket.gethostname(), "network": network,
                  "write_graph_folder": write_work, "write_root": write_root}))
