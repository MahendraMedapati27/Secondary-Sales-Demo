"""
Metrics collection and monitoring utilities.

This module provides:
- Request metrics tracking
- Performance metrics
- Error rate tracking
- Circuit breaker metrics
"""
import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)

# Thread-safe metrics storage
_metrics_lock = Lock()
_metrics = {
    'requests': {
        'total': 0,
        'by_status': defaultdict(int),
        'by_endpoint': defaultdict(int),
        'response_times': deque(maxlen=1000)  # Keep last 1000 response times
    },
    'errors': {
        'total': 0,
        'by_type': defaultdict(int),
        'by_endpoint': defaultdict(int)
    },
    'external_services': {
        'groq': {'calls': 0, 'errors': 0, 'response_times': deque(maxlen=100)},
        'azure_translator': {'calls': 0, 'errors': 0, 'response_times': deque(maxlen=100)},
        'microsoft_graph': {'calls': 0, 'errors': 0, 'response_times': deque(maxlen=100)},
        'database': {'queries': 0, 'errors': 0, 'response_times': deque(maxlen=100)}
    },
    'circuit_breakers': {}
}


def record_request(endpoint, status_code, response_time):
    """Record request metrics"""
    with _metrics_lock:
        _metrics['requests']['total'] += 1
        _metrics['requests']['by_status'][status_code] += 1
        _metrics['requests']['by_endpoint'][endpoint] += 1
        _metrics['requests']['response_times'].append(response_time)


def record_error(error_type, endpoint):
    """Record error metrics"""
    with _metrics_lock:
        _metrics['errors']['total'] += 1
        _metrics['errors']['by_type'][error_type] += 1
        _metrics['errors']['by_endpoint'][endpoint] += 1


def record_external_service_call(service_name, success, response_time):
    """Record external service call metrics"""
    with _metrics_lock:
        if service_name not in _metrics['external_services']:
            _metrics['external_services'][service_name] = {
                'calls': 0,
                'errors': 0,
                'response_times': deque(maxlen=100)
            }
        
        service_metrics = _metrics['external_services'][service_name]
        service_metrics['calls'] += 1
        service_metrics['response_times'].append(response_time)
        
        if not success:
            service_metrics['errors'] += 1


def record_circuit_breaker_state(breaker_name, state):
    """Record circuit breaker state"""
    with _metrics_lock:
        if 'circuit_breakers' not in _metrics:
            _metrics['circuit_breakers'] = {}
        _metrics['circuit_breakers'][breaker_name] = {
            'state': state,
            'timestamp': datetime.utcnow().isoformat()
        }


def get_metrics_summary():
    """Get metrics summary"""
    with _metrics_lock:
        # Calculate averages
        response_times = list(_metrics['requests']['response_times'])
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Calculate error rate
        total_requests = _metrics['requests']['total']
        total_errors = _metrics['errors']['total']
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
        
        # External service metrics
        service_metrics = {}
        for service_name, metrics in _metrics['external_services'].items():
            service_times = list(metrics['response_times'])
            avg_time = sum(service_times) / len(service_times) if service_times else 0
            error_rate_service = (metrics['errors'] / metrics['calls'] * 100) if metrics['calls'] > 0 else 0
            
            service_metrics[service_name] = {
                'calls': metrics['calls'],
                'errors': metrics['errors'],
                'error_rate': error_rate_service,
                'avg_response_time': avg_time
            }
        
        return {
            'requests': {
                'total': total_requests,
                'by_status': dict(_metrics['requests']['by_status']),
                'by_endpoint': dict(_metrics['requests']['by_endpoint']),
                'avg_response_time': avg_response_time,
                'p95_response_time': _calculate_percentile(response_times, 95) if response_times else 0,
                'p99_response_time': _calculate_percentile(response_times, 99) if response_times else 0
            },
            'errors': {
                'total': total_errors,
                'error_rate': error_rate,
                'by_type': dict(_metrics['errors']['by_type']),
                'by_endpoint': dict(_metrics['errors']['by_endpoint'])
            },
            'external_services': service_metrics,
            'circuit_breakers': dict(_metrics.get('circuit_breakers', {}))
        }


def _calculate_percentile(data, percentile):
    """Calculate percentile of data"""
    if not data:
        return 0
    sorted_data = sorted(data)
    index = int(len(sorted_data) * percentile / 100)
    return sorted_data[min(index, len(sorted_data) - 1)]


def reset_metrics():
    """Reset all metrics (for testing)"""
    global _metrics
    with _metrics_lock:
        _metrics = {
            'requests': {
                'total': 0,
                'by_status': defaultdict(int),
                'by_endpoint': defaultdict(int),
                'response_times': deque(maxlen=1000)
            },
            'errors': {
                'total': 0,
                'by_type': defaultdict(int),
                'by_endpoint': defaultdict(int)
            },
            'external_services': {
                'groq': {'calls': 0, 'errors': 0, 'response_times': deque(maxlen=100)},
                'azure_translator': {'calls': 0, 'errors': 0, 'response_times': deque(maxlen=100)},
                'microsoft_graph': {'calls': 0, 'errors': 0, 'response_times': deque(maxlen=100)},
                'database': {'queries': 0, 'errors': 0, 'response_times': deque(maxlen=100)}
            },
            'circuit_breakers': {}
        }

