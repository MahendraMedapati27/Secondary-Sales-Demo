"""Verification script to check all production improvements"""
from app import create_app

app = create_app()

print("=" * 60)
print("PRODUCTION IMPROVEMENTS VERIFICATION")
print("=" * 60)

# 1. Check endpoints
print("\n1. HEALTH CHECK ENDPOINTS:")
routes = [str(rule) for rule in app.url_map.iter_rules()]
health_routes = [r for r in routes if 'health' in r or 'metrics' in r]
for route in sorted(health_routes):
    print(f"   ✓ {route}")

# 2. Check configuration
print("\n2. CONFIGURATION:")
print(f"   ✓ MAX_CONTENT_LENGTH: {app.config.get('MAX_CONTENT_LENGTH') / 1024 / 1024}MB")
db_opts = app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
print(f"   ✓ DB Pool Size: {db_opts.get('pool_size')}")
print(f"   ✓ DB Max Overflow: {db_opts.get('max_overflow')}")
print(f"   ✓ DB Pool Pre-ping: {db_opts.get('pool_pre_ping')}")
print(f"   ✓ Session Lifetime: {app.config.get('PERMANENT_SESSION_LIFETIME')}s")

# 3. Check imports
print("\n3. MODULE IMPORTS:")
modules = [
    'app.error_handling',
    'app.timeout_utils',
    'app.session_manager',
    'app.circuit_breaker',
    'app.db_locking',
    'app.metrics'
]
for module in modules:
    try:
        __import__(module)
        print(f"   ✓ {module}")
    except Exception as e:
        print(f"   ✗ {module}: {str(e)}")

# 4. Check integrations
print("\n4. INTEGRATIONS:")
checks = {
    'Error Handler': any('handle_exception' in str(h) for h in app.error_handler_spec.get(None, {}).values()) if hasattr(app, 'error_handler_spec') else False,
    'Before Request Hook': len(app.before_request_funcs.get(None, [])) > 0,
    'After Request Hook': len(app.after_request_funcs.get(None, [])) > 0,
    'Metrics Endpoint': '/metrics' in routes,
    'Health Endpoints': len(health_routes) >= 3
}
for check, result in checks.items():
    status = "✓" if result else "✗"
    print(f"   {status} {check}")

# 5. Check timeout configurations
print("\n5. TIMEOUT CONFIGURATIONS:")
try:
    from app.timeout_utils import TIMEOUTS
    for service, timeout in TIMEOUTS.items():
        print(f"   ✓ {service}: {timeout}s")
except Exception as e:
    print(f"   ✗ Error loading timeouts: {str(e)}")

# 6. Check circuit breakers
print("\n6. CIRCUIT BREAKERS:")
try:
    from app.circuit_breaker import _circuit_breakers
    if _circuit_breakers:
        print(f"   ✓ Circuit breakers initialized: {len(_circuit_breakers)}")
        for name in _circuit_breakers.keys():
            print(f"     - {name}")
    else:
        print("   ✓ Circuit breakers ready (will be created on first use)")
except Exception as e:
    print(f"   ✗ Error: {str(e)}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)

