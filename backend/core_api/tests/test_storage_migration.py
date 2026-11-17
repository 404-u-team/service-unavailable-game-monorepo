from unittest import TestCase
from uuid import uuid4

from src.services.games import (
    deploy,
    edit_draft,
    migration_pace,
    migration_upgrade,
    open_draft,
    review,
)
from src.services.save_files import export_file, parse_save_file
from src.simulation.engine import evaluate
from src.simulation.engineering import shard_assignments
from src.simulation.models import Incident
from src.simulation.progression import advance
from src.simulation.topology import RuleError, config

from tests.test_engineering import routed_shards
from tests.test_simulation import add_node, component, fixture, link, monitor


class StorageMigrationTests(TestCase):
    def media_move(self):
        game = fixture()
        game.balance = 50_000
        game.released.append("images")
        game.infrastructure_releases.append("images")
        game.storage["db"] = 22
        game.media_by_node = {"db": 15}
        game.free_media_storage_gb = 15
        monitor(game, "api", "db")
        draft = game.model_copy(deep=True)
        add_node(draft, "objects", "object_storage", storage=64)
        link(draft, "api", "objects")
        link(draft, "objects", "telemetry")
        open_draft(game, game.revision)
        with self.assertRaisesRegex(RuleError, "Object Storage research"):
            edit_draft(game, game.revision, draft.production)
        game.engineering["object_storage"] = 0
        edit_draft(game, game.revision, draft.production)
        plan = review(game, game.revision)
        self.assertEqual(plan.errors, [])
        self.assertEqual(plan.migration_media_sources, {"db": 15})
        self.assertEqual(plan.migration_database_sources, {})
        return game, plan

    def test_new_uploads_switch_immediately_and_old_downloads_follow_copied_bytes(self):
        game, plan = self.media_move()
        baseline = evaluate(game)
        deploy(game, game.revision, uuid4())
        staged = evaluate(game)
        self.assertEqual(staged.snapshot.demand, baseline.snapshot.demand)
        self.assertEqual(staged.media_by_node["db"], 15)
        self.assertGreater(staged.media_by_node["objects"], 0)
        self.assertLess(staged.storage["db"] - 22, baseline.storage["db"] - 22)
        self.assertNotIn("objects", [node.id for node in game.production.nodes])
        advance(game, 1)
        snapshot = evaluate(game).snapshot
        download = {
            edge.target: edge.operations["download"]
            for edge in snapshot.traffic
            if edge.source == "api" and "download" in edge.operations
        }
        self.assertGreater(download["db"], 0)
        self.assertGreater(download["objects"], 0)
        _, portable = export_file(game)
        restored = parse_save_file(portable.model_dump_json().encode()).game
        advance(game, plan.migration_ticks)
        advance(restored, plan.migration_ticks)
        self.assertEqual(game, restored)
        self.assertIsNone(game.migration)
        self.assertNotIn("db", game.media_by_node)
        self.assertGreater(game.media_by_node["objects"], 15)
        self.assertAlmostEqual(game.media_by_node["objects"], game.storage["objects"])
        self.assertGreater(game.storage["db"], 7)

    def test_object_outage_stalls_copy_and_preserves_source(self):
        game, _ = self.media_move()
        deploy(game, game.revision, uuid4())
        game.incidents.append(
            Incident(
                id="object-failure",
                kind="failure",
                title="Storage outage",
                symptom="Temporary outage",
                severity="warning",
                target="objects",
                start=0,
                end=3,
            )
        )
        advance(game, 2)
        self.assertTrue(game.migration.blocked)
        self.assertEqual(game.media_by_node["db"], 15)
        self.assertNotIn("objects", game.media_by_node)
        advance(game, 1)
        self.assertLess(game.media_by_node["db"], 15)
        self.assertFalse(game.migration.blocked)

    def test_upgrade_removed_primary_and_keep_next_draft_after_cutover(self):
        game = fixture()
        game.balance = 100_000
        component(game, "db").config["storage"] = 10000
        game.storage["db"] = 1800
        open_draft(game, game.revision)
        candidate = game.draft.model_copy(deep=True)
        candidate.nodes = [
            n
            if n.id != "db"
            else n.model_copy(update={"id": "new-db", "config": {"storage": 4000}})
            for n in candidate.nodes
        ]
        candidate.edges[-1].target = "new-db"
        edit_draft(game, game.revision, candidate)
        deploy(game, game.revision, uuid4())
        self.assertGreater(game.migration.ready_at, 400)
        migration_pace(game, game.revision, "paused")
        remaining = game.migration.remaining_work
        advance(game, 10)
        self.assertEqual(game.migration.remaining_work, remaining)
        original_balance = game.balance
        cost = migration_upgrade(
            game, game.revision, "production", "db", "cpu", 8, quote=True
        )
        self.assertEqual(game.balance, original_balance)
        migration_upgrade(game, game.revision, "production", "db", "cpu", 8)
        self.assertAlmostEqual(game.balance, original_balance - cost)
        self.assertEqual(config(component(game, "db"))["cpu"], 8)
        self.assertFalse(any(n.id == "db" for n in game.migration.topology.nodes))
        migration_upgrade(game, game.revision, "destination", "new-db", "storage", 5000)
        open_draft(game, game.revision)
        next_draft = game.draft.model_copy(deep=True)
        next(n for n in next_draft.nodes if n.id == "api").name = "Next API name"
        edit_draft(game, game.revision, next_draft)
        with self.assertRaises(RuleError):
            deploy(game, game.revision, uuid4())
        migration_pace(game, game.revision, "fast")
        advance(game, game.migration.ready_at - game.tick)
        self.assertIsNone(game.migration)
        self.assertEqual(game.draft, next_draft)
        self.assertNotEqual(component(game, "api").name, "Next API name")
        self.assertEqual(config(component(game, "new-db"))["storage"], 5000)
        self.assertGreaterEqual(game.storage["new-db"], 1800)

    def test_key_move_changes_live_write_demand_only_after_migration(self):
        game = routed_shards()
        game.balance = 100_000
        game.storage.update({"db": 12, "shard-1": 12})
        baseline = evaluate(game).snapshot
        assignments = shard_assignments(game.production)["router"]
        old = assignments[0]
        new = "db" if old == "shard-1" else "shard-1"
        open_draft(game, game.revision)
        candidate = game.draft.model_copy(deep=True)
        candidate.shard_owners = {"router": {0: new}}
        edit_draft(game, game.revision, candidate)
        plan = review(game, game.revision)
        self.assertEqual(plan.errors, [])
        self.assertGreater(plan.migration_database_sources[old], 0)
        deploy(game, game.revision, uuid4())
        self.assertEqual(shard_assignments(game.production)["router"], assignments)
        advance(game, plan.migration_ticks)
        self.assertEqual(shard_assignments(game.production)["router"][0], new)
        result = evaluate(game).snapshot
        self.assertLess(
            result.components[old].partition_share,
            baseline.components[old].partition_share,
        )
        self.assertGreater(
            result.components[new].partition_share,
            baseline.components[new].partition_share,
        )
