from .health import router as health_router
from .appointment import router as appointment_router, debug_router

__all__ = ["health_router", "appointment_router", "debug_router"]
