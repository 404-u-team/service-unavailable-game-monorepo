from datetime import UTC, datetime, timedelta
from unittest import TestCase
from uuid import uuid4

from src.api.game_schemas import OnboardingAction, PatchDiagram
from src.services.games import (
    RevisionConflict,
    advance_clock,
    change_onboarding,
    onboarding_progress,
    patch_diagram,
    view,
)
from src.services.live import live_frame
from src.services.markets import (
    campaign_plan,
    develop_language,
    market_action,
    markets,
    targeted_campaign,
)
from src.simulation.catalog import REGIONS
from src.simulation.demand import local_time, workload
from src.simulation.engine import evaluate
from src.simulation.models import DiagramGroup, Position
from src.simulation.progression import advance
from src.simulation.topology import RuleError

from tests.test_simulation import add_node, fixture, link, monitor


class WorkbenchFeatures(TestCase):
    def test_layout_patches_merge_fields_and_guard_group_conflicts(self):
        game = fixture()
        baseline = game.production.model_copy(deep=True)
        group = DiagramGroup(id="data", name="Data", members=["db"])
        patch_diagram(
            game, PatchDiagram(request_id=uuid4(), groups=[group], group_base=[])
        )
        patch_diagram(
            game,
            PatchDiagram(request_id=uuid4(), positions={"api": Position(x=500, y=400)}),
        )
        with self.assertRaises(RevisionConflict):
            patch_diagram(
                game, PatchDiagram(request_id=uuid4(), groups=[], group_base=[])
            )
        self.assertEqual(game.diagram.groups, [group])
        self.assertEqual(game.diagram.positions["api"].y, 400)
        self.assertEqual(game.production, baseline)

    def test_five_times_clock_and_live_history_patch(self):
        game = fixture()
        anchor = datetime.now(UTC)
        first, raw = live_frame(view(game, anchor), None, 1)
        game.speed = 5
        now = anchor + timedelta(seconds=2)
        self.assertEqual(advance_clock(game, anchor, now)[1], 5)
        delta, updated = live_frame(view(game, now), raw, 2)
        self.assertEqual(first["type"], "snapshot")
        self.assertEqual(delta["changes"]["tick"], 5)
        self.assertNotIn("production", delta["changes"])
        for name, section in (("business_history", None), ("finance", "economy")):
            before = raw[section]["history"] if section else raw[name]
            after = updated[section]["history"] if section else updated[name]
            patch = delta["histories"][name]
            self.assertEqual(before[patch["drop"] :] + patch["append"], after)

    def test_replica_must_use_same_primary_as_its_readers(self):
        game = fixture()
        monitor(game, "db")
        add_node(game, "independent", "database")
        add_node(game, "read", "replica")
        link(game, "api", "read")
        link(game, "read", "telemetry")
        self.assertEqual(evaluate(game).snapshot.components["read"].throughput, 0)
        link(game, "read", "independent")
        result = evaluate(game)
        self.assertEqual(result.snapshot.components["read"].throughput, 0)
        self.assertEqual(result.storage.get("independent", 0), 0)
        game.production.edges = [
            edge for edge in game.production.edges if edge.target != "independent"
        ]
        link(game, "read", "db")
        result = evaluate(game)
        traffic = next(
            edge for edge in result.snapshot.traffic if edge.target == "read"
        )
        self.assertNotIn("send", traffic.operations)
        self.assertGreater(result.snapshot.components["read"].throughput, 0)

    def test_market_launch_targeted_acquisition_and_localization(self):
        game = fixture()
        region = "south_america"
        with self.assertRaises(RuleError):
            campaign_plan(game, "ads", region, 100, 8)
        market_action(game, region, "develop")
        self.assertEqual(
            next(m.stage for m in markets(game) if m.id == region), "developing"
        )
        with self.assertRaises(RuleError):
            market_action(game, region, "launch")
        develop_language(game, "Spanish")
        advance(game, REGIONS[region]["duration"])
        self.assertEqual(
            next(m.stage for m in markets(game) if m.id == region), "ready"
        )
        market_action(game, region, "launch")
        localized = campaign_plan(game, "ads", region, 100, 8)
        control = game.model_copy(deep=True)
        control.language_projects.clear()
        baseline = campaign_plan(control, "ads", region, 100, 8)
        self.assertGreater(localized.acquired, baseline.acquired)
        targeted_campaign(game, "ads", localized)
        advance(game, 4)
        live = workload(game, overview=True)
        self.assertAlmostEqual(
            sum(live.operations.values()),
            sum(row.requests for row in live.overview.regions),
        )
        self.assertGreater(game.market_audience[region], 0)
        self.assertEqual(game.north_america_audience, 0)
        advance(game, 4)
        self.assertNotIn("ads", game.regional_campaigns)
        self.assertGreater(game.market_audience[region], localized.acquired * 0.98)

    def test_iana_offset_changes_with_the_simulated_season(self):
        self.assertEqual(local_time("America/New_York", 0)[2], -300)
        self.assertEqual(local_time("America/New_York", 180 * 1440)[2], -240)
        self.assertEqual(local_time("Asia/Kolkata", 0)[2], 330)

    def test_onboarding_advances_only_after_the_requested_milestone(self):
        game = fixture()

        def event(name):
            change_onboarding(
                game,
                OnboardingAction(
                    request_id=uuid4(),
                    step=onboarding_progress(game).step,
                    interaction=name,
                ),
            )

        event("next")
        event("next")
        event("inspect")
        self.assertEqual(game.onboarding.step, 3)
        event("coverage")
        self.assertEqual(game.onboarding.step, 3)
        monitor(game, "api", "db")
        event("coverage")
        self.assertEqual(game.onboarding.step, 4)
        event("skip")
        event("monitor")
        self.assertEqual(game.onboarding.step, 4)
        event("resume")
        event("monitor")
        self.assertEqual(game.onboarding.step, 5)
