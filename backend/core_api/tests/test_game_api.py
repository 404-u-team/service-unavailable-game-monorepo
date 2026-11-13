"""Integration checks against a running Core API and its real PostgreSQL database."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
from unittest import TestCase, skipUnless
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

API_URL = os.environ.get("TEST_GAME_API_URL")


def session():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def call(client, path="", method="GET", payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{API_URL}/api/games{path}",
        body,
        {"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with client.open(request, timeout=8) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            return error.code, json.load(error)


def action(**kwargs):
    return {"request_id": str(uuid4()), **kwargs}


@skipUnless(API_URL, "Set TEST_GAME_API_URL to run PostgreSQL-backed API tests.")
class GameApiTests(TestCase):
    def setUp(self):
        self.client = session()
        self.assertEqual(call(self.client)[0], 200)
        self.create_body = {
            "id": str(uuid4()),
            "name": "Integration messenger",
            "seed": 7,
        }
        status, self.game = call(self.client, method="POST", payload=self.create_body)
        self.assertEqual(status, 201, self.game)
        self.path = f"/{self.game['id']}"

    def test_diagram_mutation_is_independent_from_deployment(self):
        diagram = {
            "positions": {"api": {"x": 600, "y": 300}},
            "routes": {"api:db": [{"x": 700, "y": 350}]},
            "groups": [
                {
                    "id": "storage",
                    "name": "Data path",
                    "members": ["api", "db"],
                    "collapsed": True,
                }
            ],
        }
        status, updated = call(
            self.client, self.path + "/diagram", "PUT", action(diagram=diagram)
        )
        self.assertEqual(status, 200, updated)
        self.assertEqual(updated["diagram"], diagram)
        self.assertEqual(updated["production"], self.game["production"])
        self.assertEqual(updated["revision"], self.game["revision"])
        self.assertEqual(updated["snapshot"], self.game["snapshot"])
        self.assertIsNone(updated["draft"])
        self.assertEqual(call(self.client, self.path)[1]["diagram"], diagram)

    def test_owned_saves_and_idempotent_creation(self):
        self.assertEqual(call(session(), self.path)[0], 404)
        self.assertEqual(call(session())[1], [])
        self.assertEqual(
            call(self.client, method="POST", payload=self.create_body)[1], self.game
        )
        self.assertEqual(len(call(self.client)[1]), 1)
        saved = call(self.client, self.path + "/save", "POST", action())[1]
        self.assertEqual(call(self.client, self.path)[1], saved)
        status, error = call(
            self.client,
            method="POST",
            payload=self.create_body | {"scenario": "social"},
        )
        self.assertEqual(status, 422, error)

    def test_voice_release_revalidates_production_and_generates_worker_load(self):
        def mutate(path, method="POST", **body):
            status, updated = call(
                self.client, self.path + path, method, action(**body)
            )
            self.assertEqual(status, 200, updated)
            return updated

        def finish_development(feature):
            target = next(
                item["remaining"]
                for item in mutate(f"/features/{feature}", action="develop")["features"]
                if item["id"] == feature
            )
            started = mutate("/clock", "PUT", speed=3)["tick"]
            deadline = time.monotonic() + (target + 8) * 2 / 3
            while time.monotonic() < deadline:
                current = call(self.client, self.path)[1]
                if current["tick"] >= started + target:
                    return mutate("/clock", "PUT", speed=0)
                time.sleep(0.25)
            self.fail("Development did not complete at 3× speed")

        finish_development("images")
        mutate("/features/images", action="release")
        ready = finish_development("voice")
        voice = next(item for item in ready["features"] if item["id"] == "voice")
        self.assertEqual(voice["state"], "ready")
        self.assertFalse(voice["can_release"])

        draft = mutate("/draft", revision=ready["revision"])
        topology = draft["draft"]
        for kind in ("queue", "worker", "monitor"):
            topology["nodes"].append(
                {
                    "id": kind,
                    "kind": kind,
                    "name": kind,
                    "position": {"x": 0, "y": 0},
                    "config": {"detail": "Service history"}
                    if kind == "monitor"
                    else {},
                }
            )
        topology["edges"].extend(
            {"source": source, "target": target}
            for source, target in (
                ("api", "queue"),
                ("queue", "worker"),
                ("queue", "monitor"),
                ("worker", "monitor"),
            )
        )
        edited = mutate("/draft", "PUT", revision=draft["revision"], topology=topology)
        status, rejected = call(
            self.client, self.path + "/features/voice", "POST", action(action="release")
        )
        self.assertEqual(status, 422, rejected)
        deployed = mutate("/deployments", revision=edited["revision"])
        self.assertTrue(
            next(item for item in deployed["features"] if item["id"] == "voice")[
                "can_release"
            ]
        )
        released = mutate("/features/voice", action="release")
        status, snapshot = call(self.client, self.path + "/monitoring")
        self.assertEqual(status, 200, snapshot)
        self.assertTrue(snapshot["monitored"])
        self.assertEqual(released["snapshot"], snapshot)
        self.assertGreater(snapshot["demand"]["voice"], 0)
        self.assertGreater(
            next(
                edge["operations"]["voice"]
                for edge in snapshot["traffic"]
                if edge["source"] == "queue" and edge["target"] == "worker"
            ),
            0,
        )

    def test_catalog_difficulty_profiles_match_new_games(self):
        status, catalog = call(self.client, "/catalog")
        self.assertEqual(status, 200, catalog)
        profiles = catalog["difficulties"]
        self.assertEqual(set(profiles), {"beginner", "standard", "expert"})
        for difficulty, profile in profiles.items():
            with self.subTest(difficulty=difficulty):
                status, game = call(
                    self.client,
                    method="POST",
                    payload=self.create_body
                    | {"id": str(uuid4()), "difficulty": difficulty},
                )
                self.assertEqual(status, 201, game)
                self.assertEqual(game["difficulty"], difficulty)
                self.assertEqual(game["balance"], profile["balance"])
                self.assertEqual(game["audience"], profile["audience"])

    def test_read_endpoints_and_incident_acknowledgement(self):
        self.assertEqual(
            call(self.client, self.path + "/architecture")[1], self.game["production"]
        )
        self.assertEqual(
            call(self.client, self.path + "/monitoring")[1], self.game["snapshot"]
        )
        self.assertEqual(
            call(self.client, self.path + "/finance")[1], self.game["economy"]
        )
        self.assertEqual(call(self.client, self.path + "/incidents")[1], [])
        status, game = call(
            self.client, self.path + "/incidents/drill", "POST", action()
        )
        self.assertEqual(status, 200, game)
        event = game["incidents"][0]
        self.assertIsNone(event["target"])
        self.assertNotIn("api", event["id"])
        status, game = call(
            self.client,
            self.path + f"/incidents/{event['id']}/acknowledge",
            "POST",
            action(),
        )
        self.assertEqual(status, 200, game)
        self.assertTrue(
            call(self.client, self.path + "/incidents")[1][0]["acknowledged"]
        )

    def test_concurrent_campaign_replay_is_charged_once(self):
        body = action()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda _: call(
                        self.client, self.path + "/campaigns/community", "POST", body
                    ),
                    range(2),
                )
            )
        self.assertEqual([status for status, _ in results], [200, 200])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(results[0][1]["economy"]["marketing"], 420)
        self.assertEqual(
            call(self.client, self.path + "/campaigns/ads", "POST", body)[0], 409
        )
        self.assertEqual(
            call(self.client, self.path + "/campaigns/community", "POST", action())[0],
            422,
        )

    def test_failed_deploy_preserves_draft_and_production(self):
        status, opened = call(
            self.client, self.path + "/draft", "POST", action(revision=0)
        )
        self.assertEqual(status, 200, opened)
        draft = opened["draft"]
        draft["edges"] = draft["edges"][:-1]
        status, changed = call(
            self.client, self.path + "/draft", "PUT", action(revision=1, topology=draft)
        )
        self.assertEqual(status, 200, changed)
        status, review = call(
            self.client, self.path + "/draft/review", "POST", {"revision": 2}
        )
        self.assertEqual(status, 200, review)
        self.assertTrue(review["errors"])
        self.assertEqual(
            call(self.client, self.path + "/deployments", "POST", action(revision=2))[
                0
            ],
            422,
        )
        self.assertEqual(
            call(self.client, self.path)[1]["production"], self.game["production"]
        )
        self.assertEqual(call(self.client, self.path)[1]["draft"], draft)
        self.assertEqual(
            call(self.client, self.path + "/draft/discard", "POST", action(revision=1))[
                0
            ],
            409,
        )
