from prometheus_client import Counter, Histogram, Gauge
from fastapi import Request
from fastapi.routing import APIRoute
import time
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# HTTP Metrics
# ============================================================================

# Request counter by method, endpoint, and status
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# Request duration histogram
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

# Request size
http_request_size_bytes = Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint']
)

# Response size
http_response_size_bytes = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint']
)

# Active requests gauge
http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests in progress',
    ['method', 'endpoint']
)

# ============================================================================
# Application-Specific Metrics
# ============================================================================

# Database operations
db_operations_total = Counter(
    'db_operations_total',
    'Total database operations',
    ['operation_type', 'collection', 'status']
)

db_operation_duration_seconds = Histogram(
    'db_operation_duration_seconds',
    'Database operation duration in seconds',
    ['operation_type', 'collection']
)

# Authentication metrics
auth_attempts_total = Counter(
    'auth_attempts_total',
    'Total authentication attempts',
    ['status']  # success, failed, invalid
)

# Employee operations
employee_operations_total = Counter(
    'employee_operations_total',
    'Total employee operations',
    ['operation']  # created, updated, deleted, viewed
)

# Production metrics
production_entries_total = Counter(
    'production_entries_total',
    'Total production entries',
    ['status']  # submitted, pending_approval, approved, rejected
)

# FG Stock operations
fg_stock_operations_total = Counter(
    'fg_stock_operations_total',
    'Total FG stock operations',
    ['operation']  # dispatch, adjustment, bin_transfer
)

# Cache operations
cache_operations_total = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'status']  # hit, miss, set, delete
)

# ============================================================================
# Middleware Class
# ============================================================================

class PrometheusMiddleware:
    """
    FastAPI middleware to collect Prometheus metrics
    """
    
    async def __call__(self, request: Request, call_next):
        # Extract route pattern (e.g., /api/v1/employees/{emp_id})
        route = request.url.path
        for route_obj in request.app.routes:
            if isinstance(route_obj, APIRoute):
                match = route_obj.path_regex.match(route)
                if match:
                    route = route_obj.path
                    break
        
        method = request.method
        
        # Track in-progress requests
        http_requests_in_progress.labels(method=method, endpoint=route).inc()
        
        # Track request size
        request_size = int(request.headers.get('content-length', 0))
        http_request_size_bytes.labels(method=method, endpoint=route).observe(request_size)
        
        # Start timer
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Track response metrics
            duration = time.time() - start_time
            status_code = response.status_code
            
            # Record metrics
            http_requests_total.labels(
                method=method, 
                endpoint=route, 
                status_code=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method, 
                endpoint=route
            ).observe(duration)
            
            # Track response size (if available)
            if hasattr(response, 'body'):
                response_size = len(response.body)
                http_response_size_bytes.labels(
                    method=method, 
                    endpoint=route
                ).observe(response_size)
            
            return response
            
        except Exception as e:
            # Track failed requests
            http_requests_total.labels(
                method=method, 
                endpoint=route, 
                status_code=500
            ).inc()
            
            logger.error(f"Request failed: {str(e)}")
            raise
            
        finally:
            # Decrement in-progress counter
            http_requests_in_progress.labels(method=method, endpoint=route).dec()


# ============================================================================
# Helper Functions for Application Metrics
# ============================================================================

def track_db_operation(operation_type: str, collection: str, duration: float, success: bool):
    """Track database operation metrics"""
    status = "success" if success else "error"
    db_operations_total.labels(
        operation_type=operation_type,
        collection=collection,
        status=status
    ).inc()
    
    db_operation_duration_seconds.labels(
        operation_type=operation_type,
        collection=collection
    ).observe(duration)


def track_auth_attempt(success: bool):
    """Track authentication attempts"""
    status = "success" if success else "failed"
    auth_attempts_total.labels(status=status).inc()


def track_employee_operation(operation: str):
    """Track employee operations"""
    employee_operations_total.labels(operation=operation).inc()


def track_production_entry(status: str):
    """Track production entry submissions"""
    production_entries_total.labels(status=status).inc()


def track_fg_stock_operation(operation: str):
    """Track FG stock operations"""
    fg_stock_operations_total.labels(operation=operation).inc()


def track_cache_operation(operation: str, hit: bool = None):
    """Track cache operations"""
    if hit is not None:
        status = "hit" if hit else "miss"
    else:
        status = "success"
    
    cache_operations_total.labels(
        operation=operation,
        status=status
    ).inc()