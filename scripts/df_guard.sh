# df_guard DIR MIN_GIB COMMAND [ARGS...]
# Run COMMAND; every 2 s read free space on DIR's file system with `df`; if it falls below MIN_GIB, stop the command
# and everything it started (its process group). Returns the command's exit code, or 75 when it was stopped.
df_guard() {
  local dir=$1 min=$(( $2 * 1024 * 1024 * 1024 )) avail pid
  shift 2
  setsid "$@" &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    avail=$(df --output=avail -B1 "$dir" | tail -n 1)
    if (( avail < min )); then
      echo "df_guard: only $(( avail / 1024 / 1024 )) MiB free on $dir; stopping $*" >&2
      kill -TERM -- "-$pid" 2>/dev/null; sleep 2; kill -KILL -- "-$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      return 75
    fi
    sleep 2
  done
  wait "$pid"
}
