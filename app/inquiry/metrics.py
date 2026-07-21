from prometheus_client import Histogram

# inquiry 패키지 전용 메트릭. 공통 app/monitoring/metrics.py는 건드리지 않는다.
INQUIRY_ANALYSIS_STAGE_DURATION = Histogram(
    "inquiry_python_analysis_stage_duration_seconds",
    "Python inquiry AI analysis duration by stage.",
    ["stage"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
