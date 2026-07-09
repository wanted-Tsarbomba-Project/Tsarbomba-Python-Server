from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "python_http_requests_total",
    "Total HTTP requests processed by the Python server.",
    ["domain", "method", "api", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "python_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["domain", "method", "api", "status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

RECOMMENDATION_GENERATION_STAGE_DURATION = Histogram(
    "recommendation_python_generation_stage_duration_seconds",
    "Python recommendation generation duration by stage.",
    ["stage", "scale_users"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

RECOMMENDATION_GENERATION_STAGE_LAST_DURATION = Gauge(
    "recommendation_python_generation_stage_last_duration_seconds",
    "Last Python recommendation generation duration by stage.",
    ["stage", "scale_users"],
)

RECOMMENDATION_GENERATION_SCALE = Gauge(
    "recommendation_python_generation_scale",
    "Last Python recommendation generation scale values.",
    ["type"],
)
