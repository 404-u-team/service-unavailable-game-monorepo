from dataclasses import dataclass
from typing import Literal

from src.simulation.catalog import COMPONENTS, DATABASE_DISKS, MINUTES_PER_TICK
from src.simulation.models import DatabaseDiagnostic, DatabaseTelemetry

SECONDS_PER_STEP = MINUTES_PER_TICK * 60
WARNING = 0.78


def compute_limits(cfg: dict) -> tuple[float, float]:
    cpu = (cfg["cpu"] / 2) ** 0.74
    return 155 * cpu * (cfg["memory"] / 8) ** 0.22, 62 * cpu


def disk_limits(cfg: dict) -> tuple[float, float]:
    multiplier = DATABASE_DISKS[cfg["disk"]][0]
    return 420 * multiplier, 115 * multiplier


def standalone_limits(cfg: dict) -> tuple[float, float]:
    cpu_read, cpu_write = compute_limits(cfg)
    disk_read, disk_write = disk_limits(cfg)
    index_cost = 1.2 if cfg.get("search_index") == "Enabled" else 1
    return (
        min(cpu_read, disk_read, cfg.get("reads", float("inf"))),
        min(min(cpu_write, disk_write) / index_cost, cfg.get("writes", float("inf"))),
    )


@dataclass
class DatabaseLoad:
    cfg: dict
    reads: float
    writes: float
    factor: float
    followers: int = 0
    primary: bool = True
    stored: float = 0
    storage_rate: float = 0

    @property
    def index_cost(self) -> float:
        return 1.2 if self.cfg.get("search_index") == "Enabled" else 1

    @property
    def disk_write_cost(self) -> float:
        return self.index_cost + 0.08 * self.followers

    def utilization(self) -> dict[str, float]:
        cfg = self.cfg
        cpu_read, cpu_write = compute_limits(cfg)
        disk_read, disk_write = disk_limits(cfg)
        read_limit, write_limit = standalone_limits(cfg)
        loads = {
            "Reads": self.reads / read_limit,
            "CPU": max(
                self.reads / cpu_read, self.writes * self.index_cost / cpu_write
            ),
            "RAM": (0.8 + self.reads * 0.014 + self.writes * 0.02) / cfg["memory"],
            "Connections": (self.reads + self.writes) / cfg["connections"],
            "Disk I/O": self.reads / disk_read
            + self.writes * self.disk_write_cost / disk_write,
        }
        loads["Writes" if self.primary else "Replication"] = self.writes / write_limit
        if "reads" in cfg:
            loads["Legacy read throttle"] = self.reads / cfg["reads"]
        if "writes" in cfg:
            loads["Legacy write throttle"] = self.writes / cfg["writes"]
        usage = {key: value / max(self.factor, 0.001) for key, value in loads.items()}
        if self.primary:
            usage["Storage"] = self.stored / cfg["storage"]
        return usage

    def sustainable_writes(self) -> float:
        """Write units per second with current reads held constant and today's write mix."""
        if not self.factor or (self.primary and self.stored >= self.cfg["storage"]):
            return 0
        cfg = self.cfg
        cpu_read, cpu_write = compute_limits(cfg)
        disk_read, disk_write = disk_limits(cfg)
        if self.reads > min(cpu_read, cfg.get("reads", float("inf"))) * self.factor:
            return 0
        limits = [
            cpu_write * self.factor / self.index_cost,
            (self.factor - self.reads / disk_read) * disk_write / self.disk_write_cost,
            (cfg["memory"] * self.factor - 0.8 - self.reads * 0.014) / 0.02,
            cfg["connections"] * self.factor - self.reads,
            cfg.get("writes", float("inf")) * self.factor,
        ]
        if self.primary and self.storage_rate and self.writes:
            limits.append(
                (cfg["storage"] - self.stored)
                * self.writes
                / (self.storage_rate * SECONDS_PER_STEP)
            )
        return max(0, min(limits))

    def telemetry(
        self, usage: dict[str, float], replayed: float = 0
    ) -> DatabaseTelemetry:
        sustainable = self.sustainable_writes() if self.primary else None
        diagnostic = None
        resources = [
            key
            for key in (
                "CPU",
                "RAM",
                "Connections",
                "Disk I/O",
                "Legacy read throttle",
                "Legacy write throttle",
                "Storage",
            )
            if usage.get(key, 0) >= WARNING
        ]
        # Storage can cap the current step even before its volume meter reaches 78%.
        storage_limited = self.primary and self.storage_rate * SECONDS_PER_STEP > max(
            0, self.cfg["storage"] - self.stored
        )
        if storage_limited and "Storage" not in resources:
            resources.append("Storage")
        if self.factor and resources:
            resources.sort(key=lambda key: usage[key], reverse=True)
            overloaded = [key for key in resources if usage[key] >= 1]
            if storage_limited and "Storage" not in overloaded:
                overloaded.append("Storage")
            targets = overloaded or resources
            level: Literal["write_exceeded", "write_pressure", "resource_pressure"]
            if sustainable is not None and self.writes > sustainable + 1e-9:
                level = "write_exceeded"
            elif self.primary and usage["Writes"] >= WARNING:
                level = "write_pressure"
            else:
                level = "resource_pressure"
            cfg = self.cfg
            fields = COMPONENTS["database" if self.primary else "replica"]["fields"]
            upgrades = []
            for resource, field, action in (
                ("CPU", "cpu", "cpu"),
                ("RAM", "memory", "memory"),
                ("Connections", "connections", "connections"),
                ("Storage", "storage", "storage"),
            ):
                if resource in targets and cfg[field] < fields[field]["max"]:
                    upgrades.append(action)
            if "Disk I/O" in targets:
                next_disk = {"SSD": "nvme", "NVMe": "nvme_array"}.get(cfg["disk"])
                if next_disk:
                    upgrades.append(next_disk)
            if "Legacy read throttle" in targets or "Legacy write throttle" in targets:
                upgrades.append("legacy")
            diagnostic = DatabaseDiagnostic(
                level=level, resources=resources, limiting=overloaded, upgrades=upgrades
            )
        disk_read, disk_write = disk_limits(self.cfg)
        return DatabaseTelemetry(
            read_demand=self.reads,
            disk_read_iops=self.reads,
            disk_write_iops=self.writes * self.disk_write_cost * disk_read / disk_write,
            disk_capacity_iops=disk_read * self.factor,
            write_demand=self.writes if self.primary else 0,
            write_capacity=sustainable,
            replication_demand=self.writes if not self.primary else 0,
            replication_throughput=replayed,
            diagnostic=diagnostic,
        )
