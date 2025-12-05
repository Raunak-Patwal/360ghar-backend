from typing import Any, Dict, Optional
from fastapi import HTTPException, status

class BaseAPIException(HTTPException):
    """Base exception for all API exceptions"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "An error occurred"
    headers = None

    def __init__(
        self,
        detail: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        super().__init__(
            status_code=self.status_code,
            detail=detail or self.detail,
            headers=headers or self.headers
        )
        self.extra = kwargs

class NotFoundException(BaseAPIException):
    """Resource not found exception"""
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"

class UnauthorizedException(BaseAPIException):
    """Unauthorized access exception"""
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Unauthorized access"
    headers = {"WWW-Authenticate": "Bearer"}

class ForbiddenException(BaseAPIException):
    """Forbidden access exception"""
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Access forbidden"

class ValidationException(BaseAPIException):
    """Validation error exception"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation error"

class ConflictException(BaseAPIException):
    """Conflict error exception"""
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource conflict"

class BadRequestException(BaseAPIException):
    """Bad request exception"""
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad request"

class RateLimitException(BaseAPIException):
    """Rate limit exceeded exception"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Rate limit exceeded"
    headers = {"Retry-After": "60"}

class ServiceUnavailableException(BaseAPIException):
    """Service unavailable exception"""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Service temporarily unavailable"

# Domain-specific exceptions
class PropertyNotFoundException(NotFoundException):
    """Property not found exception"""
    detail = "Property not found"

class UserNotFoundException(NotFoundException):
    """User not found exception"""
    detail = "User not found"

class AgentNotFoundException(NotFoundException):
    """Agent not found exception"""
    detail = "Agent not found"

class BookingNotFoundException(NotFoundException):
    """Booking not found exception"""
    detail = "Booking not found"

class VisitNotFoundException(NotFoundException):
    """Visit not found exception"""
    detail = "Visit not found"

class InsufficientPermissionsError(ForbiddenException):
    """Insufficient permissions error"""
    detail = "Insufficient permissions to perform this action"

class PropertyOwnershipError(ForbiddenException):
    """Property ownership error"""
    detail = "You can only modify your own properties"

class BookingConflictError(ConflictException):
    """Booking conflict error"""
    detail = "Property not available for the requested dates"

class DuplicateSwipeError(ConflictException):
    """Duplicate swipe error"""
    detail = "You have already swiped on this property"
