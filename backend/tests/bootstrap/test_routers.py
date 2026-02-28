from app.bootstrap.routers import api_router


def test_bootstrap_api_router_includes_health_endpoint() -> None:
    paths = {route.path for route in api_router.routes}

    assert "/api/health" in paths
