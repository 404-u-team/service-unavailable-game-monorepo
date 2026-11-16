from datetime import UTC, datetime
from unittest import TestCase
from uuid import uuid4

from src.services.games import (
    deploy,
    develop_research,
    edit_draft,
    open_draft,
    prepare_sharding,
    research_state,
    review,
    view,
)
from src.services.live import live_frame
from src.services.save_files import export_file, parse_save_file
from src.simulation.engine import evaluate
from src.simulation.engineering import RESEARCH, architecture_errors, migrated_storage
from src.simulation.models import Edge, Incident
from src.simulation.progression import advance
from src.simulation.topology import RuleError, daily_cost, inspect_graph, topology_cost
from tests.test_simulation import add_node, component, fixture, link, monitor


def unlock(game):
    game.engineering = dict.fromkeys(RESEARCH, 0)


def specialized():
    game = fixture()
    unlock(game)
    component(game, "api").config["role"] = "Messages"
    add_node(game, "accounts", "api", role="Accounts")
    link(game, "edge", "accounts")
    link(game, "accounts", "db")
    link(game, "api", "accounts")
    monitor(game, "api", "accounts", "db")
    return game


def sharded(count):
    game = fixture()
    unlock(game)
    component(game, "api").config.update(
        instances=24,
        cpu=32,
        memory=128,
        network=1000,
        connections=25000,
        concurrency=800,
    )
    component(game, "edge").config.update(network=2000, connections=100000)
    primary = component(game, "db")
    primary.config.update(
        domain="Messages",
        partition="Partition",
        cpu=32,
        memory=128,
        storage=10000,
        disk="NVMe array",
        connections=10000,
    )
    add_node(
        game,
        "accounts-db",
        "database",
        domain="Accounts",
        cpu=32,
        memory=128,
        storage=10000,
        disk="NVMe array",
        connections=10000,
    )
    link(game, "api", "accounts-db")
    for i in range(1, count):
        add_node(game, f"shard-{i}", "database", **primary.config)
        link(game, "api", f"shard-{i}")
    monitor(game, "api", "db", "accounts-db", *(f"shard-{i}" for i in range(1, count)))
    component(game, "telemetry").config["slots"] = 32
    return game


class EngineeringTests(TestCase):
    def test_research_cost_time_prerequisites_and_no_automatic_architecture(self):
        game = fixture()
        original = game.production.model_copy(deep=True)
        with self.assertRaises(RuleError):
            develop_research(game, "domains")
        develop_research(game, "decomposition")
        self.assertEqual(game.development_spend, RESEARCH["decomposition"]["cost"])
        self.assertEqual(research_state(game, "decomposition").state, "developing")
        advance(game, RESEARCH["decomposition"]["duration"])
        self.assertEqual(research_state(game, "decomposition").state, "completed")
        self.assertEqual(research_state(game, "domains").state, "available")
        self.assertEqual(game.production, original)
        with self.assertRaises(RuleError):
            develop_research(game, "decomposition")

    def test_universal_small_scale_is_cheaper_and_specialization_routes_real_operations(
        self,
    ):
        mono = fixture()
        micro = specialized()
        monitor(mono, "api", "db")
        a, b = evaluate(mono).snapshot, evaluate(micro).snapshot
        self.assertEqual(a.demand, b.demand)
        self.assertGreaterEqual(a.metrics.throughput, b.metrics.throughput)
        self.assertLess(a.metrics.latency, b.metrics.latency)
        self.assertLess(topology_cost(mono.production), topology_cost(micro.production))
        self.assertNotIn("auth", b.components["api"].operations)
        self.assertEqual(set(b.components["accounts"].operations), {"auth", "identity"})
        self.assertGreater(b.components["accounts"].operations["identity"], 0)
        self.assertGreater(
            b.components["db"].database.read_demand,
            a.components["db"].database.read_demand,
        )
        self.assertAlmostEqual(
            a.components["db"].database.write_demand,
            b.components["db"].database.write_demand,
        )
        self.assertEqual(
            architecture_errors(micro, inspect_graph(micro.production)), []
        )

    def test_legacy_mixed_api_roles_do_not_duplicate_demand(
        self,
    ):
        game = specialized()
        component(game, "api").config["role"] = "Universal"
        game.production.edges = [
            e
            for e in game.production.edges
            if (e.source, e.target) != ("api", "accounts")
        ]
        snapshot = evaluate(game).snapshot
        self.assertAlmostEqual(
            snapshot.components["api"].operations["auth"], snapshot.demand["auth"] / 2
        )
        self.assertAlmostEqual(
            snapshot.components["accounts"].operations["auth"],
            snapshot.demand["auth"] / 2,
        )
        self.assertAlmostEqual(snapshot.metrics.throughput, snapshot.metrics.rps)
        add_node(game, "unused", "api", role="Media")
        self.assertFalse(
            any(t.target == "unused" for t in evaluate(game).snapshot.traffic)
        )

    def test_missing_role_route_and_identity_failure_propagate(self):
        game = specialized()
        healthy = evaluate(game).snapshot
        game.production.edges = [
            e
            for e in game.production.edges
            if (e.source, e.target) != ("api", "accounts")
        ]
        broken = evaluate(game).snapshot
        self.assertGreater(broken.metrics.errors, healthy.metrics.errors)
        self.assertTrue(architecture_errors(game, inspect_graph(game.production)))
        game.production.edges.append(Edge(source="api", target="accounts"))
        game.incidents.append(
            Incident(
                id="failure",
                kind="failure",
                title="Test",
                symptom="Test",
                severity="warning",
                start=0,
                end=3,
                target="accounts",
            )
        )
        self.assertLess(
            evaluate(game).snapshot.metrics.availability, healthy.metrics.availability
        )
        game.incidents.clear()
        game.production.edges = [
            e
            for e in game.production.edges
            if (e.source, e.target) != ("edge", "accounts")
        ]
        self.assertIn(
            "A required operation has no connected API service. Connect an API that handles this operation.",
            architecture_errors(game, inspect_graph(game.production)),
        )

    def test_domain_separation_moves_accounts_without_removing_message_writes(self):
        game = specialized()
        before = evaluate(game).snapshot
        component(game, "db").config["domain"] = "Messages"
        add_node(game, "accounts-db", "database", domain="Accounts")
        game.production.edges = [
            e
            for e in game.production.edges
            if (e.source, e.target) != ("accounts", "db")
        ]
        link(game, "accounts", "accounts-db")
        link(game, "accounts-db", "telemetry")
        after = evaluate(game).snapshot
        self.assertEqual(architecture_errors(game, inspect_graph(game.production)), [])
        self.assertAlmostEqual(
            before.components["db"].database.write_demand,
            after.components["db"].database.write_demand
            + after.components["accounts-db"].database.write_demand,
        )
        self.assertGreater(after.components["db"].database.write_demand, 0)
        self.assertAlmostEqual(
            after.components["db"].database.write_demand, after.demand["send"]
        )
        add_node(game, "accounts-b", "api", role="Accounts")
        add_node(game, "unrelated", "database", domain="Accounts")
        link(game, "edge", "accounts-b")
        link(game, "accounts-b", "unrelated")
        self.assertTrue(architecture_errors(game, inspect_graph(game.production)))

    def test_identity_only_accounts_cannot_use_a_conflicting_dataset(self):
        game = specialized()
        game.production.edges = [
            e
            for e in game.production.edges
            if (e.source, e.target) not in {("edge", "accounts"), ("accounts", "db")}
        ]
        add_node(game, "universal", "api")
        link(game, "edge", "universal")
        link(game, "universal", "db")
        add_node(game, "private-accounts", "database", domain="Accounts")
        link(game, "accounts", "private-accounts")
        self.assertIn(
            "APIs handling the same domain must use the same primary or the same complete partition set.",
            architecture_errors(game, inspect_graph(game.production)),
        )

    def test_shards_scale_finite_writes_have_hotspots_overhead_and_partial_failure(
        self,
    ):
        snapshots = [evaluate(sharded(n), load_scale=28).snapshot for n in (1, 2, 4)]
        self.assertLess(
            snapshots[0].metrics.availability, snapshots[1].metrics.availability
        )
        self.assertLess(
            snapshots[1].metrics.availability, snapshots[2].metrics.availability
        )
        self.assertGreater(
            snapshots[0].components["db"].database.write_demand,
            snapshots[0].components["db"].database.write_capacity,
        )
        self.assertGreater(
            snapshots[2].components["api"].utilization["CPU"],
            snapshots[0].components["api"].utilization["CPU"],
        )
        shares = [
            m.partition_share
            for m in snapshots[2].components.values()
            if m.partition_share is not None
        ]
        self.assertGreater(max(shares), min(shares))
        self.assertAlmostEqual(sum(shares), 1)
        game = sharded(4)
        healthy = evaluate(game, load_scale=1).snapshot
        game.incidents.append(
            Incident(
                id="failed-shard",
                kind="failure",
                title="Test",
                symptom="Test",
                severity="warning",
                start=0,
                end=10,
                target="db",
            )
        )
        broken = evaluate(game).snapshot
        self.assertGreater(broken.metrics.errors, 0)
        self.assertGreater(broken.metrics.availability, 0.5)
        self.assertLess(broken.metrics.availability, healthy.metrics.availability)
        self.assertEqual(broken.components["db"].throughput, 0)
        self.assertLess(
            evaluate(sharded(4), load_scale=300).snapshot.metrics.availability, 0.99
        )
        self.assertGreater(
            topology_cost(sharded(4).production), topology_cost(sharded(1).production)
        )

    def test_replica_reads_only_its_shard_and_replays_that_shards_writes(self):
        game = sharded(2)
        add_node(
            game,
            "replica",
            "replica",
            cpu=16,
            memory=128,
            disk="NVMe array",
            connections=10000,
        )
        link(game, "replica", "db")
        link(game, "api", "replica")
        link(game, "replica", "telemetry")
        snapshot = evaluate(game).snapshot
        replica = snapshot.components["replica"]
        self.assertGreater(replica.database.replication_demand, 0)
        self.assertGreater(replica.rps, 0)
        self.assertEqual(replica.database.write_demand, 0)
        self.assertEqual(snapshot.components["shard-1"].database.replication_demand, 0)

    def test_read_offload_and_four_partitions_stabilize_work_above_max_primary(self):
        snapshots = []
        for count in (1, 2, 4):
            game = sharded(count)
            add_node(game, "cache", "cache", memory=64, ttl=3600)
            link(game, "api", "cache")
            for node in game.production.nodes:
                if node.config.get("domain") == "Messages":
                    link(game, "cache", node.id)
            snapshots.append(evaluate(game, load_scale=28).snapshot)
        self.assertLess(snapshots[0].metrics.availability, 0.9)
        self.assertLess(snapshots[1].metrics.availability, 0.99)
        self.assertEqual(snapshots[2].metrics.availability, 1)
        self.assertEqual(snapshots[0].demand, snapshots[2].demand)
        self.assertAlmostEqual(
            snapshots[0].components["db"].database.write_demand,
            sum(
                snapshots[2].components[p].database.write_demand
                for p in ("db", "shard-1", "shard-2", "shard-3")
            ),
        )

    def test_cache_on_shared_primary_cannot_serve_message_domain(self):
        game = fixture()
        unlock(game)
        add_node(game, "messages-db", "database", domain="Messages")
        add_node(game, "cache", "cache")
        link(game, "api", "messages-db")
        link(game, "api", "cache")
        link(game, "cache", "db")
        monitor(game, "api", "cache", "messages-db")
        snapshot = evaluate(game).snapshot
        traffic = {(edge.source, edge.target): edge.operations for edge in snapshot.traffic}
        self.assertNotIn(("api", "cache"), traffic)
        self.assertEqual(snapshot.components["cache"].cache_hit, 0)
        for op in ("history", "conversations"):
            self.assertAlmostEqual(traffic["api", "messages-db"][op], snapshot.demand[op])

    def test_cache_covers_only_the_shard_owned_by_its_replica(self):
        game = sharded(2)
        add_node(game, "cache", "cache", scope="History only", ttl=3600)
        add_node(game, "reader", "replica")
        link(game, "api", "cache")
        link(game, "cache", "reader")
        link(game, "reader", "db")
        for node in ("cache", "reader"):
            link(game, node, "telemetry")
        snapshot = evaluate(game).snapshot
        traffic = {(edge.source, edge.target): edge.operations for edge in snapshot.traffic}
        cached = traffic["api", "cache"]["history"]
        other = traffic["api", "shard-1"]["history"]
        self.assertAlmostEqual(cached + other, snapshot.demand["history"])
        self.assertEqual(set(traffic["api", "cache"]), {"history"})
        hit = snapshot.components["cache"].cache_hit
        self.assertGreater(hit, 0)
        self.assertAlmostEqual(traffic["cache", "reader"]["history"], cached * (1 - hit))
        self.assertAlmostEqual(
            snapshot.components["api"].completed_operations["history"], snapshot.demand["history"]
        )

    def test_draft_can_stage_both_switches_and_deploy_only_consistent_modes(self):
        game = fixture()
        unlock(game)
        open_draft(game, game.revision)
        staged = specialized()
        add_node(staged, "unused-api", "api")
        add_node(staged, "messages-db", "database", domain="Messages")
        edit_draft(game, game.revision, staged.production)
        issues = review(game, game.revision).errors
        self.assertIn("Use either shared databases or domain databases throughout the topology.", issues)
        self.assertIn("Use either Universal APIs or specialized APIs throughout the topology.", issues)
        with self.assertRaises(RuleError):
            deploy(game, game.revision, uuid4())
        self.assertIsNone(game.migration)
        self.assertEqual(component(game, "db").config.get("domain", "Shared"), "Shared")
        _, legacy = export_file(staged)
        self.assertEqual(parse_save_file(legacy.model_dump_json().encode()).game.production, staged.production)
        edit_draft(game, game.revision, specialized().production)
        result = review(game, game.revision)
        self.assertEqual(result.errors, [])
        deploy(game, game.revision, uuid4())
        advance(game, result.migration_ticks)
        self.assertEqual(component(game, "api").config["role"], "Messages")

    def test_migration_keeps_explicit_domain_volumes(self):
        game = sharded(2)
        game.storage = {"db": 8, "shard-1": 4, "accounts-db": 3}
        result = migrated_storage(game, sharded(1).production)
        self.assertAlmostEqual(result["accounts-db"], 3)
        self.assertAlmostEqual(result["db"], 12)

    def test_prepare_sharding_splits_shared_data_and_routes_queries_after_copy(self):
        game = fixture()
        monitor(game, "api", "db")
        before = game.production.model_copy(deep=True)
        with self.assertRaisesRegex(RuleError, "Complete Database Sharding"):
            prepare_sharding(game, game.revision, "db")
        self.assertIsNone(game.draft)
        unlock(game)
        prepare_sharding(game, game.revision, "db")
        self.assertEqual(game.production, before)
        router = next(node for node in game.draft.nodes if node.kind == "shard_router")
        self.assertEqual(router.config["domain"], "Messages")
        graph = inspect_graph(game.draft)
        shards = graph.primaries(router.id)
        self.assertEqual(len(shards), 2)
        self.assertEqual(len(graph.primaries("api")), 3)
        self.assertNotIn("db", graph.targets["api"])

        game.draft.edges.append(Edge(source=router.id, target="telemetry"))
        for shard in shards:
            if shard != "db":
                game.draft.edges.append(Edge(source=shard, target="telemetry"))
        result = review(game, game.revision)
        self.assertEqual(result.errors, [])
        self.assertGreater(result.migration_cost, 0)
        deploy(game, game.revision, uuid4())
        self.assertEqual(game.production, before)
        _, pending = export_file(game)
        self.assertEqual(parse_save_file(pending.model_dump_json().encode()).game, game)
        advance(game, result.migration_ticks)
        self.assertIsNone(game.migration)
        self.assertGreaterEqual(sum(game.storage.values()), 2)
        snapshot = evaluate(game).snapshot
        traffic = {(edge.source, edge.target): edge.operations for edge in snapshot.traffic}
        self.assertEqual(set(traffic["api", router.id]), {"send", "history", "conversations"})
        self.assertAlmostEqual(
            sum(traffic[router.id, shard]["send"] for shard in shards),
            traffic["api", router.id]["send"],
        )
        self.assertTrue(all(game.storage[shard] > 0 for shard in shards))
        self.assertEqual(snapshot.components[router.id].data_domain, "Messages")

    def test_shard_router_blocks_deployment_with_wrong_partition_or_direct_link(self):
        game = fixture()
        unlock(game)
        prepare_sharding(game, game.revision, "db")
        game.draft.edges.append(Edge(source="api", target="db"))
        db = next(node for node in game.draft.nodes if node.id == "db")
        db.config["partition"] = "Independent"
        result = review(game, game.revision)
        self.assertIn("Connect each shard router to at least two primary partitions of its data domain.", result.errors)
        self.assertIn("Connect each API to one shard router per domain and remove its direct links to that domain's primaries.", result.errors)

    def test_sharding_upgrades_a_legacy_shared_database_with_one_remaining_domain(self):
        game = fixture()
        unlock(game)
        add_node(game, "messages-db", "database", domain="Messages")
        link(game, "api", "messages-db")
        prepare_sharding(game, game.revision, "messages-db")
        self.assertEqual(review(game, game.revision).errors, [])
        remaining = next(node for node in game.draft.nodes if node.id == "db")
        self.assertEqual(remaining.config["domain"], "Accounts")

    def test_query_plan_changes_only_eligible_work_and_increases_index_writes(self):
        game = fixture()
        unlock(game)
        monitor(game, "api", "db")
        before = evaluate(game).snapshot
        component(game, "db").config["query_plan"] = "History indexes"
        after = evaluate(game).snapshot
        self.assertEqual(before.demand, after.demand)
        self.assertLess(
            after.components["db"].database.read_demand,
            before.components["db"].database.read_demand,
        )
        self.assertAlmostEqual(
            after.components["db"].database.write_demand
            - before.components["db"].database.write_demand,
            before.demand["send"] * 0.1,
        )
        self.assertEqual(
            after.components["api"].utilization, before.components["api"].utilization
        )

    def test_migration_is_paid_delayed_locked_conserves_data_and_roundtrips(self):
        game = sharded(1)
        game.balance = 1_000_000
        game.storage = {"db": 8, "accounts-db": 1}
        candidate = sharded(2).production
        open_draft(game, game.revision)
        edit_draft(game, game.revision, candidate)
        result = review(game, game.revision)
        self.assertEqual(result.errors, [])
        self.assertGreaterEqual(result.migration_ticks, 3)
        original = game.production.model_copy(deep=True)
        deploy(game, game.revision, uuid4())
        self.assertEqual(game.production, original)
        self.assertEqual(game.deployment_spend, result.install)
        with self.assertRaises(RuleError):
            edit_draft(game, game.revision, candidate)
        game = type(game).model_validate(game.model_dump())
        _, portable = export_file(game)
        restored = parse_save_file(portable.model_dump_json().encode()).game
        self.assertEqual(restored.migration, game.migration)
        advance(game, result.migration_ticks)
        advance(restored, result.migration_ticks)
        self.assertEqual(game, restored)
        self.assertIsNone(game.migration)
        self.assertEqual(game.production, candidate)
        self.assertGreaterEqual(sum(game.storage.values()), 9)
        self.assertEqual(game.deployment_spend, result.install)
        self.assertAlmostEqual(
            sum(migrated_storage(game, sharded(1).production).values()),
            sum(game.storage.values()),
        )
        self.assertEqual(game.deployments[-1].cost, result.install)

    def test_autoscaling_needs_coverage_reacts_late_and_bills_active_instances(self):
        game = fixture()
        unlock(game)
        component(game, "api").config.update(
            autoscale="Enabled",
            min_instances=1,
            max_instances=2,
            target_utilization=40,
            cpu=1,
            memory=1,
        )
        advance(game, 5)
        self.assertEqual(game.autoscaling["api"].instances, 1)
        monitor(game, "api", "db")
        advance(game, 1)
        self.assertEqual(game.autoscaling["api"].instances, 1)
        advance(game, 1)
        self.assertEqual(game.autoscaling["api"].instances, 2)
        advance(game, 4)
        state = view(game, datetime.now(UTC))
        self.assertEqual(
            state.component_costs["api"], 2 * daily_cost(component(game, "api"))
        )
        self.assertEqual(state.snapshot.components["api"].active_instances, 2)
        self.assertGreater(game.infrastructure_spend, 0)
        self.assertLessEqual(game.autoscaling["api"].instances, 2)
        candidate = game.production.model_copy(deep=True)
        candidate.nodes[2].config["min_instances"] = 2
        comparison = review(game, game.revision, candidate)
        self.assertEqual(comparison.daily_before, comparison.daily_after)

    def test_shard_removal_and_rollback_both_pay_and_prepare_data(self):
        game = sharded(2)
        game.balance = 1_000_000
        game.storage = {"db": 8, "shard-1": 4, "accounts-db": 3}
        original = game.production.model_copy(deep=True)
        open_draft(game, game.revision)
        edit_draft(game, game.revision, sharded(1).production)
        deploy(game, game.revision, uuid4())
        self.assertIsNotNone(game.migration)
        advance(game, game.migration.ready_at - game.tick)
        self.assertGreaterEqual(sum(game.storage.values()), 15)
        self.assertNotIn("shard-1", game.storage)
        paid = game.deployment_spend
        deploy(game, game.revision, uuid4(), rollback=game.deployments[-1].id)
        self.assertIsNotNone(game.migration)
        self.assertGreater(game.deployment_spend, paid)
        advance(game, game.migration.ready_at - game.tick)
        self.assertEqual(game.production, original)
        self.assertGreater(game.storage["shard-1"], 0)
        self.assertGreaterEqual(sum(game.storage.values()), 15)

    def test_unlocks_import_validation_and_live_patch_are_explicit(self):
        game = fixture()
        candidate = game.production.model_copy(deep=True)
        candidate.nodes[2].config["role"] = "Accounts"
        self.assertTrue(review(game, game.revision, candidate).errors)
        first = view(game, datetime.now(UTC))
        _, previous = live_frame(first, None, 1)
        develop_research(game, "queries")
        frame, _ = live_frame(view(game, datetime.now(UTC)), previous, 2)
        self.assertIn("engineering", frame["changes"])
        game.engineering["sharding"] = 0
        game = type(game).model_validate(game.model_dump())
        _, portable = export_file(game)
        with self.assertRaises(RuleError):
            parse_save_file(portable.model_dump_json().encode())
