from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from src.services.games import deploy, open_draft
from src.simulation.catalog import OPERATIONS
from src.simulation.engine import evaluate
from src.simulation.progression import advance

from tests.test_simulation import add_node, component, fixture, link, monitor


class DatabasePressureTests(TestCase):
    def setUp(self):
        self.game = fixture()
        component(self.game, "api").config.update(cpu=32, memory=128, connections=10000)
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
        link(self.game, "cache", "telemetry")
        # With no explicit data link, cache misses fall back to the API's primary.
        after = self.snapshot(send=20, history=50, auth=10).components
        hit = after["cache"].cache_hit
        self.assertGreater(hit, 0.5)
        db = after["db"]
        self.assertAlmostEqual(db.database.read_demand, 10 + 90 * (1 - hit))
        self.assertEqual(db.database.write_demand, base.database.write_demand)
        self.assertEqual(db.utilization["Writes"], base.utilization["Writes"])

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
