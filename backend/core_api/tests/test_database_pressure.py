from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from src.services.games import deploy, open_draft, review
from src.simulation.catalog import OPERATIONS
from src.simulation.engine import evaluate
from src.simulation.progression import advance
from src.simulation.topology import daily_cost

from tests.test_simulation import add_node, component, fixture, link, monitor


class DatabasePressureTests(TestCase):
    def setUp(self):
        self.game = fixture()
        component(self.game, "api").config.update(
            cpu=32, memory=128, connections=10000, concurrency=400
        )
        component(self.game, "edge").config.update(connections=10000)
        self.db = component(self.game, "db")
        self.db.config.update(memory=32, connections=10000)
        monitor(self.game, "db")

    def snapshot(self, **operations):
        with patch("src.simulation.engine.workload") as workload:
            workload.return_value.operations = operations
            workload.return_value.overview = None
            workload.return_value.active_users = 0
            workload.return_value.regional_ad_rates = {}
            return evaluate(self.game).snapshot

    def test_write_throughput_under_sustained_load_and_hardware_upgrades(self):
        self.db.config["cpu"] = 2
        ssd = self.snapshot(send=160).components["db"]
        self.assertEqual(ssd.database.write_demand, 160)
        self.assertEqual(ssd.database.write_capacity, 62)
        self.assertEqual(ssd.database.diagnostic.level, "write_exceeded")
        self.assertIn("cpu", ssd.database.diagnostic.upgrades)

        self.db.config["disk"] = "NVMe"
        cpu_bound = self.snapshot(send=160).components["db"]
        self.assertEqual(cpu_bound.throughput, ssd.throughput)
        self.assertAlmostEqual(
            cpu_bound.utilization["Disk I/O"], ssd.utilization["Disk I/O"] / 1.45
        )
        self.assertFalse(cpu_bound.database.diagnostic.read_options)
        self.assertNotIn("nvme", cpu_bound.database.diagnostic.upgrades)

        self.db.config.update(cpu=16, disk="SSD")
        disk_bound = self.snapshot(send=160).components["db"]
        self.assertAlmostEqual(disk_bound.throughput, 115)
        self.assertIn("nvme", disk_bound.database.diagnostic.upgrades)
        self.db.config["disk"] = "NVMe"
        upgraded = self.snapshot(send=160).components["db"]
        self.assertAlmostEqual(upgraded.database.write_capacity, 166.75)
        self.assertAlmostEqual(upgraded.throughput, 160)

        self.db.config["connections"] = 25
        pooled = self.snapshot(send=160).components["db"]
        self.assertAlmostEqual(pooled.throughput, 25)
        self.assertEqual(pooled.database.write_capacity, 25)
        self.assertIn("connections", pooled.database.diagnostic.upgrades)
        self.assertFalse(pooled.database.diagnostic.read_options)

        self.game.audience = 1_000_000
        before = self.game.storage["db"]
        advance(self.game, 12)
        sustained = evaluate(self.game).snapshot.components["db"]
        self.assertGreater(
            sustained.database.write_demand, sustained.database.write_capacity
        )
        self.assertGreater(self.game.storage["db"], before)

    def test_reported_mixed_load_and_finite_upgrade_path(self):
        self.db.config.update(
            cpu=8, memory=12, connections=600, disk="NVMe", search_index="Enabled"
        )
        # Authentication stays on the primary because it also writes.
        ops = {"send": 251.3, "history": 311.1 / 1.8, "auth": 10}
        base = self.snapshot(**ops)
        database = base.components["db"]
        self.assertAlmostEqual(database.database.read_demand, 321.1)
        self.assertAlmostEqual(database.database.write_demand, 253.8)
        self.assertAlmostEqual(database.database.write_capacity, 65.7, places=1)
        for resource, value in {
            "CPU": 1.76,
            "Disk I/O": 2.35,
            "RAM": 0.86,
            "Connections": 0.96,
        }.items():
            self.assertAlmostEqual(database.utilization[resource], value, places=2)
        self.assertEqual(database.database.diagnostic.limiting, ["Disk I/O", "CPU"])
        self.assertEqual(database.database.diagnostic.upgrades, ["cpu", "nvme_array"])
        self.assertTrue(database.database.diagnostic.read_options)
        start_cost = daily_cost(self.db)

        self.db.config.update(connections=10000)
        self.assertEqual(self.snapshot(**ops).metrics, base.metrics)
        self.assertEqual(daily_cost(self.db), start_cost)
        self.db.config.update(memory=32)
        self.assertEqual(self.snapshot(**ops).metrics, base.metrics)
        self.assertGreater(daily_cost(self.db), start_cost)

        self.db.config.update(memory=12, connections=600, disk="SSD")
        ssd = self.snapshot(**ops)
        self.assertLess(ssd.metrics.throughput, base.metrics.throughput)
        self.assertGreater(ssd.metrics.errors, base.metrics.errors)
        self.assertGreater(ssd.components["db"].utilization["Disk I/O"], 3)
        self.db.config.update(cpu=32, disk="NVMe")
        cpu_only = self.snapshot(**ops)
        self.assertEqual(cpu_only.metrics, base.metrics)
        self.assertLess(cpu_only.components["db"].utilization["CPU"], 1)

        self.db.config.update(cpu=8, disk="NVMe array")
        disk_only = self.snapshot(**ops)
        self.assertLess(disk_only.metrics.errors, base.metrics.errors)
        self.assertLess(disk_only.metrics.latency, base.metrics.latency)
        self.assertGreater(disk_only.metrics.errors, 0)
        self.assertEqual(
            disk_only.components["db"].database.diagnostic.limiting, ["CPU"]
        )

        self.db.config.update(cpu=16)
        self.assertGreater(self.snapshot(**ops).metrics.errors, 0)
        self.db.config.update(cpu=32, memory=16, connections=800)
        stable = self.snapshot(**ops)
        self.assertAlmostEqual(stable.metrics.throughput, sum(ops.values()))
        self.assertAlmostEqual(stable.metrics.errors, 0)
        self.assertLess(stable.metrics.latency, base.metrics.latency)
        self.assertGreater(stable.components["db"].database.write_capacity, 300)
        self.assertGreater(daily_cost(self.db), start_cost)
        self.assertLess(daily_cost(self.db), 85)
        self.assertGreater(self.snapshot(send=530, history=100).metrics.errors, 0)

    def test_mixed_load_read_offload_and_reducing_write_demand(self):
        self.db.config.update(cpu=16, memory=16, connections=800, disk="NVMe")
        heavy = {"send": 253.8, "history": 321.1 / 1.8}
        base = self.snapshot(**heavy)
        lower_reads = self.snapshot(**{**heavy, "history": 0})
        lower_writes = self.snapshot(**{**heavy, "send": 70})
        self.assertGreater(lower_reads.metrics.errors, 0)
        self.assertGreater(
            lower_reads.components["db"].database.write_capacity,
            base.components["db"].database.write_capacity,
        )
        self.assertAlmostEqual(lower_writes.metrics.errors, 0)

        add_node(self.game, "cache", "cache", ttl=10, memory=1)
        link(self.game, "api", "cache")
        link(self.game, "cache", "db")
        link(self.game, "cache", "telemetry")
        low_hit = self.snapshot(**heavy)
        cache = component(self.game, "cache")
        low_cost = daily_cost(cache)
        cache.config.update(ttl=1200, memory=8, policy="LFU")
        high_hit = self.snapshot(**heavy)
        self.assertGreater(daily_cost(cache), low_cost)
        self.assertGreater(
            high_hit.components["cache"].cache_hit,
            low_hit.components["cache"].cache_hit,
        )
        self.assertLess(
            high_hit.components["db"].database.read_demand,
            low_hit.components["db"].database.read_demand,
        )
        self.assertEqual(high_hit.components["db"].database.write_demand, heavy["send"])
        self.assertLess(high_hit.metrics.errors, low_hit.metrics.errors)
        self.assertGreater(high_hit.metrics.errors, 0)

        for replica_id in ("read1", "read2"):
            add_node(self.game, replica_id, "replica", cpu=16, disk="NVMe", memory=16)
            link(self.game, "cache", replica_id)
            link(self.game, replica_id, "db")
            link(self.game, replica_id, "telemetry")
            linked = self.snapshot(**heavy)
            self.assertGreater(
                linked.components[replica_id].database.replication_demand, 0
            )
            self.assertEqual(
                linked.components["db"].database.write_demand, heavy["send"]
            )
        self.assertAlmostEqual(
            linked.components["db"].database.read_demand,
            high_hit.components["db"].database.read_demand / 3,
        )
        self.assertGreater(linked.metrics.errors, 0)

    def test_grown_messenger_with_groups_and_search_has_stable_upgrade_path(self):
        self.game.audience = 40_000
        self.game.released.extend(("groups", "search"))
        self.game.infrastructure_releases.extend(("groups", "search"))
        self.db.config.update(
            cpu=16, memory=16, connections=800, disk="NVMe", search_index="Enabled"
        )
        before = evaluate(self.game).snapshot
        self.assertGreater(before.components["db"].database.write_demand, 253.8)
        self.assertGreater(before.metrics.errors, 0)

        self.db.config.update(cpu=32, disk="NVMe array")
        add_node(self.game, "cache", "cache", memory=12, ttl=1200, policy="LFU")
        link(self.game, "api", "cache")
        link(self.game, "cache", "db")
        link(self.game, "cache", "telemetry")
        after = evaluate(self.game).snapshot
        self.assertEqual(after.metrics.errors, 0)
        self.assertLess(after.metrics.latency, before.metrics.latency)
        self.assertEqual(
            after.components["db"].database.write_demand,
            before.components["db"].database.write_demand,
        )
        self.assertLess(after.components["db"].utilization["Disk I/O"], 0.8)

    def test_draft_database_forecast_requires_coverage_in_both_topologies(self):
        open_draft(self.game, 0)
        next_db = next(node for node in self.game.draft.nodes if node.id == "db")
        next_db.config.update(cpu=16, disk="NVMe array")
        result = review(self.game, self.game.revision)
        database = result.forecast.databases["db"]
        current = evaluate(self.game).snapshot.components["db"]
        self.assertEqual(database.current_utilization, current.utilization)
        self.assertEqual(
            database.current_write_capacity, current.database.write_capacity
        )
        self.assertLess(
            database.projected_utilization["CPU"].high, current.utilization["CPU"]
        )
        self.assertGreater(
            database.projected_write_capacity.low, database.current_write_capacity
        )
        self.assertGreater(result.daily_after, result.daily_before)

        edges = self.game.draft.edges
        self.game.draft.edges = [edge for edge in edges if edge.target != "telemetry"]
        self.assertEqual(review(self.game, self.game.revision).forecast.databases, {})
        self.game.draft.edges = edges
        self.game.production.edges = [
            edge for edge in self.game.production.edges if edge.target != "telemetry"
        ]
        self.assertEqual(review(self.game, self.game.revision).forecast.databases, {})

    def add_replica(self, primary="db", **config):
        add_node(self.game, "read", "replica", **config)
        link(self.game, "api", "read")
        link(self.game, "read", primary)
        link(self.game, "read", "telemetry")

    def test_replica_replays_commits_and_serves_eligible_reads(self):
        base = self.snapshot(send=40, history=125)
        self.add_replica(cpu=8, memory=32)
        after = self.snapshot(send=40, history=125)
        db = after.components["db"]
        replica = after.components["read"]
        self.assertEqual(db.database.write_capacity, 62)
        self.assertEqual(db.database.write_demand, 40)
        self.assertEqual(replica.database.write_demand, 0)
        self.assertEqual(replica.database.replication_demand, 40)
        self.assertEqual(replica.database.replication_throughput, 40)
        self.assertEqual(replica.database.replication_backlog, 0)
        reads = 125 * OPERATIONS["history"]["read"] / 2
        self.assertAlmostEqual(db.database.read_demand, reads)
        self.assertAlmostEqual(replica.database.read_demand, reads)
        self.assertGreater(after.metrics.throughput, base.metrics.throughput)

    def test_read_replication_cannot_raise_pure_write_capacity(self):
        self.db.config["cpu"] = 16
        base = self.snapshot(send=160).components["db"]
        self.add_replica(cpu=16)
        metrics = self.snapshot(send=160).components
        db, replica = metrics["db"], metrics["read"]
        self.assertEqual(db.database.write_demand, base.database.write_demand)
        self.assertEqual(db.utilization["Writes"], base.utilization["Writes"])
        self.assertAlmostEqual(
            db.utilization["Disk I/O"], base.utilization["Disk I/O"] * 1.08
        )
        self.assertLessEqual(db.database.write_capacity, base.database.write_capacity)
        self.assertEqual(replica.database.replication_demand, db.throughput)
        self.assertEqual(replica.throughput, 0)
        self.assertFalse(db.database.diagnostic.read_options)

    def test_replication_backlog_advances_and_resets_when_reparented(self):
        self.add_replica(connections=25)
        advance(self.game, 4)
        self.assertGreater(self.game.replication["read"], 0)
        old = evaluate(self.game).snapshot.components["read"]
        component(self.game, "read").config.update(
            cpu=16, memory=128, disk="NVMe", connections=10000
        )
        advance(self.game, 1)
        new = evaluate(self.game).snapshot.components["read"]
        self.assertLess(new.replication_lag, old.replication_lag)
        self.game.replication["read"] = 500
        open_draft(self.game, 0)
        game_copy = self.game.model_copy(update={"production": self.game.draft})
        add_node(game_copy, "other", "database")
        self.game.draft.edges = [
            edge
            for edge in self.game.draft.edges
            if edge.source != "read" or edge.target != "db"
        ]
        link(game_copy, "read", "other")
        deploy(self.game, 1, uuid4())
        self.assertNotIn("read", self.game.replication)

    def test_independent_primary_does_not_receive_replication_or_reads(self):
        add_node(self.game, "other", "database")
        link(self.game, "other", "telemetry")
        self.add_replica("other")
        snapshot = self.snapshot(send=30, history=30)
        self.assertEqual(snapshot.components["db"].database.write_demand, 30)
        self.assertEqual(snapshot.components["other"].database.write_demand, 0)
        self.assertEqual(snapshot.components["read"].database.replication_demand, 0)
        self.assertEqual(snapshot.components["read"].database.read_demand, 0)

    def test_cache_reduces_eligible_demand_and_keeps_writes(self):
        base = self.snapshot(send=20, history=50, auth=10).components["db"]
        add_node(self.game, "cache", "cache", ttl=500)
        link(self.game, "api", "cache")
        link(self.game, "cache", "db")
        link(self.game, "cache", "telemetry")
        after = self.snapshot(send=20, history=50, auth=10).components
        hit = after["cache"].cache_hit
        self.assertGreater(hit, 0.5)
        db = after["db"]
        self.assertAlmostEqual(db.database.read_demand, 10 + 90 * (1 - hit))
        self.assertEqual(db.database.write_demand, base.database.write_demand)
        self.assertEqual(db.utilization["Writes"], base.utilization["Writes"])

    def test_hdd_reduces_cost_and_throughput_and_suggests_ssd(self):
        self.db.config["cpu"] = 16
        ssd_cost = daily_cost(self.db)
        ssd = self.snapshot(send=42, history=25).components["db"]
        self.db.config["disk"] = "HDD"
        hdd = self.snapshot(send=42, history=25).components["db"]
        self.assertLess(daily_cost(self.db), ssd_cost)
        self.assertEqual(hdd.database.disk_capacity_iops, 126)
        self.assertLess(hdd.database.write_capacity, ssd.database.write_capacity)
        self.assertIn("ssd", hdd.database.diagnostic.upgrades)

    def test_diagnostics_depend_on_monitoring_coverage(self):
        self.db.config.update(cpu=16, memory=128)
        snapshot = self.snapshot(send=55, history=130)
        telemetry = snapshot.components["db"]
        self.assertGreater(telemetry.utilization["Disk I/O"], 1)
        self.assertLess(telemetry.utilization["Writes"], 1)
        self.assertTrue(telemetry.database.diagnostic.read_options)
        self.assertEqual(telemetry.database.diagnostic.upgrades, ["nvme"])
        self.game.production.edges = [
            edge for edge in self.game.production.edges if edge.source != "db"
        ]
        hidden = self.snapshot(send=55, history=130)
        self.assertEqual(hidden.metrics, snapshot.metrics)
        self.assertNotIn("db", hidden.components)
