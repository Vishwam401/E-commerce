"""
Custom Exception Hierarchy for Alpha-Commerce

Architecture:
    Exception (Python built-in)
    └── AppException (Base for our app)
        ├── BadRequestError (400)
        ├── UnauthorizedError (401)
        ├── ForbiddenError (403)
        ├── NotFoundError (404)
        ├── ConflictError (409)
        ├── RateLimitError (429)
        └── ServiceUnavailableError (503)
            └── PaymentGatewayError (502/503)
"""

import uuid
from typing import List, Optional


class AppException(Exception):
    """
    Base exception class for entire application.
    Every custom exception inherits from this.

    super().__init__(self.message) calls Python's built-in Exception.__init__().
    This ensures:
      1. str(exception) returns the message
      2. traceback is properly captured
      3. exception can be caught as 'except Exception'
    """

    def __init__(self, message: str, status_code: int = 500, error_code: str = None):
        self.message = message
        self.status_code = status_code
        # Agar error_code nahi diya, toh class ka naam use karo
        self.error_code = error_code or self.__class__.__name__

        # Parent Exception class ka constructor call karo
        super().__init__(self.message)


# ==================== HTTP-Level Exceptions ====================

class BadRequestError(AppException):
    """400 - Client ne galat data bheja"""

    def __init__(self, message: str = "Bad request"):
        super().__init__(message, status_code=400)


class UnauthorizedError(AppException):
    """401 - User login nahi hai ya token invalid"""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)


class ForbiddenError(AppException):
    """403 - User login hai par permission nahi"""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)


class NotFoundError(AppException):
    """404 - Resource DB mein nahi mila"""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ConflictError(AppException):
    """409 - Duplicate entry ya resource already exists"""

    def __init__(self, message: str = "Conflict"):
        super().__init__(message, status_code=409)


class RateLimitError(AppException):
    """429 - Too many requests"""

    def __init__(self, message: str = "Too many requests"):
        super().__init__(message, status_code=429)


class ServiceUnavailableError(AppException):
    """503 - External service down (Redis, Razorpay, SMTP)"""

    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(message, status_code=503)


# ==================== Domain-Specific Exceptions ====================
# Ye sab upar wali classes se inherit karte hain
# Isse handler automatically unka status_code jaan jata hai

class CartEmptyError(BadRequestError):
    def __init__(self):
        super().__init__("Cart is empty.")


class InsufficientStockError(BadRequestError):
    def __init__(self, product_name: str = "item"):
        super().__init__(f"Insufficient stock for '{product_name}'.")


class ProductUnavailableError(BadRequestError):
    def __init__(self, product_id: str = "unknown"):
        super().__init__(f"Product '{product_id}' is unavailable or deleted.")


class InvalidAddressError(BadRequestError):
    def __init__(self):
        super().__init__("Invalid or deleted shipping address.")


class MinimumOrderError(BadRequestError):
    def __init__(self):
        super().__init__("Minimum order amount must be at least ₹1.")


class PaymentGatewayError(ServiceUnavailableError):
    """Razorpay down ya order creation fail"""

    def __init__(self, message: str = "Payment gateway error"):
        super().__init__(message)


class PaymentVerificationError(BadRequestError):
    """Razorpay signature mismatch"""

    def __init__(self):
        super().__init__("Payment verification failed. Invalid signature.")


class OrderCancellationError(BadRequestError):
    def __init__(self, status: str):
        super().__init__(f"Cannot cancel order in {status} status.")


class InvalidStatusTransitionError(BadRequestError):
    def __init__(self, current: str, target: str, allowed: Optional[List[str]] = None):
        allowed_str = ", ".join(allowed) if allowed else "none (terminal state)"
        super().__init__(
            f"Invalid status transition: '{current}' → '{target}'. "
            f"Allowed next states: {allowed_str}."
        )


class EmailAlreadyExistsError(ConflictError):
    def __init__(self):
        super().__init__("This email is already registered.")


class UsernameAlreadyExistsError(ConflictError):
    def __init__(self):
        super().__init__("This username is already registered.")


class DataIntegrityError(ServiceUnavailableError):
    """DB mein kuch toot-phoot ho gayi"""

    def __init__(self, message: str = "Data integrity error"):
        super().__init__(message)


class WebhookSignatureError(BadRequestError):
    def __init__(self):
        super().__init__("Invalid webhook signature.")


class DatabaseError(ServiceUnavailableError):
    """SQLAlchemy fail hone pe"""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message)


class AuthenticationError(UnauthorizedError):
    """Token invalid, expired, ya blacklist mein"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)


class AccountInactiveError(ForbiddenError):
    def __init__(self):
        super().__init__("Account is not active. Please verify your email.")


class TokenCompromisedError(UnauthorizedError):
    """Refresh token theft detection"""

    def __init__(self):
        super().__init__("Token compromised. Please login again.")


class InvalidTokenError(BadRequestError):
    """JWT decode fail ya wrong token type"""

    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(message)


class SessionInvalidatedError(UnauthorizedError):
    """Password change ke baad purana token use hua"""

    def __init__(self):
        super().__init__("Invalidated session. Please login again.")