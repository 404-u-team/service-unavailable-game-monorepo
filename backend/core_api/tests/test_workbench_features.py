from datetime import UTC, datetime, timedelta
from unittest import TestCase
from uuid import uuid4

from src.api.game_schemas import (
    ClockAction,
    OnboardingAction,
    PatchDiagram,
    TutorialProgressAction,
)
from src.services.games import (
    RevisionConflict,
    advance_clock,
    change_onboarding,
    deploy,
    edit_draft,
    onboarding_progress,
    open_draft,
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
from src.simulation.models import DiagramGroup, Onboarding, Position
from src.simulation.onboarding import TutorialStep
from src.simulation.progression import advance
from src.simulation.topology import RuleError

from tests.test_simulation import add_node, component, fixture, link, monitor


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

    def test_fast_clock_and_live_history_patch(self):
        for speed in (5, 10, 20, 50):
            with self.subTest(speed=speed):
                game = fixture()
                anchor = datetime.now(UTC)
                first, raw = live_frame(view(game, anchor), None, 1)
                game.speed = ClockAction(request_id=uuid4(), speed=speed).speed
                game = type(game).model_validate_json(game.model_dump_json())
                now = anchor + timedelta(seconds=2)
                self.assertEqual(advance_clock(game, anchor, now), (now, speed))
                delta, updated = live_frame(view(game, now), raw, 2)
                self.assertEqual(first["type"], "snapshot")
                self.assertEqual(delta["changes"]["tick"], speed)
                self.assertEqual(delta["changes"]["speed"], speed)
                self.assertNotIn("production", delta["changes"])
                for name, section in (
                    ("business_history", None),
                    ("finance", "economy"),
                ):
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

    def test_tutorial_requires_the_api_edit_and_records_the_deployment_in_the_same_mutation(
        self,
    ):
        game = fixture()
        game.onboarding = Onboarding(
            step=6,
            furthest=6,
            step_id=TutorialStep.CREATE_DRAFT,
            furthest_id=TutorialStep.CREATE_DRAFT,
        )

        def event(step, interaction="observed"):
            change_onboarding(
                game,
                TutorialProgressAction(
                    request_id=uuid4(), step_id=step, interaction=interaction
                ),
            )
            return onboarding_progress(game).step_id

        self.assertEqual(event(TutorialStep.CREATE_DRAFT), TutorialStep.CREATE_DRAFT)
        open_draft(game, game.revision)
        self.assertEqual(event(TutorialStep.CREATE_DRAFT), TutorialStep.EDIT_API)
        self.assertEqual(event(TutorialStep.CREATE_DRAFT), TutorialStep.EDIT_API)
        self.assertEqual(event(TutorialStep.EDIT_API), TutorialStep.SAVE_CAPACITY)
        self.assertEqual(event(TutorialStep.SAVE_CAPACITY), TutorialStep.SAVE_CAPACITY)
        topology = game.draft.model_copy(deep=True)
        next(node for node in topology.nodes if node.id == "api").config["cpu"] = 4
        edit_draft(game, game.revision, topology)
        self.assertEqual(
            event(TutorialStep.SAVE_CAPACITY), TutorialStep.CAPACITY_REVIEW
        )
        self.assertEqual(
            event(TutorialStep.CAPACITY_REVIEW), TutorialStep.CAPACITY_FORECAST
        )
        self.assertEqual(
            event(TutorialStep.CAPACITY_FORECAST, "next"), TutorialStep.CAPACITY_COSTS
        )
        self.assertEqual(
            event(TutorialStep.CAPACITY_COSTS, "next"), TutorialStep.CAPACITY_DEPLOY
        )
        self.assertEqual(
            event(TutorialStep.CAPACITY_DEPLOY), TutorialStep.CAPACITY_DEPLOY
        )
        self.assertEqual(component(game, "api").config, {})
        deploy(game, game.revision, uuid4())
        self.assertEqual(onboarding_progress(game).step_id, TutorialStep.COMPARE)
        self.assertEqual(component(game, "api").config["cpu"], 4)
        self.assertEqual(
            event(TutorialStep.COMPARE, "back"), TutorialStep.CAPACITY_DEPLOY
        )
        self.assertEqual(
            event(TutorialStep.CAPACITY_DEPLOY, "next"), TutorialStep.COMPARE
        )

    def test_migrating_and_restarting_tutorial_preserves_gameplay(self):
        game = fixture()
        game.onboarding = Onboarding(step=3, furthest=5, skipped=True)
        progress = onboarding_progress(game)
        self.assertEqual(progress.step_id, TutorialStep.MONITORING)
        self.assertEqual(progress.furthest_id, TutorialStep.TELEMETRY)
        self.assertTrue(progress.skipped)
        original = game.production.model_copy(deep=True)
        change_onboarding(
            game,
            TutorialProgressAction(
                request_id=uuid4(),
                step_id=TutorialStep.MONITORING,
                interaction="restart",
            ),
        )
        self.assertEqual(onboarding_progress(game).step_id, TutorialStep.CLOCK)
        self.assertEqual(onboarding_progress(game).furthest_id, TutorialStep.CLOCK)
        self.assertFalse(game.onboarding.skipped)
        self.assertEqual(game.production, original)
