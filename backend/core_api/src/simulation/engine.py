from collections import defaultdict
from dataclasses import dataclass, field, replace
from math import exp, prod

from src.simulation.catalog import (
    FEATURES,
    MEDIA_OPERATIONS,
    MINUTES_PER_TICK,
    OPERATIONS,
    topic_accepts,
)
from src.simulation.database import WARNING, DatabaseLoad
from src.simulation.demand import active_incidents, workload
from src.simulation.engineering import (
    DOMAINS,
    data_targets,
    partition_weights,
    supports,
)
from src.simulation.models import (
    ComponentMetrics,
    Game,
    Metrics,
    MonitorCoverage,
    Snapshot,
    Topology,
    Traffic,
)
from src.simulation.topology import config, daily_cost, inspect_graph


@dataclass
class Batch:
    rate: float = 0
    latency_total: float = 0

    def add(self, rate: float, latency: float) -> None:
        self.rate += rate
        self.latency_total += rate * latency

    @property
    def latency(self) -> float:
        return self.latency_total / self.rate if self.rate else 0


@dataclass
class Evaluation:
    snapshot: Snapshot
    queues: dict[str, float] = field(default_factory=dict)
    storage: dict[str, float] = field(default_factory=dict)
    media_storage: tuple[float, ...] = ()
    replication: dict[str, float] = field(default_factory=dict)
    daily_active_users: float = 0
    ad_impressions_per_second: float = 0
    ad_value_per_impression: float = 0
    regional_ad_rates: dict[str, float] = field(default_factory=dict)


def demand(
    game: Game, audience: float | None = None, boost: float = 0
) -> dict[str, float]:
    return workload(game, audience, boost).operations


def evaluate(
    game: Game,
    topology: Topology | None = None,
    *,
    audience: float | None = None,
    boost: float = 0,
    overview: bool = False,
    load_scale: float = 1,
) -> Evaluation:
    topology = topology or game.production
    graph = inspect_graph(topology)
    activity = workload(game, audience, boost, overview=overview, load_scale=load_scale)
    workloads = {key: rate * load_scale for key, rate in activity.operations.items()}
    media = activity.media
    population = game.audience if audience is None else audience
    operations = {
        key: {
            **operation,
            "cpu": operation["cpu"] * media.cpu_factor,
            "mb": operation["mb"] * media.size_factor,
            "storage": operation["storage"] * media.size_factor,
        }
        if key in MEDIA_OPERATIONS
        else operation
        for key, operation in OPERATIONS.items()
    }
    requested = sum(workloads.values())
    settings = {node.id: config(node) for node in topology.nodes}
    for node in topology.nodes:
        cfg = settings[node.id]
        if cfg.get("autoscale") == "Enabled":
            state = game.autoscaling.get(node.id)
            cfg["instances"] = min(
                cfg["max_instances"],
                max(
                    cfg["min_instances"],
                    state.instances if state else cfg["min_instances"],
                ),
            )
    enforced = {
        FEATURES[key]["operation"]: FEATURES[key]["infrastructure"]
        for key in game.infrastructure_releases
        if key in game.enabled_features
    }
    events = list(active_incidents(game))
    factors = defaultdict(lambda: 1.0)
    failures = defaultdict(int)
    for event in events:
        if event.target and event.kind == "failure":
            failures[event.target] += 1
        elif event.target and event.kind == "degradation":
            factors[event.target] *= event.factor

    if game.migration:
        for n in game.production.nodes:
            if n.kind == "database":
                factors[n.id] *= 0.9

    # A cohort is an operation and its originating API. Cohorts merge at each node,
    # keeping the calculation proportional to the graph rather than the request count.
    incoming: dict[str, dict[tuple[str, str], Batch]] = defaultdict(dict)
    edges: dict[tuple[str, str], float] = defaultdict(float)
    edge_operations: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    components: dict[str, ComponentMetrics] = {}
    completed: dict[tuple[str, str], Batch] = {}
    queues = {}
    storage = dict(game.storage)
    media_written = 0.0
    replication = {}
    committed_writes: dict[str, float] = defaultdict(float)
    identity_routes = {}
    identity_sent = defaultdict(float)
    shard_shares = {}
    routed_partitions: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    rejected = 0.0
    seconds = MINUTES_PER_TICK * 60

    def add(batches: dict, key: tuple, rate: float, latency: float) -> None:
        if rate > 0:
            batches.setdefault(key, Batch()).add(rate, latency)

    def forward(
        source: str,
        targets: list[str],
        key: tuple,
        rate: float,
        latency: float,
        weights: list[float] | None = None,
    ) -> None:
        if not targets:
            return
        weights = weights or [1.0] * len(targets)
        total = sum(weights)
        if total == 0:
            return
        for target, weight in zip(targets, weights):
            share = rate * weight / total
            add(incoming[target], key, share, latency)
            edges[source, target] += share
            edge_operations[source, target][key[0]] += share

    def report(
        node_id: str,
        rate: float,
        accepted: float,
        latency: float,
        usage: dict,
        *,
        failed: bool = False,
        **details,
    ) -> None:
        maximum = max(usage.values(), default=0)
        status = "healthy"
        if failed:
            status = "failed"
        elif maximum > 1.0 or (rate and accepted < rate * 0.97):
            status = "overloaded"
        elif maximum >= WARNING:
            status = "warning"
        elif not rate:
            status = "idle"
        components[node_id] = ComponentMetrics(
            status=status,
            rps=rate,
            throughput=accepted,
            latency=latency,
            utilization={name: min(usage, 99) for name, usage in usage.items()},
            **details,
        )

    primary_for = {
        node.id: next(iter(graph.primaries(node.id)), None)
        for node in topology.nodes
        if node.kind == "replica"
    }

    followers: dict[str, int] = defaultdict(int)
    for node_id, primary in primary_for.items():
        if primary and graph.nodes[node_id].kind == "replica" and not failures[node_id]:
            followers[primary] += 1

    router_shards = {
        node.id: {
            primary
            for primary in graph.primaries(node.id)
            if settings[primary]["domain"] == settings[node.id]["domain"]
        }
        for node in topology.nodes
        if node.kind == "shard_router"
    }

    def read_targets(source: str, primary: str) -> list[str]:
        return [
            target
            for target in graph.targets[source]
            if target == primary
            or (
                graph.nodes[target].kind == "replica"
                and primary_for[target] == primary
                and not failures[target]
            )
            or primary in router_shards.get(target, ())
        ]

    def forward_partition(
        source: str,
        targets: list[str],
        key: tuple[str, str],
        primary: str,
        rate: float,
        latency: float,
    ) -> None:
        op, origin = key
        for target in targets:
            if graph.nodes[target].kind in {"shard_router", "cache"}:
                partitions = routed_partitions[target, op, origin]
                partitions[primary] = partitions.get(primary, 0) + rate / len(targets)
        forward(source, targets, key, rate, latency)

    def route_data(
        api: str,
        key: tuple[str, str],
        rate: float,
        latency: float,
        *,
        reads: bool = False,
    ) -> None:
        op, _ = key
        primaries = data_targets(graph, api, op)
        if not primaries:
            return
        routes = graph.primary_routes(api)
        weights = (
            partition_weights(DOMAINS[key[0]], primaries)
            if len(primaries) > 1
            else [1.0]
        )
        for primary, weight in zip(primaries, weights):
            if len(primaries) > 1:
                shard_shares[primary] = weight
            partition_rate = rate * weight
            partition_latency = latency + (
                4 + len(primaries) if len(primaries) > 1 else 0
            )
            if reads:
                caches = [
                    target
                    for target in graph.targets[api]
                    if graph.nodes[target].kind == "cache"
                    and (settings[target]["scope"] == "All reads" or op == "history")
                    and read_targets(target, primary)
                ]
                if caches:
                    forward_partition(
                        api, caches, key, primary, partition_rate, partition_latency
                    )
                    continue
            if (
                "search_index" in enforced.get(op, ())
                and settings[primary].get("search_index") != "Enabled"
            ):
                continue
            destinations = read_targets(api, primary) if reads else [routes[primary]]
            forward_partition(
                api, destinations, key, primary, partition_rate, partition_latency
            )

    for op, rate in workloads.items():
        add(incoming["traffic"], (op, ""), rate, 18)

    # Process primaries before replicas so replicas can replay this step's writes.
    data_order = {"database": 1, "replica": 2}
    for node_id in sorted(
        graph.order, key=lambda item: data_order.get(graph.nodes[item].kind, 0)
    ):
        node = graph.nodes[node_id]
        kind = node.kind
        if kind in {"queue", "worker", "monitor"}:
            continue
        cfg = settings[node_id]
        targets = [
            target
            for target in graph.targets[node_id]
            if graph.relationships[node_id, target]
            in {"request", "queries", "reads", "cache"}
        ]
        cohorts = incoming[node_id]
        rate = sum(batch.rate for batch in cohorts.values())

        def load(
            field: str,
            cohorts: dict[tuple[str, str], Batch] = cohorts,
            indexed: bool = cfg.get("search_index") == "Enabled",
            query_primary: str | None = node_id
            if kind == "database"
            else primary_for.get(node_id),
        ) -> float:
            optimized = bool(
                query_primary
                and settings[query_primary].get("query_plan") == "History indexes"
            )
            return sum(
                (0.35 if field == "read" and key[0] == "search" and indexed else 1)
                * (
                    0.65
                    if optimized and field == "read" and key[0] == "history"
                    else 0.8
                    if optimized and field == "read" and key[0] == "conversations"
                    else 1.1
                    if optimized and field == "write" and key[0] in {"send", "groups"}
                    else 1
                )
                * operations[key[0]][field]
                * batch.rate
                for key, batch in cohorts.items()
            )

        instances = max(0, cfg.get("instances", 1) - failures[node_id])
        factor = factors[node_id]
        capacity = instances * factor
        usage: dict[str, float] = {}
        base = 0.0
        details = {}

        if kind == "api":
            overhead = 1.06 if cfg["role"] != "Universal" else 1
            overhead += 0.03 * max(
                0,
                max(
                    (len(data_targets(graph, node_id, op)) for op, _ in cohorts),
                    default=1,
                )
                - 1,
            )
            usage = {
                "CPU": load("cpu") * overhead / (cfg["cpu"] * 77),
                "RAM": (0.9 * instances + load("connections") * 0.0035) / cfg["memory"],
                "Network": load("mb") * overhead / cfg["network"],
                "Connections": load("connections") / cfg["connections"],
                "Concurrency": (load("cpu") * 0.17) / cfg["concurrency"],
            }
            details["active_instances"] = instances
            details["service_role"] = cfg["role"]
            details["autoscaling"] = (
                "Enabled" if cfg["autoscale"] == "Enabled" else None
            )
            details["daily_cost"] = (
                daily_cost(node) / config(node)["instances"] * cfg["instances"]
            )
            base = 12
        elif kind == "balancer":
            usage = {
                "Connections": load("connections") / cfg["connections"],
                "Network": load("mb") / cfg["network"],
            }
            base = 3
        elif kind == "shard_router":
            usage = {"Routing capacity": rate / cfg["routing_capacity"]}
            details["data_domain"] = cfg["domain"]
            base = 3
        elif kind in {"database", "replica"}:
            primary = primary_for[node_id] if kind == "replica" else None
            pending = 0.0
            if kind == "replica":
                if not primary:
                    capacity = 0
                else:
                    pending = (
                        game.replication.get(node_id, 0)
                        + committed_writes[primary] * seconds
                    )
            database = DatabaseLoad(
                cfg=cfg,
                reads=load("read"),
                writes=load("write") if kind == "database" else pending / seconds,
                factor=capacity,
                followers=followers[node_id],
                primary=kind == "database",
                stored=game.storage.get(node_id, 0),
                storage_rate=load("storage") if kind == "database" else 0,
            )
            if kind == "database":
                details["storage_used"] = database.stored
            details["data_domain"] = cfg.get(
                "domain", settings.get(primary, {}).get("domain", "Shared")
            )
            details["partition_share"] = shard_shares.get(node_id)
            base = 21
        elif kind == "cache":
            usage = {"CPU": rate / (160 + cfg["memory"] * 35)}
            base = 4

        if kind in data_order:
            usage = database.utilization()
        else:
            usage = {
                key: value
                / (
                    max(instances, 1)
                    if key == "RAM" and kind == "api"
                    else max(capacity, 0.001)
                )
                for key, value in usage.items()
            }
        pressure = max((v for key, v in usage.items() if key != "Storage"), default=0)
        share = min(1.0, 1 / max(pressure, 1)) if capacity else 0
        latency = base * (1 + 2.2 * min(pressure, 1.8) ** 3)
        limited_rate = 0.0
        if kind == "limiter":
            scoped = sum(
                batch.rate
                for (op, _), batch in cohorts.items()
                if applies(cfg["scope"], op)
            )
            limit = (cfg["limit"] + cfg["burst"]) / cfg["window"]
            usage["Rate limit"] = scoped / limit
            limited_rate = min(1, limit / scoped) if scoped else 1
            base = latency = 2

        write_share = 1.0
        if kind == "database":
            free = max(0, cfg["storage"] - database.stored)
            additional = database.storage_rate * share * seconds
            write_share = min(1, free / additional) if additional else float(free > 0)

        if kind in data_order:
            replayed = 0.0
            if kind == "replica" and primary:
                replayed = database.writes * share
                remaining = max(0.0, pending - replayed * seconds)
                replication[node_id] = remaining
                if replayed or not remaining:
                    details["replication_lag"] = round(
                        0.2 + (remaining / replayed if replayed else 0), 2
                    )
            telemetry = database.telemetry(usage, replayed)
            telemetry.replication_backlog = replication.get(node_id, 0.0)
            if kind == "database" and telemetry.diagnostic:
                # Only suggest offloading actual eligible traffic from this primary.
                eligible = sum(
                    operations[op]["read"] * batch.rate
                    for (op, _), batch in cohorts.items()
                    if not operations[op]["write"]
                    and "search_index" not in enforced.get(op, ())
                )
                without_eligible = replace(
                    database, reads=max(0, database.reads - eligible)
                )
                before = pressure
                after = max(
                    v
                    for key, v in without_eligible.utilization().items()
                    if key != "Storage"
                )
                telemetry.diagnostic.read_options = (
                    eligible > 0
                    and before >= WARNING
                    and (
                        after < before - 0.01
                        or without_eligible.sustainable_writes()
                        > (telemetry.write_capacity or 0) + 0.01
                    )
                )
            details["database"] = telemetry

        accepted_total = 0.0
        cache_hits = 0.0
        for (op, origin), batch in cohorts.items():
            key = (op, origin)
            operation = operations[op]
            accepted = batch.rate * share
            total_latency = batch.latency + latency
            if kind == "limiter" and applies(cfg["scope"], op):
                accepted *= limited_rate
                rejected += batch.rate * share * (1 - limited_rate)
            if kind == "database" and operation["write"]:
                accepted *= write_share
            if kind == "replica" and operation["write"]:
                accepted = 0
            accepted_total += accepted

            if kind in {"database", "replica"}:
                add(completed, key, accepted, total_latency)
                if kind == "database":
                    committed_writes[node_id] += accepted * operation["write"]
                    written = accepted * operation["storage"] * seconds
                    storage[node_id] = storage.get(node_id, 0) + written
                    if op in MEDIA_OPERATIONS:
                        media_written += written
            elif kind == "api":
                key = (op, node_id)
                if not supports(node, op):
                    continue
                if cfg["role"] not in {"Universal", "Accounts"}:
                    accounts = [
                        t
                        for t in graph.targets[node_id]
                        if graph.relationships[node_id, t] == "identity"
                    ]
                    identity_routes[node_id] = accounts
                    for account in accounts:
                        identity_sent[account] += accepted * 0.02 / len(accounts)
                    forward(
                        node_id, accounts, ("identity", node_id), accepted * 0.02, 0
                    )
                if operation["write"] or "search_index" in enforced.get(op, ()):
                    route_data(node_id, key, accepted, total_latency)
                elif operation["read"]:
                    route_data(node_id, key, accepted, total_latency, reads=True)
                else:
                    add(completed, key, accepted, total_latency)
            elif kind == "cache":
                working_set = max(1, population / 6000)
                hit = min(
                    0.91,
                    (0.25 + 0.65 * (1 - exp(-cfg["ttl"] / 150)))
                    * min(1, cfg["memory"] / working_set)
                    * (1.10 if cfg["policy"] == "LFU" else 1),
                )
                cache_hits += accepted * hit
                add(completed, key, accepted * hit, total_latency)
                for primary, rate in routed_partitions[node_id, op, origin].items():
                    forward_partition(
                        node_id,
                        read_targets(node_id, primary),
                        key,
                        primary,
                        rate * share * (1 - hit),
                        total_latency,
                    )
            elif kind == "shard_router":
                for primary, rate in routed_partitions[node_id, op, origin].items():
                    forward(node_id, [primary], key, rate * share, total_latency)
            elif kind == "balancer":
                routed = [
                    target
                    for target in targets
                    if supports(graph.nodes[target], op)
                    and (
                        cfg["health"] == "Disabled"
                        or settings[target]["instances"] > failures[target]
                    )
                ]
                weights = (
                    [
                        settings[target]["cpu"]
                        * max(1, settings[target]["instances"] - failures[target])
                        for target in routed
                    ]
                    if cfg["algorithm"] == "Weighted capacity"
                    else None
                )
                forward(node_id, routed, key, accepted, total_latency, weights)
            else:
                eligible = [
                    t
                    for t in targets
                    if graph.nodes[t].kind != "api" or supports(graph.nodes[t], op)
                ]
                forward(node_id, eligible, key, accepted, total_latency)

        if kind == "cache":
            details["cache_hit"] = cache_hits / accepted_total if accepted_total else 0
        details["operations"] = {
            op: sum(b.rate for (name, _), b in cohorts.items() if name == op)
            for op, _ in cohorts
        }
        report(
            node_id,
            rate,
            accepted_total,
            latency,
            usage,
            failed=not instances,
            **details,
        )

    for key, batch in list(completed.items()):
        op, origin = key
        if op == "identity":
            continue
        if origin in identity_routes:
            accounts = identity_routes[origin]
            shares, latencies = [], []
            for account in accounts:
                replies = [
                    b
                    for (name, api), b in completed.items()
                    if name == "identity" and api == account
                ]
                total = sum(b.rate for b in replies)
                shares.append(min(1, total / max(identity_sent[account], 1e-12)))
                latencies.append(
                    sum(b.latency_total for b in replies) / max(total, 1e-12)
                )
            original_latency = batch.latency
            batch.rate *= sum(shares) / len(shares) if shares else 0
            batch.latency_total = batch.rate * (
                original_latency + (sum(latencies) / len(latencies) if latencies else 0)
            )
    completed = {key: batch for key, batch in completed.items() if key[0] != "identity"}

    # Background work is generated only by requests that reached a successful terminal.
    jobs: dict[str, float] = defaultdict(float)
    async_routes: dict[tuple[str, str], tuple[list[str], list[str]]] = {}
    queued_operations: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    missing_queues = set()
    for key, batch in completed.items():
        op, origin = key
        targets = [
            target
            for target in graph.targets[origin]
            if graph.nodes[target].kind == "queue"
            and topic_accepts(settings[target]["topic"], op)
        ]
        if "background_jobs" in enforced.get(op, ()):
            if not targets:
                missing_queues.add(key)
            # Prefer queues with workers when one of the links has no consumer.
            targets = [
                queue
                for queue in targets
                if any(
                    graph.relationships[queue, worker] == "jobs"
                    for worker in graph.targets[queue]
                )
            ] or targets
        if OPERATIONS[op]["jobs"] and targets:
            shared = [
                target
                for target in targets
                if settings[target]["delivery"] == "Distribute"
            ]
            broadcast = [
                target
                for target in targets
                if settings[target]["delivery"] == "Broadcast"
            ]
            async_routes[key] = shared, broadcast
            for target in targets:
                copies = len(shared) if target in shared else 1
                rate = batch.rate * OPERATIONS[op]["jobs"] / copies
                jobs[target] += rate
                edges[origin, target] += rate
                edge_operations[origin, target][op] += rate
                queued_operations[target][op] += rate

    dropped: dict[str, float] = {}
    worker_load: dict[str, float] = defaultdict(float)
    worker_capacity = {
        node.id: max(0, settings[node.id]["instances"] - failures[node.id])
        * factors[node.id]
        * min(
            settings[node.id]["cpu"] * 10,
            settings[node.id]["concurrency"] * 3,
            settings[node.id]["memory"] * 10,
        )
        for node in topology.nodes
        if node.kind == "worker"
    }
    worker_consumers = {
        worker: max(
            1,
            sum(
                worker in graph.targets[node.id] and node.id in graph.reachable
                for node in topology.nodes
                if node.kind == "queue"
            ),
        )
        for worker in worker_capacity
    }
    for node in topology.nodes:
        if node.kind != "queue":
            continue
        cfg = settings[node.id]
        workers = [
            target for target in graph.targets[node.id] if target in worker_capacity
        ]
        shares = [
            worker_capacity[worker] / worker_consumers[worker] for worker in workers
        ]
        capacity = sum(shares)
        previous = game.queues.get(node.id, 0)
        expired = previous * MINUTES_PER_TICK / cfg["retention"]
        backlog = previous - expired
        if failures[node.id]:
            capacity = 0
        rate = jobs[node.id]
        volume = backlog + rate * seconds
        processed = min(volume, capacity * seconds)
        for worker, share in zip(workers, shares):
            worker_rate = (processed / seconds) * share / capacity if capacity else 0
            worker_load[worker] += worker_rate
            edges[node.id, worker] += worker_rate
            current_share = min(1, rate * seconds / volume) if volume else 0
            for operation, arrival in queued_operations[node.id].items():
                edge_operations[node.id, worker][operation] += (
                    worker_rate * current_share * arrival / rate
                )
        pending = max(0, volume - processed)
        dropped[node.id] = (
            min(1, max(0, pending - cfg["capacity"]) / (rate * seconds)) if rate else 0
        )
        queues[node.id] = min(cfg["capacity"], pending)
        report(
            node.id,
            rate,
            rate * (1 - dropped[node.id]),
            0,
            {"Queue capacity": pending / cfg["capacity"]},
            backlog=queues[node.id],
            queue_wait_minutes=queues[node.id] / capacity / 60 if capacity else None,
            jobs_dropped=rate * seconds * dropped[node.id],
            jobs_expired=expired,
            failed=bool(failures[node.id]),
        )
    for worker, capacity in worker_capacity.items():
        rate = worker_load[worker]
        instances = settings[worker]["instances"] - failures[worker]
        report(
            worker,
            rate,
            rate,
            0,
            {
                "CPU": rate
                / max(instances * factors[worker] * settings[worker]["cpu"] * 10, 1),
                "Concurrency": rate
                / max(
                    instances * factors[worker] * settings[worker]["concurrency"] * 3, 1
                ),
                "RAM": rate
                / max(instances * factors[worker] * settings[worker]["memory"] * 10, 1),
            },
            failed=instances <= 0,
            active_instances=max(0, instances),
        )

    success = Batch()
    latency_cohorts = []
    ad_success = 0.0
    service_success = defaultdict(Batch)
    service_operations = defaultdict(lambda: defaultdict(float))
    for key, batch in completed.items():
        if key in missing_queues:
            continue
        shared, broadcast = async_routes.get(key, ([], []))
        shared_success = (
            1 - sum(dropped[target] for target in shared) / len(shared) if shared else 1
        )
        served = (
            batch.rate
            * shared_success
            * prod(1 - dropped[target] for target in broadcast)
        )
        success.add(served, batch.latency)
        service_success[key[1]].add(served, batch.latency)
        service_operations[key[1]][key[0]] += served
        if served > 0:
            latency_cohorts.append((batch.latency, served))
        if key[0] == "ad":
            ad_success += served

    monitors = {}
    visible = set()
    for node in topology.nodes:
        if node.kind != "monitor":
            continue
        linked = sorted(
            source
            for (source, target), kind in graph.relationships.items()
            if target == node.id and kind == "telemetry"
        )
        cfg = settings[node.id]
        capacity = int(cfg["slots"])
        failed = bool(failures[node.id])
        history = (
            cfg["detail"] == "Service history"
            and capacity >= 3
            and bool(linked)
            and not failed
        )
        available_slots = 0 if failed else max(0, capacity - (2 if history else 0))
        covered, dropped = linked[:available_slots], linked[available_slots:]
        visible.update(covered)
        monitors[node.id] = MonitorCoverage(
            capacity=capacity,
            history=history,
            covered=covered,
            dropped=dropped,
            failed=failed,
        )
    rollout = 1.0
    for event in events:
        if event.kind == "deploy":
            rollout *= event.factor
    errors = max(0, requested - success.rate * rollout)
    if errors < 1e-9:
        errors = 0
    errors = min(requested, max(errors, rejected))
    throughput = requested - errors
    available = throughput / requested if requested else 1
    p95 = None
    if throughput:
        cumulative = 0.0
        for latency, served in sorted(latency_cohorts):
            cumulative += served
            if cumulative >= success.rate * 0.95:
                p95 = latency
                break
    for node_id, metric in components.items():
        if graph.nodes[node_id].kind == "api":
            metric.completed_operations = dict(service_operations[node_id])
            metric.service_errors = max(
                0,
                sum(v for op, v in metric.operations.items() if op != "identity")
                - service_success[node_id].rate * rollout,
            )
            metric.service_latency = service_success[node_id].latency
    snapshot = Snapshot(
        metrics=Metrics(
            rps=requested,
            throughput=throughput,
            availability=available,
            latency=success.latency if success.rate else (2000 if requested else 0),
            errors=errors,
            p95_latency=p95,
            rejected=rejected,
        ),
        components={
            key: metric for key, metric in components.items() if key in visible
        },
        traffic=[
            Traffic(
                source=source,
                target=target,
                rps=rate,
                operations=edge_operations.get((source, target), {}),
            )
            for (source, target), rate in edges.items()
            if source in visible or target in visible or source == "traffic"
        ],
        demand=workloads,
        demand_overview=activity.overview,
        monitored=any(monitor.history for monitor in monitors.values()),
        monitors=monitors,
    )
    ad_share = ad_success * rollout / workloads["ad"] if workloads.get("ad") else 0
    return Evaluation(
        snapshot=snapshot,
        queues=queues,
        storage=storage,
        media_storage=tuple(
            stored + media_written * media.storage_shares[index]
            if media.storage_shares
            else stored
            for index, stored in enumerate(media.stored)
        ),
        replication=replication,
        daily_active_users=activity.active_users,
        ad_impressions_per_second=ad_success * rollout,
        ad_value_per_impression=activity.ad_value_per_impression,
        regional_ad_rates={
            key: rate * ad_share for key, rate in activity.regional_ad_rates.items()
        },
    )


def applies(scope: str, operation: str) -> bool:
    return (
        scope == "All requests"
        or (scope == "Writes" and OPERATIONS[operation]["write"] > 0)
        or (scope == "Media" and OPERATIONS[operation]["mb"] >= 0.4)
    )
