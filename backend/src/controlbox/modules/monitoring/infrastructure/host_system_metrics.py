"""Read host-level metrics from /proc (supports HOST_PROC mount in Docker)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import psutil

_SKIP_NET_PREFIXES = ("lo", "docker", "br-", "veth", "virbr", "weave", "cni", "flannel")


def resolve_proc_path(explicit: str = "") -> Path:
    if explicit:
        candidate = Path(explicit)
        if (candidate / "stat").is_file():
            return candidate
    host_proc = Path("/host/proc")
    if (host_proc / "stat").is_file():
        return host_proc
    return Path("/proc")


def resolve_disk_path(explicit_root: str, data_path: str) -> str:
    if explicit_root:
        root = Path(explicit_root)
        if root.is_dir():
            return str(root)
    for candidate in (data_path, "/var/lib/controlbox"):
        path = Path(candidate)
        if path.is_dir():
            return str(path)
    return "/"


def _read_cpu_jiffies(proc_path: Path) -> tuple[int, int]:
    with open(proc_path / "stat", encoding="utf-8") as handle:
        line = handle.readline()
    parts = line.split()
    if len(parts) < 5 or parts[0] != "cpu":
        return 0, 0
    values = [int(v) for v in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def read_cpu_percent(proc_path: Path, last: tuple[int, int, float] | None) -> tuple[float, tuple[int, int, float] | None]:
    total, idle = _read_cpu_jiffies(proc_path)
    now = time.time()
    if last is None or total < last[0]:
        return 0.0, (total, idle, now)
    total_delta = total - last[0]
    idle_delta = idle - last[1]
    if total_delta <= 0:
        return 0.0, (total, idle, now)
    usage = (1.0 - idle_delta / total_delta) * 100.0
    return max(0.0, min(100.0, usage)), (total, idle, now)


def read_memory_percent(proc_path: Path) -> tuple[float, float, float]:
    mem_total = 0
    mem_available = 0
    with open(proc_path / "meminfo", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("MemTotal:"):
                mem_total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                mem_available = int(line.split()[1])
    if mem_total <= 0:
        mem = psutil.virtual_memory()
        return mem.percent, mem.used / (1024 * 1024), mem.total / (1024 * 1024)
    used = mem_total - mem_available
    percent = (used / mem_total) * 100.0
    return percent, used / 1024.0, mem_total / 1024.0


def read_uptime_seconds(proc_path: Path) -> int:
    with open(proc_path / "uptime", encoding="utf-8") as handle:
        return int(float(handle.read().split()[0]))


def read_network_bytes(proc_path: Path) -> tuple[int, int]:
    recv = 0
    sent = 0
    with open(proc_path / "net" / "dev", encoding="utf-8") as handle:
        for line in handle.readlines()[2:]:
            if ":" not in line:
                continue
            name, stats = line.split(":", 1)
            iface = name.strip()
            if iface == "lo" or any(iface.startswith(prefix) for prefix in _SKIP_NET_PREFIXES):
                continue
            parts = stats.split()
            if len(parts) < 9:
                continue
            recv += int(parts[0])
            sent += int(parts[8])
    return recv, sent


def network_rates_mbps(
    proc_path: Path,
    last: tuple[int, int, float] | None,
) -> tuple[float, float, tuple[int, int, float] | None]:
    recv, sent = read_network_bytes(proc_path)
    now = time.time()
    if last is None:
        return 0.0, 0.0, (recv, sent, now)
    dt = max(now - last[2], 0.001)
    in_mbps = max(0.0, ((recv - last[0]) * 8) / (dt * 1_000_000))
    out_mbps = max(0.0, ((sent - last[1]) * 8) / (dt * 1_000_000))
    if recv < last[0] or sent < last[1]:
        in_mbps = 0.0
        out_mbps = 0.0
    return in_mbps, out_mbps, (recv, sent, now)


def read_disk_usage(path: str) -> tuple[float, float, float]:
    usage = psutil.disk_usage(path)
    return usage.percent, usage.used / (1024**3), usage.total / (1024**3)
