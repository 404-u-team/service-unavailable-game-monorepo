import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from src.services.games import (
    GameService,
    change_feature,
    deploy,
    edit_draft,
    open_draft,
    start_campaign,
)
from src.services.markets import (
    campaign_plan,
    develop_language,
    market_action,
    targeted_campaign,
)
from src.services.save_files import MAX_SAVE_BYTES, export_file, parse_save_file
from src.simulation.engine import evaluate
from src.simulation.models import Diagram, Game, Onboarding
from src.simulation.onboarding import TutorialStep
from src.simulation.progression import advance, drill
from src.simulation.topology import RuleError

from tests.test_simulation import add_node, component, fixture, link, monitor


class SaveFileTests(TestCase):
    def roundtrip(self, game: Game):
        filename, exported = export_file(game)
        self.assertRegex(
            filename, r"^service-unavailable-pulse-messenger-\d{4}-\d{2}-\d{2}\.json$"
        )
        restored = parse_save_file(exported.model_dump_json().encode())
        self.assertEqual(restored, exported)
        self.assertEqual(restored.game, game)
        self.assertEqual(restored.preview().balance, game.balance)
        self.assertEqual(restored.preview().audience, round(game.audience))
        clone = restored.game.model_copy(update={"id": uuid4()})
        source = game.model_copy(deep=True)
        self.assertNotEqual(source.id, clone.id)
        self.assertEqual(evaluate(source), evaluate(clone))
        advance(source, 40)
        advance(clone, 40)
        self.assertEqual(source, clone.model_copy(update={"id": source.id}))
        self.assertEqual(evaluate(source), evaluate(clone))

    def test_new_game(self):
        self.roundtrip(fixture())

    def test_established_game_and_background_work(self):
        game = fixture()
        add_node(game, "jobs", "queue")
        add_node(game, "media", "worker", cpu=1)
        link(game, "api", "jobs")
        link(game, "jobs", "media")
        advance(game, 76)
        drill(game)
        game.clock_fraction = 0.42
        self.roundtrip(game)

    def test_replicas_cache_and_monitoring(self):
        game = fixture()
        add_node(game, "replica", "replica", connections=25)
        add_node(game, "cache", "cache", ttl=400)
        link(game, "api", "cache")
        link(game, "cache", "replica")
        link(game, "replica", "db")
        monitor(game, "db", "replica", "cache")
        advance(game, 12)
        self.assertGreater(game.replication["replica"], 0)
        self.roundtrip(game)

    def test_high_capacity_database_save(self):
        game = fixture()
        component(game, "db").config.update(cpu=32.0, disk="NVMe array")
        monitor(game, "db")
        self.roundtrip(game)

    def test_active_campaigns_and_regional_expansion(self):
        game = fixture()
        market_action(game, "south_america", "develop")
        develop_language(game, "Spanish")
        advance(game, 20)
        market_action(game, "south_america", "launch")
        market_action(game, "east_asia", "develop")
        start_campaign(game, "community")
        targeted_campaign(
            game, "creator", campaign_plan(game, "creator", "south_america", 100, 20)
        )
        advance(game, 3)
        self.roundtrip(game)

    def test_released_disabled_and_developing_features(self):
        game = fixture()
        change_feature(game, "images", "develop")
        advance(game, game.development["images"])
        change_feature(game, "images", "release")
        change_feature(game, "images", "disable")
        change_feature(game, "groups", "develop")
        self.roundtrip(game)

    def test_visual_groups_routes_draft_and_deployment_history(self):
        game = fixture()
        open_draft(game, 0)
        next_topology = game.draft.model_copy(deep=True)
        next_topology.nodes[-1].config["cpu"] = 4.0
        edit_draft(game, 1, next_topology)
        deploy(game, 2, uuid4())
        open_draft(game, 3)
        game.draft.nodes[-1].config["disk"] = "NVMe"
        game.diagram = Diagram.model_validate(
            {
                "positions": {"db": {"x": 540, "y": 200}},
                "routes": {"api:db": [{"x": 500, "y": 200}]},
                "groups": [
                    {
                        "id": "inner",
                        "name": "Storage",
                        "members": ["db"],
                        "collapsed": True,
                    },
                    {"id": "outer", "name": "Servers", "members": ["inner", "api"]},
                ],
                "viewports": {"wide": {"x": -80, "y": 20, "zoom": 0.8}},
            }
        )
        game.onboarding = Onboarding(step=3, furthest=5)
        self.roundtrip(game)

    def test_portable_tutorial_accepts_legacy_progress_and_round_trips_stable_ids(self):
        game = fixture()
        game.onboarding = Onboarding(step=3, furthest=4, skipped=True)
        _, exported = export_file(game)
        payload = exported.model_dump(mode="json")
        del payload["game"]["onboarding"]["step_id"]
        del payload["game"]["onboarding"]["furthest_id"]
        self.assertEqual(
            parse_save_file(json.dumps(payload).encode()).game.onboarding,
            game.onboarding,
        )
        game.onboarding = Onboarding(
            step=3,
            furthest=4,
            step_id=TutorialStep.LINK_COVERAGE,
            furthest_id=TutorialStep.OPEN_TELEMETRY,
        )
        self.roundtrip(game)

    def test_rejects_invalid_files(self):
        _, save = export_file(fixture())
        for raw, code in (
            (b"{broken", "save_file_json"),
            (b'{"version":1,"version":2}', "save_file_json"),
            (b'{"broken":"\\ud800"}', "save_file_json"),
            (b"[" * 2000, "save_file_json"),
            (b" " * (MAX_SAVE_BYTES + 1), "save_file_too_large"),
            (
                b'{"format":"service-unavailable-save","version":405}',
                "save_file_version",
            ),
            (
                b'{"format":"service-unavailable-save","version":true}',
                "save_file_invalid",
            ),
        ):
            with self.subTest(code=code), self.assertRaises(RuleError) as result:
                parse_save_file(raw)
            self.assertEqual(result.exception.code, code)

        def bad_game(**state):
            return save.model_dump(mode="json") | {
                "game": save.game.model_dump(mode="json") | state
            }

        missing = bad_game()
        del missing["game"]["settings"]
        bad_config = bad_game()
        bad_config["game"]["production"]["nodes"][-1]["config"]["disk"] = "SATA"
        bad_edge = bad_game()
        bad_edge["game"]["production"]["edges"][-1]["target"] = "missing"
        bad_kind = bad_game()
        bad_kind["game"]["production"]["nodes"][-1]["kind"] = "mystery"
        for data in (
            missing,
            bad_config,
            bad_edge,
            bad_kind,
            bad_game(tick=-1),
            bad_game(tick="0"),
            bad_game(tick=10**20),
            bad_game(campaigns={"unknown": 0}),
            bad_game(launched_markets=["unknown"]),
            bad_game(audience=-1),
            bad_game(owner="another"),
            bad_game(product={"premium_price": -500}),
        ):
            with (
                self.subTest(data=list(data["game"])),
                self.assertRaises(RuleError) as result,
            ):
                parse_save_file(json.dumps(data).encode())
            self.assertEqual(
                result.exception.code,
                "save_file_invalid"
                if data["game"]["tick"] != 10**20
                else "save_file_json",
            )


class PortableClockTests(IsolatedAsyncioTestCase):
    async def test_running_save_carries_the_partial_tick_without_time_in_transit(self):
        game = fixture()
        game.speed = 3
        exported_at = datetime(2026, 11, 14, tzinfo=UTC)
        row = {
            "clock_at": exported_at - timedelta(seconds=0.3),
            "saved_at": exported_at,
        }

        @asynccontextmanager
        async def locked(_owner, _id):
            yield None, row

        repository = AsyncMock()
        repository.lock = locked
        repository.restore = lambda _: game.model_copy(deep=True)
        service = GameService(repository)
        with patch("src.services.games.datetime") as clock:
            clock.now.return_value = exported_at
            saved = await service.read(
                "source",
                game.id,
                lambda snapshot, _: export_file(snapshot)[1],
                capture_clock=True,
            )
        self.assertAlmostEqual(saved.game.clock_fraction, 0.45)
        repository.save.assert_not_awaited()
        imported_at = exported_at + timedelta(days=10)
        repository.create.return_value = imported_at
        result = await service.import_game("destination", saved.game)
        owner, restored, elapsed = repository.create.await_args.args
        self.assertEqual(owner, "destination")
        self.assertEqual(result.saved_at, imported_at)
        self.assertEqual(result.tick, game.tick)
        self.assertNotEqual(result.id, game.id)
        self.assertEqual(restored.speed, game.speed)
        self.assertEqual(elapsed, timedelta(seconds=0.3))
