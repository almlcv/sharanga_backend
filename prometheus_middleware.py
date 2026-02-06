from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
import time
from typing import Callable


# -------------------------
# HTTP Metrics
# -------------------------

http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'HTTP requests currently in progress',
    ['method', 'endpoint']
)

# -------------------------
# Database Metrics
# -------------------------

db_operations_total = Counter(
    'db_operations_total',
    'Total database operations',
    ['operation', 'collection', 'status']
)

db_operation_duration_seconds = Histogram(
    'db_operation_duration_seconds',
    'Database operation duration',
    ['operation', 'collection'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# -------------------------
# Production Metrics
# -------------------------

production_documents_total = Counter(
    'production_documents_total',
    'Total production documents created',
    ['part_description', 'status']
)

production_quantity = Counter(
    'production_quantity_total',
    'Total production quantity',
    ['part_description', 'type']  # type: ok, rejected
)

production_downtime_minutes = Counter(
    'production_downtime_minutes_total',
    'Total production downtime in minutes',
    ['part_description', 'downtime_code']
)

machine_utilization = Gauge(
    'machine_utilization_percent',
    'Current machine utilization percentage',
    ['part_description']
)

# -------------------------
# Stock Metrics
# -------------------------

fg_stock_current = Gauge(
    'fg_stock_current_quantity',
    'Current FG stock quantity',
    ['variant_name']
)

rm_stock_current = Gauge(
    'rm_stock_current_kgs',
    'Current raw material stock in kgs',
    ['material_name', 'location']  # location: hopper, store
)

# -------------------------
# Business Metrics
# -------------------------

plan_achievement = Gauge(
    'plan_achievement_percent',
    'Production plan achievement percentage',
    ['part_description', 'month']
)

rejection_rate = Gauge(
    'rejection_rate_percent',
    'Production rejection rate percentage',
    ['part_description']
)


# -------------------------
# Middleware
# -------------------------

class PrometheusMiddleware(BaseHTTPMiddleware):
    """Automatically track HTTP metrics"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)
        
        # Get endpoint pattern (not full path with IDs)
        endpoint = self._get_endpoint_pattern(request)
        method = request.method
        
        # Track in-progress
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
        
        # Start timer
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status = response.status_code
            
            # Record metrics
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status
            ).inc()
            
            duration = time.time() - start_time
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            return response
            
        except Exception as e:
            # Record error
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=500
            ).inc()
            raise
            
        finally:
            # Decrement in-progress
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()
    
    def _get_endpoint_pattern(self, request: Request) -> str:
        """Get route pattern like /api/production/{doc_id}"""
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return route.path
        return request.url.path


# -------------------------
# Helper Functions
# -------------------------

def track_production_doc(part_description: str, status: str):
    """Track production document creation"""
    production_documents_total.labels(
        part_description=part_description,
        status=status
    ).inc()


def track_production_quantity(part_description: str, ok_qty: int, rejected_qty: int):
    """Track production quantities"""
    production_quantity.labels(
        part_description=part_description,
        type="ok"
    ).inc(ok_qty)
    
    production_quantity.labels(
        part_description=part_description,
        type="rejected"
    ).inc(rejected_qty)


def track_downtime(part_description: str, downtime_code: str, minutes: float):
    """Track production downtime"""
    production_downtime_minutes.labels(
        part_description=part_description,
        downtime_code=downtime_code
    ).inc(minutes)


def update_machine_utilization(part_description: str, utilization_pct: float):
    """Update machine utilization gauge"""
    machine_utilization.labels(
        part_description=part_description
    ).set(utilization_pct)


def update_fg_stock(variant_name: str, quantity: int):
    """Update FG stock gauge"""
    fg_stock_current.labels(
        variant_name=variant_name
    ).set(quantity)


def update_rm_stock(material_name: str, hopper_kgs: float, store_kgs: float):
    """Update RM stock gauges"""
    rm_stock_current.labels(
        material_name=material_name,
        location="hopper"
    ).set(hopper_kgs)
    
    rm_stock_current.labels(
        material_name=material_name,
        location="store"
    ).set(store_kgs)


def update_plan_achievement(part_description: str, month: str, achievement_pct: float):
    """Update plan achievement gauge"""
    plan_achievement.labels(
        part_description=part_description,
        month=month
    ).set(achievement_pct)


def update_rejection_rate(part_description: str, rate_pct: float):
    """Update rejection rate gauge"""
    rejection_rate.labels(
        part_description=part_description
    ).set(rate_pct)


# -------------------------
# Metrics Endpoint
# -------------------------

def metrics_endpoint() -> Response:
    """Return Prometheus metrics"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )