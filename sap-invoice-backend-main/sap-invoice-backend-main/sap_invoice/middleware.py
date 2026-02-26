# from django.utils.timezone import localtime, timezone  # Import timezone
from django.utils import timezone
import logging
import json

logger = logging.getLogger("django")


class RequestResponseLoggerMiddleware:
    """
    Middleware to log request and response data
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log request details
        self.log_request(request)

        # Get response
        response = self.get_response(request)

        # Log response details
        self.log_response(response)

        return response

    def log_request(self, request):
        """
        Logs request data such as method, path, and body (if any).
        """
        request_data = {
            "method": request.method,
            "path": request.get_full_path(),
            "body": self.get_request_body(request),
            "headers": dict(request.headers),
            "timestamp": timezone.localtime(timezone.now()).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),  # Use timezone.now() here
        }
        logger.info(f"Request: {json.dumps(request_data, indent=4)}")

    def log_response(self, response):
        """
        Logs response data such as status code and body.
        """
        response_data = {
            "status_code": response.status_code,
            "body": self.get_response_body(response),
            "timestamp": timezone.localtime(timezone.now()).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),  # Use timezone.now() here
        }
        logger.info(f"Response: {json.dumps(response_data, indent=4)}")

    def get_request_body(self, request):
        """
        Returns the request body if it's a POST or PUT request
        and the content-type is JSON.
        """
        if (
            request.method in ["POST", "PUT"]
            and request.content_type == "application/json"
        ):
            try:
                return json.loads(request.body)
            except ValueError:
                return None
        return None

    def get_response_body(self, response):
        """
        Returns the response body if it's a JSON response.
        """
        if "application/json" in response.get("Content-Type", ""):
            try:
                return json.loads(response.content)
            except ValueError:
                return None
        return None
