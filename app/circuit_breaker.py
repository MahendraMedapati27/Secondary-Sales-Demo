"""
Circuit breaker pattern implementation for external service calls.

This module provides:
- Circuit breaker for external services
- Automatic fallback mechanisms
- Failure tracking and recovery
"""
import time
import logging
from enum import Enum
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker implementation for external services.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        expected_exception: Exception type that indicates failure
        name: Name of the circuit breaker (for logging)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "CircuitBreaker"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.success_count = 0  # For half-open state
    
    def call(self, func: Callable, *args, fallback: Optional[Callable] = None, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments for function
            fallback: Optional fallback function if circuit is open
        
        Returns:
            Result of function or fallback
        """
        # Check circuit state
        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"{self.name}: Circuit breaker entering HALF_OPEN state")
            else:
                logger.warning(f"{self.name}: Circuit breaker is OPEN, using fallback")
                if fallback:
                    return fallback(*args, **kwargs)
                raise Exception(f"{self.name} circuit breaker is OPEN")
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            logger.error(f"{self.name}: Circuit breaker failure: {str(e)}")
            
            # Try fallback if available
            if fallback:
                logger.info(f"{self.name}: Using fallback function")
                return fallback(*args, **kwargs)
            raise
    
    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 2:  # Require 2 successes to close
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"{self.name}: Circuit breaker CLOSED (recovered)")
        else:
            # Reset failure count on success
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery attempt, reopen circuit
            self.state = CircuitState.OPEN
            self.success_count = 0
            logger.warning(f"{self.name}: Circuit breaker reopened after failed recovery")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"{self.name}: Circuit breaker OPENED after {self.failure_count} failures")
    
    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if not self.last_failure_time:
            return True
        
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.recovery_timeout
    
    def reset(self):
        """Manually reset circuit breaker"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info(f"{self.name}: Circuit breaker manually reset")
    
    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time,
            'recovery_timeout': self.recovery_timeout
        }


# Global circuit breakers for external services
_circuit_breakers = {}


def get_circuit_breaker(service_name: str, **kwargs) -> CircuitBreaker:
    """Get or create circuit breaker for a service"""
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker(name=service_name, **kwargs)
    return _circuit_breakers[service_name]


def circuit_breaker(service_name: str, fallback: Optional[Callable] = None, **breaker_kwargs):
    """
    Decorator to add circuit breaker to a function.
    
    Usage:
        @circuit_breaker('groq', fallback=fallback_function)
        def call_groq():
            ...
    """
    def decorator(func):
        breaker = get_circuit_breaker(service_name, **breaker_kwargs)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, fallback=fallback, **kwargs)
        
        return wrapper
    return decorator

