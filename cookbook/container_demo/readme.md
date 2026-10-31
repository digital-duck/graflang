# container_demo

A program run inside a Docker container. `solvers/probe.py` sums the numbers it is given and then reports what the container allowed it to do: reach the network, write to the graph folder, write to the image's root filesystem. No model.

```
wf_entry -> probe (SOLVE, backend: subprocess, container: python:3.12-slim) -> done
```

| | |
|---|---|
| Input | `numbers` (TEXT, default `1,2,3`) |
| Output | `report` (JSON): `sum`, the container's `hostname`, and `network`, `write_graph_folder`, `write_root` (all `false`) |
| LLM calls | 0 |
| Needs | a running Docker daemon and `docker pull python:3.12-slim` |

## Run

```bash
docker pull python:3.12-slim
graf run cookbook/container_demo/container_demo.graph.yaml --param numbers=4,5,6
# Output: {'report': {'sum': 15, 'hostname': '<container id>', 'network': False, 'write_graph_folder': False, 'write_root': False}}
```

## What `container:` does

The node's `command` runs in `docker run` with: no network (`network: none`, the default), a read-only root filesystem with a tmpfs `/tmp`, every capability dropped, no new privileges, this folder mounted read-only at `/work` (the working directory), and caps on memory, CPU and processes (`memory_mb`, `cpus`, `pids`). Environment variables listed in `env_passthrough` are handed in by name; nothing else of your environment enters. A timeout removes the container. `network: bridge` and `mount: rw` or `none` are the only ways to widen or drop the mount. A MUTATE can never add or change `container`.

## Docker Desktop

Docker Desktop runs containers in a VM that sees only the folders shared with it, by default your home directory. Mounting any other folder (for example a graph under `/tmp`) does not fail, it hangs, so graflang checks first and stops with a message naming the folder. Either keep the graph under your home directory, or add the folder in Docker Desktop (Settings, Resources, File sharing) and list it in `GRAF_DOCKER_SHARED` (colon-separated), or use `container.mount: none` and pass everything as inputs. A plain Docker Engine has no such limit.

## Things to check

- `network` is `false` and both writes are `false`; the `hostname` is not your machine's.
- `docker ps -a --filter name=graf-` shows nothing afterwards: containers are removed (`--rm`, and `docker rm -f` on a timeout).
- `tests/test_container.py` runs the same checks without Docker (a stub `docker`) and, when a daemon and the image are present, for real.
