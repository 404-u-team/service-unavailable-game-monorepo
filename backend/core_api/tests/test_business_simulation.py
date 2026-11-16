from datetime import UTC, datetime
from itertools import pairwise
from unittest import TestCase

from src.services.games import (
    change_feature,
    change_product,
    feature_state,
    start_campaign,
    view,
)
from src.simulation.catalog import ADVERTISING, DAYS_PER_MONTH, REGIONS, TICKS_PER_DAY
from src.simulation.demand import activity, ad_forecast, product_settings
from src.simulation.economy import TERM_TICKS, update_subscriptions
from src.simulation.engine import demand, evaluate
from src.simulation.models import Game, SubscriptionTerm
from src.simulation.progression import add_event, advance
from src.simulation.topology import RuleError, topology_cost

from tests.test_simulation import component, fixture, monitor


def release(game: Game, feature: str) -> None:
    change_feature(game, feature, "develop")
    advance(game, game.development[feature] - game.tick)
    change_feature(game, feature, "release")


class BusinessSimulationTests(TestCase):
    def test_recurring_costs_and_ledger_reconcile(self):
        game = fixture()
        self.assertEqual(
            topology_cost(game.production), (120 + 180 + 360) / DAYS_PER_MONTH
        )
        self.assertEqual(view(game, datetime.now(UTC)).economy.revenue, 0)
        release(game, "advertising")
        release(game, "premium")
        advance(game, 2 * TICKS_PER_DAY)
        result = view(game, datetime.now(UTC)).economy
        self.assertAlmostEqual(result.revenue_sources.total, result.revenue)
        self.assertAlmostEqual(result.daily_sources.total, result.daily_revenue)
        self.assertAlmostEqual(result.operating_costs.total, result.operating)
        self.assertAlmostEqual(result.daily_costs.total, result.daily_operating)
        self.assertAlmostEqual(
            result.daily_profit, result.daily_revenue - result.daily_operating
        )
        self.assertAlmostEqual(
            result.balance,
            result.starting_capital
            + result.cash_received
            - result.operating
            - result.development,
        )
        self.assertAlmostEqual(
            result.deferred_subscription_revenue,
            game.subscription_cash - game.subscription_revenue,
        )
        self.assertGreater(result.revenue_sources.advertising, 0)
        self.assertGreater(result.revenue_sources.subscriptions, 0)
        self.assertGreater(result.subscribers, 0)
        self.assertGreater(result.arpdau, 0)
        self.assertLess(result.daily_active_users, game.audience)

    def test_one_time_expenses_are_counted_once_in_the_daily_window(self):
        game = fixture()
        start_campaign(game, "community")
        change_feature(game, "advertising", "develop")
        economy = view(game, datetime.now(UTC)).economy
        self.assertEqual(economy.daily_total_expenses, 900)
        self.assertEqual(economy.daily_net_profit, -900)
        advance(game, 1)
        restored = Game.model_validate_json(game.model_dump_json())
        economy = view(restored, datetime.now(UTC)).economy
        self.assertEqual(economy.recent_purchases.total, 900)
        self.assertAlmostEqual(
            economy.daily_total_expenses, economy.daily_operating + 900
        )
        advance(restored, TICKS_PER_DAY - 1)
        economy = view(restored, datetime.now(UTC)).economy
        self.assertEqual(economy.recent_purchases.total, 0)
        self.assertEqual(economy.marketing + economy.development, 900)

    def test_ad_revenue_follows_served_eligible_impressions_and_disabling(self):
        game = fixture()
        release(game, "advertising")
        advance(game, 1)
        finance = game.history[-1].finance
        self.assertAlmostEqual(
            finance.revenue.advertising,
            finance.ad_impressions * ADVERTISING["moderate"]["cpm"] / 1000,
        )
        no_subs = ad_forecast(game, "moderate")
        game.subscriptions = [
            SubscriptionTerm(expires=TERM_TICKS, subscribers=game.audience / 2, price=4)
        ]
        self.assertAlmostEqual(
            ad_forecast(game, "moderate").requests_per_day, no_subs.requests_per_day / 2
        )
        game.subscriptions[0].subscribers = game.audience
        self.assertEqual(demand(game)["ad"], 0)
        game.subscriptions = []
        game.production.edges = []
        advance(game, 1)
        self.assertEqual(game.history[-1].finance.revenue.advertising, 0)
        spend = game.development_spend
        change_feature(game, "advertising", "disable")
        self.assertNotIn("ad", demand(game))
        self.assertFalse(feature_state(game, "advertising").enabled)
        with self.assertRaisesRegex(RuleError, "infrastructure"):
            change_feature(game, "advertising", "enable")
        self.assertEqual(game.development_spend, spend)

    def test_subscriptions_respond_to_reliability_price_and_paid_terms(self):
        game = fixture()
        release(game, "premium")
        advance(game, TICKS_PER_DAY - game.tick)
        initial_subscribers = game.subscribers
        self.assertGreater(initial_subscribers, 0)
        self.assertLess(initial_subscribers, game.audience * 0.02)
        healthy = game.model_copy(deep=True)
        unreliable = game.model_copy(deep=True)
        expensive = game.model_copy(deep=True)
        change_product(
            expensive,
            product_settings(expensive).model_copy(update={"premium_price": 12}),
        )
        for state in (healthy, unreliable, expensive):
            state.tick += TERM_TICKS
        unreliable.premium_quality = 0.7
        self.assertGreater(
            update_subscriptions(healthy, 1, 0), update_subscriptions(unreliable, 1, 0)
        )
        self.assertGreater(healthy.subscribers, unreliable.subscribers)
        update_subscriptions(expensive, 1, 0)
        self.assertGreater(healthy.subscribers, expensive.subscribers)
        cash = game.subscription_cash
        revenue = game.subscription_revenue
        change_feature(game, "premium", "disable")
        advance(game, TICKS_PER_DAY)
        self.assertEqual(game.subscribers, initial_subscribers)
        self.assertEqual(game.subscription_cash, cash)
        self.assertGreater(game.subscription_revenue, revenue)
        game.tick = game.subscriptions[0].expires - 1
        advance(game, 1)
        self.assertEqual(game.subscribers, 0)
        self.assertEqual(game.subscription_cash, cash)

    def test_premium_sync_change_applies_to_new_terms_only(self):
        game = fixture()
        release(game, "premium")
        advance(game, TICKS_PER_DAY - game.tick)
        before = demand(game)["history"]
        change_product(
            game, product_settings(game).model_copy(update={"premium_fast_sync": False})
        )
        self.assertTrue(game.subscriptions[0].fast_sync)
        self.assertEqual(demand(game)["history"], before)
        advance(game, TICKS_PER_DAY)
        self.assertFalse(game.subscriptions[-1].fast_sync)
        self.assertTrue(game.subscriptions[0].fast_sync)

    def test_premium_media_changes_paid_upload_size_without_adding_requests(self):
        game = fixture()
        monitor(game, "api")
        release(game, "images")
        enabled = product_settings(game).model_copy(
            update={"premium_high_quality_media": True}
        )
        with self.assertRaisesRegex(RuleError, "Release the feature"):
            change_product(game, enabled)

        release(game, "premium")
        game.tick = TICKS_PER_DAY
        game.premium_quality = 0.97
        standard = game.model_copy(deep=True)
        update_subscriptions(standard, 1, game.audience)
        change_product(game, enabled)
        update_subscriptions(game, 1, game.audience)
        self.assertGreater(game.subscribers, standard.subscribers)
        self.assertTrue(game.subscriptions[-1].high_quality_media)
        self.assertGreater(
            view(game, datetime.now(UTC)).economy.premium_satisfaction,
            view(standard, datetime.now(UTC)).economy.premium_satisfaction,
        )

        # Compare the same audience and paid cohort at the same instant.
        standard.subscriptions = [
            term.model_copy(update={"high_quality_media": False})
            for term in game.subscriptions
        ]
        before = evaluate(standard)
        after = evaluate(game)
        self.assertEqual(after.snapshot.demand, before.snapshot.demand)
        self.assertGreater(after.storage["db"], before.storage["db"])
        self.assertGreater(
            after.snapshot.components["api"].utilization["Network"],
            before.snapshot.components["api"].utilization["Network"],
        )

        change_product(
            game, enabled.model_copy(update={"premium_high_quality_media": False})
        )
        self.assertEqual(evaluate(game).snapshot, after.snapshot)
        game.tick = 2 * TICKS_PER_DAY
        update_subscriptions(game, 1, game.audience)
        self.assertTrue(game.subscriptions[0].high_quality_media)
        self.assertFalse(game.subscriptions[-1].high_quality_media)
        game.tick = game.subscriptions[0].expires
        update_subscriptions(game, 1, game.audience)
        self.assertFalse(any(term.high_quality_media for term in game.subscriptions))

    def test_cloud_media_quota_limits_new_writes_for_each_plan(self):
        game = fixture()
        game.released.extend(("images", "voice", "files", "premium"))
        component(game, "api").config.update(
            cpu=16, memory=32, network=250, connections=5000, concurrency=200
        )
        component(game, "db").config.update(
            cpu=16, memory=32, disk="NVMe", connections=1200, storage=500
        )
        game.subscriptions = [
            SubscriptionTerm(
                expires=TERM_TICKS, subscribers=game.audience / 4, price=4,
                media_quota_gb="unlimited", media_storage_gb=21,
            )
        ]
        game.free_media_storage_gb = 63
        game.storage["db"] = 86
        baseline = evaluate(game)
        change_product(game, product_settings(game).model_copy(update={"media_quota_gb": 0.01}))
        limited = evaluate(game)
        for op in ("upload", "voice", "files"):
            self.assertAlmostEqual(limited.snapshot.demand[op], baseline.snapshot.demand[op] / 4)
        self.assertEqual(limited.snapshot.demand["send"], baseline.snapshot.demand["send"])
        self.assertEqual(limited.media_storage[0], 63)
        self.assertGreater(limited.media_storage[1], 21)
        self.assertGreater(limited.storage["db"], game.storage["db"])
        self.assertLess(limited.storage["db"], baseline.storage["db"])
        self.assertEqual(game.subscriptions[0].media_storage_gb, 21)

        game.subscriptions[0].media_quota_gb = 0.02
        game.subscriptions[0].media_storage_gb = 41.999
        remaining = evaluate(game, load_scale=2)
        self.assertAlmostEqual(remaining.media_storage[1], 42)
        game.subscriptions[0].media_storage_gb = 42
        full = evaluate(game)
        self.assertTrue(all(full.snapshot.demand[op] == 0 for op in ("upload", "voice", "files")))
        self.assertEqual(full.snapshot.metrics.errors, 0)
        self.assertEqual(full.media_storage, (63, 42))

    def test_cloud_media_benefits_are_booked_at_checkout_and_storage_survives_renewal(self):
        game = fixture()
        product = product_settings(game).model_copy(
            update={"media_quota_gb": 0.01, "premium_media_quota_gb": "unlimited"}
        )
        with self.assertRaisesRegex(RuleError, "Release the feature"):
            change_product(game, product)
        game.released.extend(("images", "premium"))
        game.free_media_storage_gb = 80
        change_product(game, product)
        game.tick = TICKS_PER_DAY
        update_subscriptions(game, 1, game.audience)
        first = game.subscriptions[0]
        self.assertEqual(first.media_quota_gb, "unlimited")
        self.assertGreater(first.media_storage_gb, 0)
        self.assertAlmostEqual(game.free_media_storage_gb + first.media_storage_gb, 80)

        change_product(game, product.model_copy(update={"premium_media_quota_gb": 0.05}))
        self.assertEqual(first.media_quota_gb, "unlimited")
        game.tick = first.expires
        update_subscriptions(game, 1, game.audience)
        self.assertEqual(game.subscriptions[0].media_quota_gb, 0.05)
        self.assertAlmostEqual(
            game.free_media_storage_gb + sum(t.media_storage_gb for t in game.subscriptions), 80
        )

    def test_disabling_preserves_development_and_data_and_respects_dependencies(self):
        game = fixture()
        release(game, "groups")
        component(game, "db").config["search_index"] = "Enabled"
        release(game, "search")
        with self.assertRaisesRegex(RuleError, "dependent"):
            change_feature(game, "groups", "disable")
        stored = dict(game.storage)
        spend = game.development_spend
        change_feature(game, "search", "disable")
        change_feature(game, "groups", "disable")
        self.assertNotIn("groups", demand(game))
        self.assertNotIn("search", demand(game))
        self.assertEqual(game.storage, stored)
        with self.assertRaisesRegex(RuleError, "required product"):
            change_feature(game, "search", "enable")
        change_feature(game, "groups", "enable")
        change_feature(game, "search", "enable")
        self.assertGreater(demand(game)["search"], 0)
        self.assertEqual(game.development_spend, spend)

    def test_optional_settings_change_real_workload(self):
        game = fixture()
        monitor(game, "api")
        release(game, "images")
        before = evaluate(game)
        standard_sync = demand(game)["history"]
        change_product(
            game,
            product_settings(game).model_copy(
                update={
                    "sync_frequency": "relaxed",
                    "media_quality": "compressed",
                }
            ),
        )
        after = evaluate(game)
        self.assertAlmostEqual(demand(game)["history"], standard_sync * 0.75)
        self.assertLess(after.storage["db"], before.storage["db"])
        self.assertLess(
            after.snapshot.components["api"].utilization["Network"],
            before.snapshot.components["api"].utilization["Network"],
        )

    def test_regional_demand_is_smooth_deterministic_and_aggregates(self):
        game = fixture()
        region = REGIONS["europe"]
        self.assertLess(activity(region, 2 * 60), activity(region, 20 * 60) / 2)
        samples = [activity(region, minute) for minute in range(0, 8 * 1440, 10)]
        self.assertLess(max(abs(a - b) for a, b in pairwise(samples)), 0.06)
        game.north_america_audience = game.audience / 2
        snapshot = evaluate(game, overview=True).snapshot
        self.assertAlmostEqual(
            snapshot.metrics.rps,
            sum(region.requests for region in snapshot.demand_overview.regions),
        )
        self.assertEqual(
            snapshot,
            evaluate(
                Game.model_validate_json(game.model_dump_json()), overview=True
            ).snapshot,
        )
        add_event(
            game, "spike", "Activity spike", "Above baseline.", "info", 6, factor=1.27
        )
        spiking = evaluate(game, overview=True).snapshot
        self.assertAlmostEqual(spiking.metrics.rps, snapshot.metrics.rps * 1.27)
        self.assertAlmostEqual(spiking.demand_overview.event_lift, 0.27)
        self.assertEqual(
            snapshot.demand_overview.expected, spiking.demand_overview.expected
        )

    def test_restoring_a_legacy_ledger_and_reloading_a_paid_save(self):
        game = fixture()
        state = game.model_dump(mode="json")
        state.update(balance=10_075, revenue=100, operating=25)
        for key in (
            "product",
            "disabled_features",
            "subscriptions",
            "start_minute",
            "advertising_revenue",
            "subscription_revenue",
            "infrastructure_spend",
        ):
            state.pop(key)
        restored = Game.model_validate(state)
        result = view(restored, datetime.now(UTC)).economy
        self.assertEqual(result.revenue_sources.legacy, 100)
        self.assertEqual(result.operating_costs.legacy, 25)
        self.assertEqual(result.starting_capital, 10_000)
        self.assertEqual(restored.start_minute, 0)
        release(restored, "premium")
        advance(restored, TICKS_PER_DAY)
        copied = Game.model_validate_json(restored.model_dump_json())
        advance(restored, TICKS_PER_DAY)
        advance(copied, TICKS_PER_DAY)
        self.assertEqual(restored, copied)
