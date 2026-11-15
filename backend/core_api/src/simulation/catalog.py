from src.simulation.models import Kind, Setting

MINUTES_PER_TICK = 10
TICKS_PER_DAY = 24 * 60 // MINUTES_PER_TICK
DAYS_PER_MONTH = 30
START_MINUTE_UTC = 8 * 60
SECONDS_PER_TICK = 2
HISTORY_LIMIT = TICKS_PER_DAY


def number(
    label: str, default: float, minimum: float, maximum: float, step: float = 1
) -> dict:
    return {
        "label": label,
        "default": default,
        "min": minimum,
        "max": maximum,
        "step": step,
    }


def choice(label: str, default: str, *options: str) -> dict:
    return {"label": label, "default": default, "options": list(options)}


# Disk throughput multiplier and surcharge as a fraction of base daily cost.
DATABASE_DISKS = {"SSD": (1.0, 0.0), "NVMe": (1.45, 0.35), "NVMe array": (4.5, 2.4)}


COMPONENTS: dict[Kind, dict] = {
    "source": {
        "name": "Traffic source",
        "category": "Traffic",
        "monthly": 0,
        "fields": {},
        "description": "Generates requests from active users, enabled features and audience activity.",
    },
    "balancer": {
        "name": "Load balancer",
        "category": "Traffic",
        "monthly": 120,
        "fields": {
            "algorithm": choice(
                "Routing strategy", "Round robin", "Round robin", "Weighted capacity"
            ),
            "health": choice("Health checks", "Enabled", "Enabled", "Disabled"),
            "connections": number("Connection capacity", 4000, 100, 100000, 100),
            "network": number("Network (MB/s)", 80, 5, 2000, 5),
        },
        "description": "Splits traffic across API targets. Weighted capacity favors larger servers. Health checks skip failed targets.",
    },
    "api": {
        "name": "API server",
        "category": "Compute",
        "monthly": 180,
        "fields": {
            "role": choice(
                "API service role",
                "Universal",
                "Universal",
                "Messages",
                "Accounts",
                "Media",
                "Search",
            ),
            "autoscale": choice("Autoscaling", "Disabled", "Disabled", "Enabled"),
            "min_instances": number("Minimum instances", 1, 1, 24),
            "max_instances": number("Maximum instances", 4, 1, 24),
            "target_utilization": number("Utilization target (%)", 65, 40, 90, 5),
            "instances": number("Instances", 1, 1, 24),
            "cpu": number("vCPU per instance", 2, 1, 32),
            "memory": number("RAM per instance (GB)", 4, 1, 128),
            "connections": number("Connections per instance", 1100, 100, 25000, 100),
            "network": number("Network per instance (MB/s)", 30, 5, 1000, 5),
            "concurrency": number("Concurrency per instance", 40, 5, 800, 5),
            "recovery": choice(
                "Hardware recovery", "Standard", "Standard", "Managed replacement"
            ),
        },
        "description": "Executes application work and routes requests to data services. Instances share the same downstream dependencies.",
    },
    "database": {
        "name": "Database",
        "category": "Data",
        "monthly": 360,
        "fields": {
            "domain": choice(
                "Data domain",
                "Shared",
                "Shared",
                "Messages",
                "Accounts",
                "Media",
                "Search",
            ),
            "partition": choice(
                "Dataset membership", "Independent", "Independent", "Partition"
            ),
            "query_plan": choice(
                "Query plan", "Standard", "Standard", "History indexes"
            ),
            "cpu": number("Database vCPU", 2, 1, 32),
            "memory": number("RAM (GB)", 8, 1, 128),
            "storage": number("Storage (GB)", 32, 4, 10000),
            "disk": choice("Storage type", "SSD", *DATABASE_DISKS),
            "connections": number("Connection pool limit", 350, 25, 10000, 25),
            "search_index": choice(
                "Message search index", "Disabled", "Disabled", "Enabled"
            ),
        },
        "description": "Serves persistent reads and writes. Throughput depends on CPU, memory, and disk. The connection pool limits admission.",
    },
    "replica": {
        "name": "Read replica",
        "category": "Data",
        "monthly": 240,
        "fields": {
            "cpu": number("Database vCPU", 2, 1, 16),
            "memory": number("RAM (GB)", 8, 1, 128),
            "disk": choice("Storage type", "SSD", *DATABASE_DISKS),
            "connections": number("Connection pool limit", 350, 25, 10000, 25),
        },
        "description": "Serves application reads. Subscribe to one primary database for replication. Reads can lag behind writes.",
    },
    "cache": {
        "name": "Cache",
        "category": "Data",
        "monthly": 150,
        "fields": {
            "memory": number("Capacity (GB)", 2, 1, 64),
            "ttl": number("TTL (seconds)", 120, 10, 3600, 10),
            "policy": choice("Eviction policy", "LRU", "LRU", "LFU"),
            "scope": choice(
                "Cacheable reads", "All reads", "All reads", "History only"
            ),
        },
        "description": "Serves repeated reads. On a miss, the cache uses its linked data sources or the API's data connections. Writes go directly to a primary database.",
    },
    "limiter": {
        "name": "Rate limiter",
        "category": "Traffic",
        "monthly": 90,
        "fields": {
            "limit": number("Requests per window", 130, 1, 100000),
            "window": number("Window (seconds)", 1, 1, 120),
            "burst": number("Burst allowance", 15, 0, 10000),
            "scope": choice(
                "Traffic scope", "All requests", "All requests", "Writes", "Media"
            ),
        },
        "description": "Rejects excess traffic in the selected scope to preserve capacity for other requests.",
    },
    "queue": {
        "name": "Queue",
        "category": "Compute",
        "monthly": 120,
        "fields": {
            "capacity": number("Capacity (jobs)", 30000, 100, 2_000_000, 100),
            "retention": number("Retention (minutes)", 60, 10, 1440, 10),
            "topic": choice(
                "Job topic",
                "All jobs",
                "All jobs",
                "Notifications",
                "Media processing",
                "Search jobs",
            ),
            "delivery": choice(
                "Delivery mode", "Distribute", "Distribute", "Broadcast"
            ),
        },
        "description": "Buffers background jobs such as notifications and media processing. Workers drain the backlog. When capacity is exhausted, new submissions fail.",
    },
    "worker": {
        "name": "Worker",
        "category": "Compute",
        "monthly": 180,
        "fields": {
            "instances": number("Instances", 1, 1, 24),
            "cpu": number("vCPU per instance", 2, 1, 32),
            "memory": number("RAM per instance (GB)", 4, 1, 128),
            "concurrency": number("Concurrency per instance", 10, 1, 200),
        },
        "description": "Consumes jobs from connected queues. Instances, CPU, RAM and concurrency limit processing speed. For example, workers can transcode voice messages after upload.",
    },
    "monitor": {
        "name": "Monitoring",
        "category": "Operations",
        "monthly": 90,
        "fields": {
            "slots": number("Collection slots", 8, 2, 32),
            "detail": choice(
                "Collection scope",
                "Linked components",
                "Linked components",
                "Service history",
            ),
        },
        "description": "Collects metrics from linked components. Each link uses one slot. Service history reserves two more slots.",
    },
}

COMPONENT_PRESETS = {
    "api": {
        "Small S1 · 1 vCPU / 2 GB": {"cpu": 1, "memory": 2},
        "Standard S2 · 2 vCPU / 4 GB": {"cpu": 2, "memory": 4},
        "Performance P4 · 4 vCPU / 8 GB": {"cpu": 4, "memory": 8},
        "Performance P8 · 8 vCPU / 16 GB": {"cpu": 8, "memory": 16},
    },
    "database": {
        "General purpose": {
            "cpu": 2,
            "memory": 8,
            "disk": "SSD",
            "storage": 32,
            "connections": 350,
        },
        "Compute optimized": {
            "cpu": 8,
            "memory": 16,
            "disk": "SSD",
            "storage": 64,
            "connections": 700,
        },
        "I/O optimized": {
            "cpu": 8,
            "memory": 16,
            "disk": "NVMe",
            "storage": 128,
            "connections": 700,
        },
    },
    "replica": {
        "General purpose": {"cpu": 2, "memory": 8, "disk": "SSD", "connections": 350},
        "High read capacity": {
            "cpu": 8,
            "memory": 32,
            "disk": "NVMe",
            "connections": 750,
        },
    },
    "cache": {
        "Small memory": {"memory": 2, "ttl": 120},
        "Large memory": {"memory": 16, "ttl": 300},
    },
    "queue": {
        "Standard": {"capacity": 30000, "retention": 60},
        "Large backlog": {"capacity": 150000, "retention": 120},
    },
    "worker": {
        "Standard": {"cpu": 2, "memory": 4, "concurrency": 10},
        "Compute optimized": {"cpu": 8, "memory": 8, "concurrency": 32},
    },
    "balancer": {
        "Standard": {"network": 80, "connections": 4000},
        "High traffic": {"network": 240, "connections": 12000},
    },
    "monitor": {
        "Basic": {"slots": 8, "detail": "Linked components"},
        "Service history": {"slots": 12, "detail": "Service history"},
        "High-volume telemetry": {"slots": 32, "detail": "Service history"},
    },
    "limiter": {
        "General admission": {
            "scope": "All requests",
            "limit": 130,
            "window": 1,
            "burst": 15,
        },
        "Protect writes": {"scope": "Writes", "limit": 62, "window": 1, "burst": 5},
    },
}

JOB_TOPICS = {
    "Notifications": {"send", "groups"},
    "Media processing": {"upload", "voice", "files"},
    "Search jobs": {"search"},
}


def topic_accepts(topic: str, operation: str) -> bool:
    return topic == "All jobs" or operation in JOB_TOPICS[topic]


SCENARIOS = {
    "messenger": {
        "name": "Messenger",
        "available": True,
        "description": "Messaging, chat history and persistent connections.",
        "activity": 1.0,
        "organic": 0.009,
        "operations": ["send", "history", "conversations", "auth", "connection"],
    },
    "social": {
        "name": "Social network",
        "available": False,
        "description": "Feeds, media uploads and advertising.",
        "activity": 1.2,
        "organic": 0.012,
        "operations": ["feed", "upload", "auth"],
    },
    "multiplayer": {
        "name": "Multiplayer game",
        "available": False,
        "description": "Real-time sessions and in-game purchases.",
        "activity": 1.4,
        "organic": 0.007,
        "operations": ["session", "connection", "auth"],
    },
    "education": {
        "name": "Educational platform",
        "available": False,
        "description": "Lessons, streaming and subscriptions.",
        "activity": 0.8,
        "organic": 0.008,
        "operations": ["lesson", "stream", "auth"],
    },
}


def operation(
    label: str,
    rate: float,
    cpu: float,
    *,
    read: float = 0,
    write: float = 0,
    mb: float = 0.007,
    connections: float = 1,
    jobs: float = 0,
    storage: float = 0,
) -> dict:
    return {
        "label": label,
        "rate": rate,
        "cpu": cpu,
        "read": read,
        "write": write,
        "mb": mb,
        "connections": connections,
        "jobs": jobs,
        "storage": storage,
    }


OPERATIONS = {
    "identity": operation("Identity checks", 0, 0.15, read=0.12, mb=0.002),
    "send": operation(
        "Send message", 0.0049, 1.0, write=1, jobs=0.2, storage=0.00000008
    ),
    "history": operation("Chat history", 0.0067, 1.1, read=1.8, mb=0.018),
    "conversations": operation("Conversation list", 0.0034, 0.75, read=1.1),
    "auth": operation("Authentication", 0.0009, 1.8, read=1, write=0.25),
    "connection": operation("Persistent connections", 0.0036, 0.25, connections=12),
    "groups": operation(
        "Group messages", 0.002, 1.5, read=0.4, write=1.4, jobs=0.65, storage=0.00000015
    ),
    "upload": operation(
        "Image uploads", 0.0007, 2.5, write=1.5, mb=1.3, jobs=2, storage=0.00012
    ),
    "voice": operation(
        "Voice messages", 0.0006, 1.6, write=1, mb=0.48, jobs=1, storage=0.00005
    ),
    "search": operation("Message search", 0.0015, 1.9, read=3.8, jobs=0.4),
    "files": operation(
        "File transfers", 0.00035, 1.6, write=1, mb=4.2, jobs=1.4, storage=0.00028
    ),
    "calls": operation("Voice calls", 0.00085, 2.2, mb=1.7, connections=42),
    "ad": operation("Ad delivery", 0, 0.65, mb=0.045),
    "feed": operation("Feed reads", 0.008, 1.1, read=3, mb=0.08),
    "session": operation("Session updates", 0.02, 0.7, connections=16),
    "lesson": operation("Lesson progress", 0.002, 1.2, read=1, write=1),
    "stream": operation("Video streams", 0.0009, 0.4, mb=3.5, connections=14),
}


def feature(
    name: str,
    cost: int,
    duration: int,
    appeal: float,
    operation_id: str | None,
    prereq: tuple = ("text",),
    requires: tuple = (),
    infrastructure: tuple[str, ...] = (),
) -> dict:
    return {
        "name": name,
        "cost": cost,
        "duration": duration,
        "appeal": appeal,
        "operation": operation_id,
        "prereq": prereq,
        "requires": requires,
        "infrastructure": infrastructure,
    }


FEATURES = {
    "text": feature("Text messaging", 0, 0, 0, None, (), infrastructure=("primary",)),
    "advertising": feature(
        "Advertising", 480, 12, 0, "ad", infrastructure=("primary",)
    ),
    "premium": feature(
        "Premium subscriptions", 720, 18, 0, None, infrastructure=("primary",)
    ),
    "groups": feature(
        "Group chats", 650, 12, 0.17, "groups", infrastructure=("primary",)
    ),
    "images": feature(
        "Image attachments",
        950,
        20,
        0.23,
        "upload",
        requires=("database",),
        infrastructure=("media_storage",),
    ),
    "voice": feature(
        "Voice messages",
        1200,
        24,
        0.18,
        "voice",
        ("images",),
        ("database",),
        infrastructure=("media_storage", "background_jobs"),
    ),
    "search": feature(
        "Message search",
        1600,
        28,
        0.24,
        "search",
        ("groups",),
        infrastructure=("search_index",),
    ),
    "files": feature(
        "File sharing",
        2000,
        36,
        0.22,
        "files",
        ("images",),
        ("queue", "worker"),
        infrastructure=("media_storage", "background_jobs"),
    ),
    "calls": feature(
        "Voice calls",
        3100,
        48,
        0.31,
        "calls",
        ("voice",),
        ("balancer",),
        infrastructure=("signaling",),
    ),
}

CAMPAIGNS = {
    "community": {
        "name": "Community campaign",
        "cost": 420,
        "duration": 18,
        "audience": 3200,
        "spike": 0.13,
        "description": "Gradual acquisition with a small increase in activity.",
    },
    "creator": {
        "name": "Creator partnership",
        "cost": 1150,
        "duration": 36,
        "audience": 9700,
        "spike": 0.25,
        "description": "Acquisition peaks during the promotion.",
    },
    "ads": {
        "name": "Advertising campaign",
        "cost": 2600,
        "duration": 54,
        "audience": 24000,
        "spike": 0.43,
        "description": "A sustained campaign with a concentrated traffic peak.",
    },
}

CONNECTIONS: dict[Kind, dict[Kind, str]] = {
    "source": {"api": "request", "balancer": "request", "limiter": "request"},
    "limiter": {"balancer": "request", "api": "request", "monitor": "telemetry"},
    "balancer": {"api": "request", "monitor": "telemetry"},
    "api": {
        "api": "identity",
        "database": "queries",
        "replica": "reads",
        "cache": "cache",
        "queue": "enqueue",
        "monitor": "telemetry",
    },
    "cache": {"database": "reads", "replica": "reads", "monitor": "telemetry"},
    "replica": {"database": "replication", "monitor": "telemetry"},
    "database": {"monitor": "telemetry"},
    "queue": {"worker": "jobs", "monitor": "telemetry"},
    "worker": {"monitor": "telemetry"},
    "monitor": {},
}
ALLOWED = {source: set(targets) for source, targets in CONNECTIONS.items()}


LEGACY_DATABASE_LIMITS = {
    "reads": number("Legacy read throttle", 155, 25, 10000, 5),
    "writes": number("Legacy write throttle", 62, 10, 5000, 1),
}


def defaults(kind: Kind) -> dict[str, Setting]:
    return {key: field["default"] for key, field in COMPONENTS[kind]["fields"].items()}


DIFFICULTIES = {
    "beginner": {
        "name": "Beginner",
        "balance": 10000,
        "audience": 8400,
        "incident_chance": 0.08,
    },
    "standard": {
        "name": "Standard",
        "balance": 7500,
        "audience": 9700,
        "incident_chance": 0.16,
    },
    "expert": {
        "name": "Expert",
        "balance": 4800,
        "audience": 11400,
        "incident_chance": 0.25,
    },
}


# Local activity sampled every three hours from midnight. Smooth interpolation
# between these anchors drives both the live workload and its forecast.
REGIONS = {
    "europe": {
        "name": "Europe",
        "timezone": "Europe/Paris",
        "population": 745_000_000,
        "potential": 74_500_000,
        "organic": 1,
        "acquisition_cost": 0.12,
        "premium_adoption": 1,
        "price_sensitivity": 1,
        "language": "French",
        "cost": 0,
        "duration": 0,
        "weekend": 1.06,
        "engagement": 1.0,
        "ad_value": 1.0,
        "profile": (0.43, 0.31, 0.48, 0.83, 0.85, 0.93, 1.03, 1.09),
    },
    "north_america": {
        "name": "North America",
        "timezone": "America/New_York",
        "population": 380_000_000,
        "potential": 46_360_000,
        "organic": 0.96,
        "acquisition_cost": 0.16,
        "premium_adoption": 1.14,
        "price_sensitivity": 0.8,
        "language": "English",
        "cost": 220,
        "duration": 24,
        "weekend": 1.08,
        "engagement": 0.95,
        "ad_value": 1.2,
        "profile": (0.44, 0.3, 0.47, 0.8, 0.86, 0.94, 1.02, 1.1),
    },
    "south_america": {
        "name": "South America",
        "timezone": "America/Sao_Paulo",
        "population": 440_000_000,
        "potential": 37_400_000,
        "organic": 1.18,
        "acquisition_cost": 0.08,
        "premium_adoption": 0.68,
        "price_sensitivity": 1.24,
        "language": "Spanish",
        "cost": 155,
        "duration": 20,
        "weekend": 1.12,
        "engagement": 1.02,
        "ad_value": 0.66,
        "profile": (0.5, 0.29, 0.42, 0.75, 0.91, 0.92, 1.08, 1.2),
    },
    "east_asia": {
        "name": "East Asia",
        "timezone": "Asia/Tokyo",
        "population": 1_650_000_000,
        "potential": 176_550_000,
        "organic": 1.08,
        "acquisition_cost": 0.13,
        "premium_adoption": 0.93,
        "price_sensitivity": 0.97,
        "language": "Japanese",
        "cost": 300,
        "duration": 34,
        "weekend": 1.05,
        "engagement": 1.13,
        "ad_value": 1.03,
        "profile": (0.48, 0.26, 0.46, 0.82, 0.92, 0.98, 1.09, 1.16),
    },
    "south_southeast_asia": {
        "name": "South and Southeast Asia",
        "timezone": "Asia/Kolkata",
        "population": 2_700_000_000,
        "potential": 221_400_000,
        "organic": 1.33,
        "acquisition_cost": 0.065,
        "premium_adoption": 0.54,
        "price_sensitivity": 1.38,
        "language": "Hindi",
        "cost": 255,
        "duration": 32,
        "weekend": 1.12,
        "engagement": 1.08,
        "ad_value": 0.52,
        "profile": (0.51, 0.32, 0.47, 0.87, 0.99, 0.99, 1.13, 1.22),
    },
    "mena": {
        "name": "Middle East and North Africa",
        "timezone": "Africa/Cairo",
        "population": 510_000_000,
        "potential": 42_840_000,
        "organic": 1.16,
        "acquisition_cost": 0.09,
        "premium_adoption": 0.7,
        "price_sensitivity": 1.21,
        "language": "Arabic",
        "cost": 185,
        "duration": 27,
        "weekend": 1.14,
        "engagement": 1.05,
        "ad_value": 0.74,
        "profile": (0.67, 0.33, 0.38, 0.71, 0.89, 0.96, 1.12, 1.26),
    },
    "sub_saharan_africa": {
        "name": "Sub-Saharan Africa",
        "timezone": "Africa/Lagos",
        "population": 1_200_000_000,
        "potential": 85_200_000,
        "organic": 1.38,
        "acquisition_cost": 0.06,
        "premium_adoption": 0.48,
        "price_sensitivity": 1.44,
        "language": "French",
        "cost": 170,
        "duration": 28,
        "weekend": 1.11,
        "engagement": 0.92,
        "ad_value": 0.45,
        "profile": (0.38, 0.26, 0.51, 0.84, 0.92, 1.02, 1.09, 1.07),
    },
    "oceania": {
        "name": "Oceania",
        "timezone": "Australia/Sydney",
        "population": 46_000_000,
        "potential": 5_106_000,
        "organic": 0.92,
        "acquisition_cost": 0.14,
        "premium_adoption": 1.09,
        "price_sensitivity": 0.85,
        "language": "English",
        "cost": 115,
        "duration": 16,
        "weekend": 1.08,
        "engagement": 0.97,
        "ad_value": 1.12,
        "profile": (0.42, 0.28, 0.49, 0.87, 0.88, 0.95, 1.06, 1.09),
    },
}

REGION_LOCALIZATION_BONUS = 0.18

# Simplified gameplay segments. Weights sum to one within each market.
REGION_LANGUAGE_WEIGHTS = {
    "europe": {"English": 0.35, "French": 0.25, "German": 0.22, "Spanish": 0.18},
    "north_america": {"English": 0.75, "Spanish": 0.18, "French": 0.07},
    "south_america": {"Spanish": 0.55, "Portuguese": 0.40, "English": 0.05},
    "east_asia": {"Japanese": 0.42, "Chinese": 0.39, "Korean": 0.15, "English": 0.04},
    "south_southeast_asia": {
        "Hindi": 0.50,
        "Indonesian": 0.24,
        "English": 0.18,
        "Chinese": 0.08,
    },
    "mena": {"Arabic": 0.78, "French": 0.12, "English": 0.10},
    "sub_saharan_africa": {"French": 0.48, "English": 0.37, "Portuguese": 0.15},
    "oceania": {"English": 0.87, "Chinese": 0.08, "Indonesian": 0.05},
}

LANGUAGES = {
    "German": (110, 18),
    "Portuguese": (110, 18),
    "Chinese": (170, 28),
    "Korean": (145, 23),
    "Indonesian": (125, 20),
    "French": (90, 14),
    "Spanish": (110, 18),
    "Japanese": (155, 25),
    "Hindi": (130, 21),
    "Arabic": (145, 23),
}

ADVERTISING = {
    "low": {"slots": 2, "fill": 0.79, "cpm": 1.40, "friction": 0.012, "churn": 0.001},
    "moderate": {
        "slots": 4,
        "fill": 0.72,
        "cpm": 1.30,
        "friction": 0.048,
        "churn": 0.007,
    },
    "high": {"slots": 7, "fill": 0.55, "cpm": 1.20, "friction": 0.16, "churn": 0.035},
}
BUSINESS = {
    "active_share": 0.64,
    "sessions_per_dau": 3.2,
    "traffic_cost_per_rps_day": 0.012,
    "payments_fee": 0.035,
    "premium_default_price": 4.0,
    "premium_min_price": 1.0,
    "premium_max_price": 15.0,
    "premium_daily_adoption": 0.0055,
    "premium_renewal": 0.91,
    "premium_quality_floor": 0.985,
    "premium_reliability_memory_days": 3,
    "premium_ad_free_satisfaction": 0.018,
    "premium_sync_multiplier": 1.30,
    "premium_sync_satisfaction": 0.012,
    "premium_standard_adoption_factor": 0.80,
    "premium_ad_free_adoption": 4.0,
    "premium_max_daily_adoption": 0.025,
    "premium_reliability_sensitivity": 4.0,
    "premium_renewal_price_sensitivity": 0.45,
    "premium_latency_threshold": 85,
    "premium_latency_scale": 320,
    "premium_price_sensitivity": 0.38,
    "expansion_acquisition_share": 0.55,
}

SYNC_FREQUENCY = {
    "relaxed": {"load": 0.75, "satisfaction": -0.032},
    "standard": {"load": 1.0, "satisfaction": 0.0},
    "frequent": {"load": 1.22, "satisfaction": 0.012},
}
MEDIA_QUALITY = {
    "compressed": {"size": 0.58, "cpu": 1.15, "satisfaction": -0.024},
    "standard": {"size": 1.0, "cpu": 1.0, "satisfaction": 0.0},
    "high": {"size": 1.52, "cpu": 0.95, "satisfaction": 0.018},
}
MEDIA_OPERATIONS = {"upload", "voice", "files"}
