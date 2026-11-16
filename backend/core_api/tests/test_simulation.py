from datetime import UTC, datetime, timedelta
from unittest import TestCase
from uuid import UUID, uuid4

from src.services.games import (
    RevisionConflict,
    advance_clock,
    change_feature,
    deploy,
    edit_draft,
    feature_state,
    forecast,
    open_draft,
    review,
    start_campaign,
    view,
)
from src.simulation.catalog import CAMPAIGNS
from src.simulation.database import standalone_limits
from src.simulation.engine import demand, evaluate
from src.simulation.models import Edge, Game, Kind, Node, Position
from src.simulation.progression import advance, drill, new_game
from src.simulation.topology import (
    RuleError,
    config,
    daily_cost,
    inspect_graph,
    topology_cost,
)


def fixture(seed: int = 7) -> Game:
    return new_game(UUID(int=1), "Pulse Messenger", seed, "messenger")


def component(game: Game, node_id: str) -> Node:
    return next(node for node in game.production.nodes if node.id == node_id)


def add_node(game: Game, node_id: str, kind: Kind, **config) -> None:
    game.production.nodes.append(
        Node(
            id=node_id,
            kind=kind,
            name=node_id,
            position=Position(x=0, y=0),
            config=config,
        )
    )


def link(game: Game, source: str, target: str) -> None:
    game.production.edges.append(Edge(source=source, target=target))


def monitor(game: Game, *targets: str) -> None:
    add_node(game, "telemetry", "monitor", detail="Service history")
    for target in targets:
        link(game, target, "telemetry")


class SimulationTests(TestCase):
    def test_determinism_and_restoring_internal_state(self):
        a = fixture(17)
        start_campaign(a, "community")
        advance(a, 15)
        b = Game.model_validate_json(a.model_dump_json())
        advance(a, 125)
        for steps in (1, 23, 72, 29):
            advance(b, steps)
        self.assertEqual(a, b)
        self.assertTrue(a.incidents)
        self.assertEqual(evaluate(a), evaluate(b))

    def test_old_saves_load_without_layout_and_keep_legacy_database_limits(self):
        game = fixture()
        game.released.extend(["images", "voice"])
        component(game, "api").config["cpu"] = 2.5
        component(game, "db").config = {"reads": 45.0, "writes": 30.0}
        monitor(game, "api", "db")
        state = game.model_dump(mode="json")
        state.pop("diagram")
        state.pop("infrastructure_releases")
        state["settings"].pop("show_objectives")
        state["history"][0].pop("peak_utilization")
        loaded = Game.model_validate(state)
        self.assertEqual(loaded.production, game.production)
        self.assertEqual(loaded.diagram.positions, {})
        self.assertEqual(loaded.diagram.groups, [])
        self.assertTrue(loaded.settings.show_objectives)
        self.assertEqual(loaded.released, ["text", "images", "voice"])
        self.assertTrue(evaluate(loaded).snapshot.monitored)
        self.assertIn("voice", evaluate(loaded).snapshot.demand)
        self.assertEqual(standalone_limits(config(component(loaded, "db"))), (45, 30))
        self.assertEqual(evaluate(loaded), evaluate(game))
        self.assertEqual(loaded.history[0].peak_utilization, {})

    def test_resource_history_records_only_components_covered_at_the_time(self):
        game = fixture()
        monitor(game, "api")
        add_node(game, "live-only", "monitor", detail="Linked components")
        link(game, "db", "live-only")
        advance(game, 1)
        self.assertEqual(set(game.history[-1].peak_utilization), {"api"})
        self.assertGreater(game.history[-1].peak_utilization["api"], 0)
        self.assertIn("db", evaluate(game).snapshot.components)
        self.assertEqual(game.history[0].peak_utilization, {})

        link(game, "db", "telemetry")
        advance(game, 1)
        self.assertEqual(set(game.history[-1].peak_utilization), {"api", "db"})
        self.assertNotIn("db", game.history[1].peak_utilization)

        game.production.edges = [
            edge
            for edge in game.production.edges
            if (edge.source, edge.target) != ("db", "telemetry")
        ]
        advance(game, 1)
        self.assertNotIn("db", game.history[-1].peak_utilization)
        self.assertIn("db", game.history[2].peak_utilization)

    def test_clock_accounts_for_partial_ticks_without_browser_time(self):
        a = fixture()
        origin = datetime(2026, 1, 1, tzinfo=UTC)
        a.speed = 1
        anchor, steps = advance_clock(a, origin, origin + timedelta(seconds=3))
        self.assertEqual((anchor, steps, a.tick), (origin + timedelta(seconds=2), 1, 1))
        a.speed = 3
        anchor, steps = advance_clock(a, anchor, anchor + timedelta(seconds=2))
        self.assertEqual((steps, a.tick), (3, 4))
        a.speed = 0
        self.assertEqual(advance_clock(a, anchor, anchor + timedelta(days=1))[1], 0)
        self.assertEqual(a.tick, 4)

    def test_difficulty_changes_starting_conditions(self):
        beginner = fixture()
        expert = new_game(UUID(int=1), "Pulse Messenger", 7, "messenger", "expert")
        self.assertLess(expert.balance, beginner.balance)
        self.assertGreater(expert.audience, beginner.audience)
        self.assertGreater(
            evaluate(expert).snapshot.metrics.rps,
            evaluate(beginner).snapshot.metrics.rps,
        )

    def test_workload_changes_by_user_count_time_and_features(self):
        game = fixture()
        baseline = demand(game)
        doubled = demand(game, game.audience * 2)
        self.assertAlmostEqual(doubled["send"], 2 * baseline["send"])
        game.tick += 36
        self.assertGreater(demand(game)["history"], baseline["history"])
        game.released.append("images")
        self.assertGreater(demand(game)["upload"], 0)

    def test_route_dependencies_and_unconnected_components(self):
        game = fixture()
        baseline = evaluate(game).snapshot.metrics
        add_node(game, "idle", "cache")
        self.assertEqual(evaluate(game).snapshot.metrics, baseline)
        game.production.edges = [
            edge for edge in game.production.edges if edge.target != "db"
        ]
        self.assertLess(evaluate(game).snapshot.metrics.availability, 0.25)

    def test_compute_memory_and_network_are_limits(self):
        game = fixture()
        monitor(game, "api")
        api = component(game, "api")
        api.config = {"cpu": 1}
        cpu = evaluate(game).snapshot
        self.assertGreater(cpu.components["api"].utilization["CPU"], 1)
        api.config = {"cpu": 8, "memory": 1}
        ram = evaluate(game).snapshot
        self.assertGreater(ram.components["api"].utilization["RAM"], 1)
        api.config = {"cpu": 8, "memory": 16}
        scaled = evaluate(game).snapshot
        self.assertGreater(scaled.metrics.availability, ram.metrics.availability)
        game.released.extend(["images", "files"])
        api.config["network"] = 5
        self.assertGreater(
            evaluate(game).snapshot.components["api"].utilization["Network"], 1
        )

    def test_database_read_and_write_saturation_and_api_replicas(self):
        game = fixture()
        monitor(game, "db", "api")
        api, db = component(game, "api"), component(game, "db")
        api.config = {"cpu": 8, "memory": 16}
        db.config = {"reads": 25, "writes": 80}
        before = evaluate(game).snapshot
        self.assertGreater(before.components["db"].utilization["Reads"], 1)
        self.assertLess(before.components["db"].utilization["Writes"], 1)
        api.config["instances"] = 3
        after = evaluate(game).snapshot
        self.assertAlmostEqual(before.metrics.availability, after.metrics.availability)
        db.config = {"reads": 1000, "writes": 10}
        write = evaluate(game).snapshot
        self.assertGreater(write.components["db"].utilization["Writes"], 1)
        self.assertLess(write.components["db"].utilization["Reads"], 1)

    def test_database_resources_limit_throughput_and_legacy_values_are_throttles(self):
        game = fixture()
        db = component(game, "db")
        api = component(game, "api")
        api.config = {"cpu": 16, "memory": 32}
        game.audience = 16_000
        base = evaluate(game).snapshot.metrics
        base_cost = daily_cost(db)
        db.config = {"connections": 10_000, "reads": 10_000, "writes": 5_000}
        self.assertEqual(evaluate(game).snapshot.metrics, base)
        self.assertEqual(daily_cost(db), base_cost)
        db.config = {"cpu": 8, "memory": 32, "disk": "NVMe"}
        self.assertGreater(evaluate(game).snapshot.metrics.throughput, base.throughput)
        self.assertGreater(daily_cost(db), base_cost)
        reads, writes = standalone_limits(config(db))
        self.assertGreater(reads, writes)
        db.config["cpu"] = 33
        with self.assertRaises(RuleError):
            inspect_graph(game.production)

    def test_monitor_slots_limit_visibility_without_consuming_capacity(self):
        game = fixture()
        traffic = evaluate(game).snapshot.metrics
        monitor(game, "api", "db", "edge")
        collector = component(game, "telemetry")
        collector.config = {"slots": 2}
        seen = evaluate(game).snapshot
        self.assertEqual(seen.metrics, traffic)
        self.assertEqual(seen.monitors["telemetry"].covered, ["api", "db"])
        self.assertEqual(seen.monitors["telemetry"].dropped, ["edge"])
        self.assertNotIn("edge", seen.components)
        cost = daily_cost(collector)
        collector.config = {"slots": 6, "detail": "Service history"}
        expanded = evaluate(game).snapshot
        self.assertEqual(expanded.metrics, traffic)
        self.assertIn("edge", expanded.components)
        self.assertTrue(expanded.monitored)
        self.assertGreater(daily_cost(collector), cost)

    def test_cache_misses_route_and_read_caching_preserves_write_load(self):
        game = fixture()
        monitor(game, "db")
        original = evaluate(game).snapshot.components["db"]
        add_node(game, "cache", "cache", ttl=500)
        link(game, "api", "cache")
        link(game, "cache", "db")
        link(game, "cache", "telemetry")
        result = evaluate(game).snapshot
        self.assertGreater(result.components["cache"].cache_hit, 0.5)
        self.assertLess(
            result.components["db"].utilization["Reads"], original.utilization["Reads"]
        )
        self.assertAlmostEqual(
            result.components["db"].utilization["Writes"],
            original.utilization["Writes"],
        )
        game.production.edges = [
            edge
            for edge in game.production.edges
            if (edge.source, edge.target) != ("cache", "db")
        ]
        fallback = evaluate(game).snapshot
        self.assertEqual(fallback.components["cache"].cache_hit, 0)
        self.assertAlmostEqual(
            fallback.components["db"].utilization["Reads"],
            original.utilization["Reads"],
        )
        self.assertFalse(any(edge.target == "cache" for edge in fallback.traffic))
        game.production.edges = [
            edge
            for edge in game.production.edges
            if (edge.source, edge.target) != ("api", "db")
        ]
        self.assertEqual(evaluate(game).snapshot.components["cache"].cache_hit, 0)

    def test_replica_requires_primary_and_offloads_reads(self):
        game = fixture()
        monitor(game, "db")
        base = evaluate(game).snapshot.components["db"].utilization["Reads"]
        add_node(game, "read", "replica")
        link(game, "api", "read")
        link(game, "read", "db")
        link(game, "read", "telemetry")
        result = evaluate(game).snapshot
        self.assertLess(result.components["db"].utilization["Reads"], base)
        self.assertGreater(result.components["read"].throughput, 0)

    def test_load_balancing_and_instance_failure(self):
        game = fixture()
        monitor(game, "api")
        add_node(game, "api2", "api", cpu=8, memory=16, connections=4000)
        link(game, "edge", "api2")
        link(game, "api2", "db")
        link(game, "api2", "telemetry")
        balanced = evaluate(game).snapshot.components
        self.assertAlmostEqual(balanced["api"].rps, balanced["api2"].rps)
        component(game, "edge").config["algorithm"] = "Weighted capacity"
        weighted = evaluate(game).snapshot.components
        self.assertGreater(weighted["api2"].rps, weighted["api"].rps)
        drill(game)
        active = evaluate(game).snapshot
        self.assertEqual(active.components["api"].status, "failed")
        self.assertEqual(active.components["api"].throughput, 0)
        self.assertAlmostEqual(active.components["api2"].rps, active.metrics.rps)
        component(game, "edge").config["health"] = "Disabled"
        self.assertGreater(
            evaluate(game).snapshot.metrics.errors, active.metrics.errors
        )
        advance(game, 12)
        self.assertEqual(game.incidents[0].resolution, "Capacity restored")

    def test_rate_limit_reports_rejections_and_respects_scope(self):
        game = fixture()
        monitor(game, "api")
        add_node(game, "throttle", "limiter", limit=2, burst=0, scope="Writes")
        game.production.edges.pop(0)
        link(game, "traffic", "throttle")
        link(game, "throttle", "edge")
        result = evaluate(game).snapshot
        self.assertGreater(result.metrics.rejected, 25)
        self.assertGreater(result.metrics.throughput, 80)
        self.assertLessEqual(result.metrics.rejected, result.metrics.errors)

    def test_queue_overflow_and_worker_processing(self):
        game = fixture()
        monitor(game, "api")
        add_node(game, "jobs", "queue", capacity=100)
        link(game, "api", "jobs")
        link(game, "jobs", "telemetry")
        overloaded = evaluate(game).snapshot
        self.assertEqual(overloaded.components["jobs"].backlog, 100)
        self.assertGreater(overloaded.metrics.errors, 0)
        add_node(game, "worker", "worker")
        link(game, "jobs", "worker")
        link(game, "worker", "telemetry")
        recovered = evaluate(game).snapshot
        self.assertEqual(recovered.components["jobs"].backlog, 0)
        self.assertGreater(recovered.components["worker"].throughput, 0)
        self.assertGreater(recovered.metrics.throughput, overloaded.metrics.throughput)

    def test_worker_memory_limits_jobs_and_backlog_does_not_add_request_latency(self):
        game = fixture()
        game.released.extend(["images", "voice", "files"])
        component(game, "db").config["storage"] = 500
        monitor(game, "jobs", "worker")
        add_node(game, "jobs", "queue")
        add_node(game, "worker", "worker", cpu=8, concurrency=30, memory=1)
        link(game, "api", "jobs")
        link(game, "jobs", "worker")
        game.queues["jobs"] = 20_000
        slow = evaluate(game).snapshot
        self.assertAlmostEqual(slow.components["worker"].throughput, 10)
        self.assertGreater(slow.components["jobs"].queue_wait_minutes, 0)
        self.assertGreater(slow.components["jobs"].jobs_expired, 0)
        component(game, "worker").config["memory"] = 8
        fast = evaluate(game).snapshot
        self.assertGreater(fast.components["worker"].throughput, 10)
        self.assertEqual(fast.components["jobs"].backlog, 0)
        self.assertEqual(fast.metrics.latency, slow.metrics.latency)

    def test_search_requirement_routes_new_releases_to_indexed_primary(self):
        game = fixture()
        game.released.append("groups")
        change_feature(game, "search", "develop")
        advance(game, 28)
        self.assertFalse(feature_state(game, "search").can_release)
        monitor(game, "db", "cache")
        add_node(game, "cache", "cache")
        link(game, "api", "cache")
        link(game, "cache", "db")
        component(game, "db").config["search_index"] = "Enabled"
        self.assertTrue(feature_state(game, "search").can_release)
        change_feature(game, "search", "release")
        snapshot = evaluate(game).snapshot
        self.assertGreater(snapshot.demand["search"], 0)
        queries = next(
            edge
            for edge in snapshot.traffic
            if (edge.source, edge.target) == ("api", "db")
        )
        self.assertGreater(queries.operations["search"], 0)
        lookups = next(edge for edge in snapshot.traffic if edge.target == "cache")
        self.assertNotIn("search", lookups.operations)

    def test_observability_controls_telemetry_and_forecast_confidence(self):
        game = fixture()
        drill(game)
        now = datetime.now(UTC)
        private = view(game, now)
        self.assertEqual(private.snapshot.components, {})
        self.assertEqual(private.history, [])
        self.assertIsNone(private.incidents[0].target)
        self.assertEqual(forecast(game, game.production).confidence, "low")
        monitor(game, "api", "db")
        observable = view(game, now)
        self.assertEqual(observable.incidents[0].target, "api")
        self.assertTrue(observable.history)
        self.assertEqual(forecast(game, game.production).confidence, "high")

    def test_growth_churn_and_consistent_economy(self):
        normal, outage = fixture(), fixture()
        outage.production.edges = []
        advance(normal, 18)
        advance(outage, 18)
        self.assertGreater(normal.audience, 8400)
        self.assertLess(outage.audience, 8400)
        self.assertGreater(normal.satisfaction, outage.satisfaction)
        self.assertEqual(normal.revenue, 0)
        self.assertEqual(outage.revenue, 0)
        self.assertAlmostEqual(
            normal.balance, 10_000 + normal.revenue - normal.operating
        )
        self.assertAlmostEqual(
            outage.operating, topology_cost(outage.production) * 18 / 144
        )

    def test_campaign_cost_growth_forecast_and_completion(self):
        game = fixture()
        campaign = CAMPAIGNS["community"]
        before = evaluate(game).snapshot.metrics
        prediction = forecast(game, game.production, "community")
        self.assertGreater(prediction.rps.high, before.rps)
        start_campaign(game, "community")
        self.assertEqual(game.balance, 10_000 - campaign["cost"])
        with self.assertRaises(RuleError):
            start_campaign(game, "community")
        advance(game, campaign["duration"])
        self.assertFalse(game.campaigns)
        self.assertGreater(game.audience, 11_400)
        self.assertGreater(evaluate(game).snapshot.metrics.rps, before.rps)

    def test_feature_lifecycle_and_real_workload(self):
        game = fixture()
        self.assertEqual(feature_state(game, "search").state, "locked")
        change_feature(game, "groups", "develop")
        with self.assertRaises(RuleError):
            change_feature(game, "groups", "release")
        self.assertEqual(game.development_spend, 650)
        advance(game, 12)
        self.assertEqual(feature_state(game, "groups").state, "ready")
        baseline = evaluate(game).snapshot.metrics.rps
        change_feature(game, "groups", "release")
        self.assertGreater(evaluate(game).snapshot.metrics.rps, baseline)
        self.assertIn("groups", demand(game))
        self.assertEqual(feature_state(game, "search").state, "available")

    def test_invalid_draft_deployment_does_not_change_production(self):
        game = fixture()
        baseline = game.production.model_copy(deep=True)
        open_draft(game, 0)
        broken = game.draft.model_copy(deep=True)
        broken.edges = [edge for edge in broken.edges if edge.target != "db"]
        edit_draft(game, 1, broken)
        self.assertTrue(review(game, 2).errors)
        with self.assertRaises(RuleError):
            deploy(game, 2, uuid4())
        self.assertEqual(game.production, baseline)
        self.assertEqual(game.balance, 10_000)
        with self.assertRaises(RevisionConflict):
            edit_draft(game, 1, baseline)
        invalid = broken.model_copy(deep=True)
        invalid.nodes[2].config["cpu"] = "four"
        self.assertTrue(review(game, 2, invalid).errors)
        with self.assertRaises(RuleError):
            edit_draft(game, 2, invalid)

    def test_running_routing_deployment_can_temporarily_drop_traffic(self):
        game = fixture()
        game.speed = 1
        open_draft(game, 0)
        draft = game.draft.model_copy(deep=True)
        draft.edges = [
            edge for edge in draft.edges if edge.source not in {"edge", "traffic"}
        ]
        draft.edges.append(Edge(source="traffic", target="api"))
        edit_draft(game, 1, draft)
        self.assertTrue(
            any("interruption" in warning for warning in review(game, 2).warnings)
        )
        deploy(game, 2, uuid4())
        self.assertLess(evaluate(game).snapshot.metrics.availability, 1)
        advance(game, 2)
        self.assertEqual(game.incidents[-1].resolution, "Activity returned to baseline")
        self.assertEqual(evaluate(game).snapshot.metrics.availability, 1)

    def test_media_writes_respect_remaining_disk_capacity(self):
        game = fixture()
        game.released.append("images")
        game.storage["db"] = 31.99
        nearly_full = evaluate(game)
        self.assertLessEqual(nearly_full.storage["db"], 32)
        game.storage = nearly_full.storage
        full = evaluate(game)
        self.assertLess(full.snapshot.metrics.availability, 0.8)

    def test_deploy_and_rollback_persist_layout_and_configuration(self):
        game = fixture()
        open_draft(game, 0)
        changed = game.draft.model_copy(deep=True)
        node = next(node for node in changed.nodes if node.id == "api")
        node.config["instances"] = 2
        node.position.x += 70
        edit_draft(game, 1, changed)
        expected = review(game, 2)
        self.assertEqual(expected.changes["modified"], ["Messenger API"])
        self.assertEqual(expected.changes["moved"], ["Messenger API"])
        deployment = uuid4()
        deploy(game, 2, deployment)
        self.assertEqual(game.production, changed)
        self.assertIsNone(game.draft)
        self.assertEqual(game.balance, 10_000 - expected.install)
        deploy(game, 3, uuid4(), deployment)
        self.assertEqual(component(game, "api").config, {})
        self.assertEqual(component(game, "api").position.x, 505)

    def test_deployment_comparison_records_only_observable_resource_pressure(self):
        for covered in (False, True):
            with self.subTest(covered=covered):
                game = fixture()
                component(game, "db").config["cpu"] = 1.0
                if covered:
                    monitor(game, "db")
                open_draft(game, 0)
                candidate = game.draft.model_copy(deep=True)
                next(node for node in candidate.nodes if node.id == "db").config[
                    "connections"
                ] = 700.0
                edit_draft(game, 1, candidate)
                deploy(game, 2, uuid4())
                comparison = game.deployments[-1].comparison
                self.assertEqual(comparison.before, comparison.after)
                if covered:
                    self.assertEqual(
                        comparison.pressure_after.component, "Primary database"
                    )
                    self.assertGreater(comparison.pressure_after.utilization, 1)
                    self.assertEqual(
                        comparison.pressure_before, comparison.pressure_after
                    )
                else:
                    self.assertIsNone(comparison.pressure_before)
                    self.assertIsNone(comparison.pressure_after)
                restored = Game.model_validate_json(game.model_dump_json())
                self.assertEqual(restored.deployments[-1].comparison, comparison)
