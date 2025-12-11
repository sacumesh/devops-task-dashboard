# api.py
import os
import requests
from typing import List, Dict, Optional, Tuple, Any
from requests import Response
from dotenv import load_dotenv

# Load environment variables once from project root
load_dotenv()

# Configuration
MANGER_HOST: str = os.getenv("MANAGER_HOST", "localhost")
MANGER_PORT: str = os.getenv("MANAGER_PORT", "8080")
MANAGER_API_URL: str = os.getenv("MANAGER_API_URL", f"http://{MANGER_HOST}:{MANGER_PORT}")

# Session initialization
_session = requests.Session()
_session.headers.update({
    "Content-Type": "application/json",
    "Accept": "application/json",
})


class ApiError(Exception):
    """Base API error for UI-friendly messages."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class NetworkError(ApiError):
    """Raised when a connection-related error occurs."""
    pass


class TimeoutError(ApiError):
    """Raised when a request times out."""
    pass


class NotFoundError(ApiError):
    """Raised when a resource is not found."""
    pass


class UnauthorizedError(ApiError):
    """Raised when user is not authorized to perform an action."""
    pass


class ValidationError(ApiError):
    """Raised when server indicates request validation failure."""
    pass


def _url(path: str) -> str:
    """Construct an absolute URL from a relative path."""
    base = MANAGER_API_URL.rstrip("/")
    suffix = path.lstrip("/")
    return f"{base}/{suffix}"


def _parse_json_safely(resp: Response) -> Dict[str, Any]:
    """Parse JSON from a response, returning empty dict if not JSON."""
    try:
        data = resp.json()
        # Ensure the parsed payload is a dict or list; for UI we expect dict/list
        return data if isinstance(data, (dict, list)) else {}
    except ValueError:
        return {}


def _handle_response(resp: Response) -> Dict[str, Any]:
    """
    Raise domain-specific errors for non-2xx responses.
    Return parsed JSON (dict or list) for successful responses.
    """
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        status = resp.status_code
        payload = _parse_json_safely(resp)
        message = (
            (payload.get("message") or payload.get("error"))
            if isinstance(payload, dict)
            else None
        ) or str(e)

        if status == 404:
            raise NotFoundError("Item not found.", status_code=status, details=payload if isinstance(payload, dict) else {})
        if status in (401, 403):
            raise UnauthorizedError("You are not authorized to perform this action.", status_code=status, details=payload if isinstance(payload, dict) else {})
        if status == 400:
            raise ValidationError("Invalid request data.", status_code=status, details=payload if isinstance(payload, dict) else {})
        if 500 <= status < 600:
            raise ApiError("Server error. Please try again later.", status_code=status, details=payload if isinstance(payload, dict) else {})
        # Fallback for other status codes
        raise ApiError(message, status_code=status, details=payload if isinstance(payload, dict) else {})

    # Successful response
    data = _parse_json_safely(resp)
    # Normalize: return dict for object responses, list wrapped in dict for consistency
    return data if isinstance(data, dict) else {"data": data}


def _request(method: str, path: str, *, json: Optional[Dict[str, Any]] = None, ) -> Dict[str, Any]:
    """
    Core request executor. Converts low-level exceptions to domain errors.
    """
    try:
        resp = _session.request(method=method, url=_url(path), json=json)
        return _handle_response(resp)
    except requests.Timeout:
        raise TimeoutError("Request timed out. Check your network and try again.")
    except requests.ConnectionError:
        raise NetworkError("Network error. Please check your internet connection.")
    except requests.RequestException as e:
        # Catch-all for other request issues (e.g., invalid URL, SSL, etc.)
        raise ApiError(f"Unexpected error: {e}")


def _ui_message(error: ApiError) -> str:
    """
    Map technical errors to user-friendly messages for the frontend UI.
    """
    if isinstance(error, TimeoutError):
        return "The request timed out. Please try again."
    if isinstance(error, NetworkError):
        return "Network issue detected. Check your internet connection."
    if isinstance(error, NotFoundError):
        return "The requested item was not found."
    if isinstance(error, UnauthorizedError):
        return "You don't have permission to perform this action."
    if isinstance(error, ValidationError):
        details = error.details.get("fields") if isinstance(error.details, dict) else None
        if isinstance(details, dict) and details:
            parts = [f"{k}: {v}" for k, v in details.items()]
            return "Invalid input: " + "; ".join(parts)
        return "Invalid input provided. Please check your data."
    if error.status_code and 500 <= error.status_code < 600:
        return "A server error occurred. Please try again later."
    return str(error)


# Public API: return (data, error) for UI-friendly handling
def health() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        data = _request("GET", "actuator/health")
        return data, None
    except ApiError as e:
        return None, _ui_message(e)


def get_tasks() -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    try:
        data = _request("GET", "api/tasks")
        # Accept both list and dict-wrapped, normalize to list for caller
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            return data["data"], None
        if isinstance(data, list):
            return data, None
        return [], None
    except ApiError as e:
        return None, _ui_message(e)


def get_task(task_id: str, ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        data = _request("GET", f"api/tasks/{task_id}")
        return data, None
    except ApiError as e:
        return None, _ui_message(e)


def create_task(title: str, description: str = "", status: Optional[str] = None, ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload: Dict[str, Any] = {"title": title, "description": description}
    if status:
        payload["status"] = status
    try:
        data = _request("POST", "api/tasks", json=payload)
        return data, None
    except ApiError as e:
        return None, _ui_message(e)


def update_task(task_id: str, title: str, description: str, status: str, ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload: Dict[str, Any] = {"id": task_id, "title": title, "description": description, "status": status}
    try:
        data = _request("PUT", "api/tasks", json=payload)
        return data, None
    except ApiError as e:
        return None, _ui_message(e)


def delete_task(task_id: str, ) -> Tuple[bool, Optional[str]]:
    try:
        _request("DELETE", f"api/tasks/{task_id}")
        return True, None
    except ApiError as e:
        return False, _ui_message(e)
    

def api_version() -> Tuple[Optional[str], Optional[str]]:
    try:
        data = _request("GET", "api/version")
        version = data.get("apiVersion") if isinstance(data, dict) else None
        return version, None
    except ApiError as e:
        return None, _ui_message(e)
