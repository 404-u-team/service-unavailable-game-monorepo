from src.simulation.models import Kind, Setting

MINUTES_PER_TICK = 10
TICKS_PER_DAY = 144
SECONDS_PER_TICK = 2
HISTORY_LIMIT = 144


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


COMPONENTS: dict[Kind, dict] = {
    "source": {
        "name": "Traffic source",
        "category": "Traffic",
        "daily": 0,
        "fields": {},
        "description": "Generates requests from active users, released features and audience activity.",
    },
    "balancer": {
        "name": "Load balancer",
        "category": "Traffic",
        "daily": 23,
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
        "daily": 42,
        "fields": {
            "instances": number("Instances", 1, 1, 24),
            "cpu": number("vCPU per instance", 2, 1, 32),
            "memory": number("RAM per instance (GB)", 4, 1, 128),
            "connections": number("Connections per instance", 1100, 100, 25000, 100),
            "network": number("Network per instance (MB/s)", 30, 5, 1000, 5),
            "concurrency": number("Concurrency per instance", 40, 5, 800, 5),
        },
        "description": "Executes application work and routes requests to data services. Instances share the same downstream dependencies.",
    },
    "database": {
        "name": "Database",
        "category": "Data",
        "daily": 51,
        "fields": {
            "reads": number("Reads per second", 155, 25, 10000, 5),
            "writes": number("Writes per second", 62, 10, 5000, 1),
            "memory": number("RAM (GB)", 8, 1, 128),
            "storage": number("Storage (GB)", 32, 4, 10000),
            "disk": choice("Storage type", "SSD", "SSD", "NVMe"),
            "connections": number("Connections", 350, 25, 10000, 25),
        },
        "description": "Serves persistent reads and writes with independent limits. NVMe increases I/O throughput.",
    },
    "replica": {
        "name": "Read replica",
        "category": "Data",
        "daily": 35,
        "fields": {
            "reads": number("Reads per second", 155, 25, 10000, 5),
            "memory": number("RAM (GB)", 8, 1, 128),
            "connections": number("Connections", 350, 25, 10000, 25),
        },
        "description": "Offloads reads. Connect it to a primary database for replication.",
    },
    "cache": {
        "name": "Cache",
        "category": "Data",
        "daily": 24,
        "fields": {
            "memory": number("Capacity (GB)", 2, 1, 64),
            "ttl": number("TTL (seconds)", 120, 10, 3600, 10),
            "policy": choice("Eviction policy", "LRU", "LRU", "LFU"),
            "scope": choice(
                "Cacheable reads", "All reads", "All reads", "History only"
            ),
        },
        "description": "Absorbs repeated reads. Misses follow its outgoing data connections. Writes still reach a primary.",
    },
    "limiter": {
        "name": "Rate limiter",
        "category": "Traffic",
        "daily": 14,
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
        "daily": 19,
        "fields": {
            "capacity": number("Capacity (jobs)", 30000, 100, 2_000_000, 100),
            "retention": number("Retention (minutes)", 60, 10, 1440, 10),
        },
        "description": "Buffers background work for workers. Full queues cause failures and old jobs can expire.",
    },
    "worker": {
        "name": "Worker",
        "category": "Compute",
        "daily": 28,
        "fields": {
            "instances": number("Instances", 1, 1, 24),
            "cpu": number("vCPU per instance", 2, 1, 32),
            "concurrency": number("Concurrency per instance", 10, 1, 200),
        },
        "description": "Processes queued jobs. Add CPU or concurrency to drain backlogs faster.",
    },
    "monitor": {
        "name": "Monitoring",
        "category": "Operations",
        "daily": 17,
        "fields": {
            "detail": choice(
                "Collection scope",
                "Linked components",
                "Linked components",
                "Service history",
            )
        },
        "description": "Connect production components to Monitoring to inspect their telemetry and incident causes.",
    },
}

SCENARIOS = {
    "messenger": {
        "name": "Messenger",
        "available": True,
        "description": "Messaging, chat history and persistent connections.",
        "activity": 1.0,
        "daily_revenue": 0.018,
        "organic": 0.009,
        "operations": ["send", "history", "conversations", "auth", "connection"],
    },
    "social": {
        "name": "Social network",
        "available": False,
        "description": "Feeds, media uploads and advertising.",
        "activity": 1.2,
        "daily_revenue": 0.014,
        "organic": 0.012,
        "operations": ["feed", "upload", "auth"],
    },
    "multiplayer": {
        "name": "Multiplayer game",
        "available": False,
        "description": "Real-time sessions and in-game purchases.",
        "activity": 1.4,
        "daily_revenue": 0.027,
        "organic": 0.007,
        "operations": ["session", "connection", "auth"],
    },
    "education": {
        "name": "Educational platform",
        "available": False,
        "description": "Lessons, streaming and subscriptions.",
        "activity": 0.8,
        "daily_revenue": 0.022,
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
) -> dict:
    return {
        "name": name,
        "cost": cost,
        "duration": duration,
        "appeal": appeal,
        "operation": operation_id,
        "prereq": prereq,
        "requires": requires,
    }


FEATURES = {
    "text": feature("Text messaging", 0, 0, 0, None, ()),
    "groups": feature("Group chats", 650, 12, 0.17, "groups"),
    "images": feature(
        "Image attachments", 950, 20, 0.23, "upload", requires=("database",)
    ),
    "voice": feature(
        "Voice messages", 1200, 24, 0.18, "voice", ("images",), ("database",)
    ),
    "search": feature("Message search", 1600, 28, 0.24, "search", ("groups",)),
    "files": feature(
        "File sharing", 2000, 36, 0.22, "files", ("images",), ("queue", "worker")
    ),
    "calls": feature("Voice calls", 3100, 48, 0.31, "calls", ("voice",), ("balancer",)),
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

ALLOWED: dict[Kind, set[Kind]] = {
    "source": {"api", "balancer", "limiter"},
    "limiter": {"balancer", "api", "monitor"},
    "balancer": {"api", "monitor"},
    "api": {"database", "replica", "cache", "queue", "monitor"},
    "cache": {"database", "replica", "monitor"},
    "replica": {"database", "monitor"},
    "database": {"monitor"},
    "queue": {"worker", "monitor"},
    "worker": {"monitor"},
    "monitor": set(),
}


def defaults(kind: Kind) -> dict[str, Setting]:
    return {key: field["default"] for key, field in COMPONENTS[kind]["fields"].items()}


DIFFICULTIES = {
    "beginner": {
        "name": "Beginner",
        "balance": 10000,
        "audience": 8400,
        "incident_chance": 0.16,
    },
    "standard": {
        "name": "Standard",
        "balance": 7500,
        "audience": 9700,
        "incident_chance": 0.23,
    },
    "expert": {
        "name": "Expert",
        "balance": 4800,
        "audience": 11400,
        "incident_chance": 0.32,
    },
}
