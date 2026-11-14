import json
from datetime import UTC, datetime
from unittest import TestCase
from uuid import uuid4

from src.services.games import deploy, finance, forecast, review, view
from src.services.markets import campaign_plan, targeted_campaign
from src.services.save_files import export_file, parse_save_file
from src.simulation.catalog import COMPONENT_PRESETS, REGION_LANGUAGE_WEIGHTS
from src.simulation.database import DatabaseLoad
from src.simulation.demand import adoption, arrival_weight
from src.simulation.engine import evaluate
from src.simulation.models import Edge
from src.simulation.progression import advance, roll_event, spend
from src.simulation.topology import RuleError, config, daily_cost, inspect_graph

from tests.test_simulation import add_node, component, fixture, link, monitor


class OverhaulTests(TestCase):
    def test_free_downsize_recovers_balance_without_refunds(self):
        for cash in (-800, 0, 400):
            with self.subTest(cash=cash):
                game = fixture()
                component(game, "api").config["instances"] = 2
                game.balance = cash
                game.draft = game.production.model_copy(deep=True)
                game.draft.nodes[2].config["instances"] = 1
                estimate = review(game, game.revision)
                self.assertEqual(estimate.errors, [])
                self.assertEqual(estimate.install, 0)
                self.assertLess(estimate.daily_after, estimate.daily_before)
                deploy(game, game.revision, uuid4())
                self.assertEqual(game.balance, cash)
                self.assertEqual(game.deployment_spend, 0)
                self.assertFalse(game.recent_purchases)
                if cash <= 0:
                    with self.assertRaises(RuleError):
                        deploy(
                            game,
                            game.revision,
                            uuid4(),
                            rollback=game.deployments[-1].id,
                        )
        with self.assertRaises(ValueError):
            spend(game, -1, "deployment")

    def test_deployment_comparison_reuses_demand_and_reports_monitored_headroom(self):
        game = fixture()
        game.audience = 100
        monitor(game, "api", "db")
        component(game, "db").config.update(
            cpu=16, memory=64, disk="NVMe array", connections=4000
        )
        game.draft = game.production.model_copy(deep=True)
        game.draft.nodes[2].config["instances"] = 2
        deploy(game, game.revision, uuid4())
        comparison = game.deployments[-1].comparison
        self.assertEqual(comparison.before.rps, comparison.after.rps)
        self.assertEqual(comparison.before.throughput, comparison.after.throughput)
        self.assertGreater(comparison.capacity_after, comparison.capacity_before)
        self.assertIsNotNone(comparison.after.p95_latency)
        self.assertGreater(comparison.daily_after, comparison.daily_before)

    def test_budget_and_duration_use_one_deterministic_acquisition_curve(self):
        game = fixture()
        game.launched_markets.update({"south_america", "north_america"})
        regions = ["north_america", "europe", "south_america"]
        short = campaign_plan(game, "ads", regions, 1500.02, 18)
        long = campaign_plan(game, "ads", regions, 1500.02, 54)
        self.assertAlmostEqual(
            sum(part.budget for part in short.allocations.values()), short.budget
        )
        self.assertEqual(short.allocations, long.allocations)
        self.assertNotEqual(
            short.allocations["europe"].audience,
            short.allocations["south_america"].audience,
        )
        self.assertAlmostEqual(sum(short.arrivals), short.acquired)
        self.assertAlmostEqual(sum(long.arrivals), short.acquired)
        self.assertGreater(max(short.arrivals), max(long.arrivals))
        self.assertEqual(arrival_weight(1, 1), 1)
        fast = forecast(game, game.production, "ads", short).plan
        slow = forecast(game, game.production, "ads", long).plan
        self.assertGreater(
            fast.peak_rps - fast.baseline_peak_rps,
            slow.peak_rps - slow.baseline_peak_rps,
        )
        with self.assertRaises(RuleError):
            campaign_plan(game, "ads", ["europe", "oceania"], 1500, 18)
        with self.assertRaises(RuleError):
            campaign_plan(game, "ads", ["europe", "europe"], 1500, 18)

        advance(game, 2)
        before = finance(game, 100)
        targeted_campaign(game, "ads", short)
        after = finance(game, 100)
        self.assertAlmostEqual(before.balance - after.balance, short.budget)
        self.assertEqual(after.daily_profit, before.daily_profit)
        self.assertEqual(after.purchases[0][1].marketing, short.budget)
        advance(game, short.duration)
        self.assertNotIn("ads", game.regional_campaigns)
        self.assertGreater(game.market_audience["south_america"], 0)
        self.assertGreater(game.north_america_audience, 0)

    def test_existing_portable_campaigns_continue_with_defaults(self):
        game = fixture()
        targeted_campaign(
            game, "community", campaign_plan(game, "community", "europe", 80, 16)
        )
        _, payload = export_file(game)
        old = payload.model_dump(mode="json")
        old["game"]["regional_campaigns"]["community"].pop("allocations")
        old["game"]["incidents"][0].pop("cause")
        for item in old["game"]["history"]:
            item["metrics"].pop("p95_latency")
            item.pop("resource_utilization")
        loaded = parse_save_file(json.dumps(old).encode()).game
        self.assertFalse(loaded.regional_campaigns["community"].allocations)
        advance(loaded, 16)
        self.assertNotIn("community", loaded.regional_campaigns)

    def test_one_language_improves_multiple_markets_based_on_local_weight(self):
        game = fixture()
        for weights in REGION_LANGUAGE_WEIGHTS.values():
            self.assertAlmostEqual(sum(weights.values()), 1)
        game.language_projects["Spanish"] = game.tick
        self.assertGreater(adoption(game, "south_america"), adoption(game, "europe"))
        self.assertGreater(adoption(game, "north_america"), 1)
        self.assertEqual(adoption(game, "oceania"), 1)

    def test_managed_replacement_changes_recovery_time_and_respects_monitoring(self):
        game = fixture()
        game.tick = 32
        for seed in range(1000):
            game.seed = seed
            game.incidents.clear()
            roll_event(game)
            if game.incidents and game.incidents[-1].kind == "failure":
                break
        event = game.incidents[-1]
        self.assertEqual(event.cause, "Simulated hardware failure")
        hidden = view(game, datetime.now(UTC)).incidents[0]
        self.assertIsNone(hidden.cause)
        self.assertIsNone(hidden.target)
        self.assertEqual(hidden.title, "Service event")
        upgraded = game.model_copy(deep=True)
        upgraded.incidents.clear()
        component(upgraded, "api").config["recovery"] = "Managed replacement"
        monitor(upgraded, "api")
        roll_event(upgraded)
        improved = upgraded.incidents[-1]
        self.assertLess(improved.end - improved.start, event.end - event.start)
        self.assertGreater(
            daily_cost(component(upgraded, "api")), daily_cost(component(game, "api"))
        )
        self.assertEqual(
            view(upgraded, datetime.now(UTC)).incidents[0].cause, event.cause
        )
        self.assertEqual(evaluate(upgraded).snapshot.components["api"].status, "failed")
        component(upgraded, "api").config["instances"] = 2
        self.assertEqual(
            evaluate(upgraded).snapshot.components["api"].active_instances, 1
        )

    def test_deployment_rejects_split_messenger_datasets(self):
        game = fixture()
        expanded = game.model_copy(deep=True)
        add_node(expanded, "api-b", "api")
        add_node(expanded, "db-b", "database")
        link(expanded, "edge", "api-b")
        link(expanded, "api-b", "db-b")
        result = review(game, game.revision, expanded.production)
        self.assertIn("must share one primary", result.errors[0])
        expanded.production.edges[-1] = Edge(source="api-b", target="db")
        self.assertEqual(review(game, game.revision, expanded.production).errors, [])

    def test_topics_and_broadcast_route_real_job_load(self):
        game = fixture()
        for name in ("delivery", "audit"):
            add_node(game, name, "queue", topic="Notifications")
            link(game, "api", name)
        add_node(game, "media", "queue", topic="Media processing")
        link(game, "api", "media")
        monitor(game, "delivery", "audit", "media")
        distributed = evaluate(game).snapshot
        self.assertGreater(distributed.components["delivery"].rps, 0)
        self.assertEqual(distributed.components["media"].rps, 0)
        component(game, "audit").config["delivery"] = "Broadcast"
        broadcast = evaluate(game).snapshot
        for name in ("delivery", "audit"):
            self.assertAlmostEqual(
                broadcast.components[name].rps, 2 * distributed.components[name].rps
            )

    def test_presets_pass_graph_validation_and_disk_budget_has_documented_units(self):
        for kind, presets in COMPONENT_PRESETS.items():
            for name, settings in presets.items():
                with self.subTest(kind=kind, name=name):
                    game = fixture()
                    add_node(game, "test-preset", kind, **settings)
                    inspect_graph(game.production)
                    self.assertGreater(daily_cost(component(game, "test-preset")), 0)
        settings = config(component(fixture(), "db")) | {
            "disk": "NVMe",
            "search_index": "Enabled",
        }
        load = DatabaseLoad(settings, reads=120, writes=25, factor=0.8, followers=2)
        ratios = load.utilization()
        data = load.telemetry(ratios)
        self.assertAlmostEqual(
            (data.disk_read_iops + data.disk_write_iops) / data.disk_capacity_iops,
            ratios["Disk I/O"],
        )
