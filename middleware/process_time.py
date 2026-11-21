import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("requests")

class ProcessTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        status_code = 500
        process_time = -1
        try:
            response = await call_next(request)
            status_code = response.status_code
            process_time = time.perf_counter() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            return response
        finally:
            if request.url.path != "/health" and request.method != "OPTIONS":
                route = request.scope.get("route")
                metadata = {
                    "uid": getattr(request.state, "uid", None),
                    "method": request.method,
                    "route": route.path if route else request.url.path,
                    "status": status_code,
                    "process_time": time.perf_counter() - start_time
                }
                logger.info(f"{request.method} {metadata["route"]}: {status_code}", extra={"json_fields": metadata})
