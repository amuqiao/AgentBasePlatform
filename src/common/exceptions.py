from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", details: dict | None = None):
        super().__init__(code=40400, message=message, status_code=404, details=details)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized", details: dict | None = None):
        super().__init__(code=40100, message=message, status_code=401, details=details)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden", details: dict | None = None):
        super().__init__(code=40300, message=message, status_code=403, details=details)


class ValidationException(AppException):
    def __init__(self, message: str = "Validation error", details: dict | None = None):
        super().__init__(code=40000, message=message, status_code=422, details=details)


class ConflictException(AppException):
    def __init__(self, message: str = "Resource already exists", details: dict | None = None):
        super().__init__(code=40900, message=message, status_code=409, details=details)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "request_id": getattr(_request.state, "request_id", None),
        },
    )


async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "code": 50000,
            "message": "Internal server error",
            "details": str(exc) if getattr(_request.app.state, "debug", False) else None,
            "request_id": getattr(_request.state, "request_id", None),
        },
    )
