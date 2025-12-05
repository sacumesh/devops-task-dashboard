# api.py
import requests
import os
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()  # loads .env from project root

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080/api/")

_session = requests.Session()
_session.headers.update({"Content-Type": "application/json"})


class ApiError(Exception):
    """Base API error for UI-friendly messages."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class NetworkError(ApiError):
    pass


class TimeoutError(ApiError):
    pass


class NotFoundError(ApiError):
    pass


class UnauthorizedError(ApiError):
    pass


class ValidationError(ApiError):
    pass


def _url(path: str) -> str:
    return f"{API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _handle_response(resp: requests.Response) -> Dict:
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        status = resp.status_code
        # Try to parse server-provided error payload
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        message = payload.get("message") or payload.get("error") or str(e)

        if status == 404:
            raise NotFoundError("Item not found.",
                                status_code=status, details=payload)
        elif status in (401, 403):
            raise UnauthorizedError(
                "You are not authorized to perform this action.", status_code=status, details=payload)
        elif status == 400:
            raise ValidationError("Invalid request data.",
                                  status_code=status, details=payload)
        elif 500 <= status < 600:
            raise ApiError("Server error. Please try again later.",
                           status_code=status, details=payload)
        else:
            raise ApiError(message, status_code=status, details=payload)
    # If OK, return parsed json (or empty)
    try:
        return resp.json()
    except ValueError:
        return {}


def _request(method: str, path: str, *, json: Optional[Dict] = None, timeout: int = 10) -> Dict:
    try:
        resp = _session.request(method, _url(path), json=json, timeout=timeout)
        return _handle_response(resp)
    except requests.Timeout:
        raise TimeoutError(
            "Request timed out. Check your network and try again.")
    except requests.ConnectionError:
        raise NetworkError(
            "Network error. Please check your internet connection.")
    except requests.RequestException as e:
        raise ApiError(f"Unexpected error: {e}")

# Public API: return (data, error) for UI-friendly handling


def get_tasks(timeout: int = 10) -> Tuple[Optional[List[Dict]], Optional[str]]:
    try:
        data = _request("GET", "/tasks", timeout=timeout)
        return data, None
    except ApiError as e:
        return None, _ui_message(e)


def get_task(task_id: str, timeout: int = 10) -> Tuple[Optional[Dict], Optional[str]]:
    try:
        data = _request("GET", f"/tasks/{task_id}", timeout=timeout)
        return data, None
    except ApiError as e:
        return None, _ui_message(e)


def create_task(title: str, description: str = "", status: Optional[str] = None, timeout: int = 10) -> Tuple[Optional[Dict], Optional[str]]:
    payload = {"title": title, "description": description}
    if status:
        payload["status"] = status
    try:
        data = _request("POST", "/tasks", json=payload, timeout=timeout)
        return data, None
    except ApiError as e:
        return None, _ui_message(e)


def update_task(task_id: str, title: str, description: str, status: str, timeout: int = 10) -> Tuple[Optional[Dict], Optional[str]]:
    payload = {"id": task_id, "title": title,
               "description": description, "status": status}
    try:
        data = _request("PUT", "/tasks", json=payload, timeout=timeout)
        return data, None
    except ApiError as e:
        return None, _ui_message(e)


def delete_task(task_id: str, timeout: int = 10) -> Tuple[bool, Optional[str]]:
    try:
        _request("DELETE", f"/tasks/{task_id}", timeout=timeout)
        return True, None
    except ApiError as e:
        return False, _ui_message(e)


def _ui_message(error: ApiError) -> str:
    # Map technical errors to user-friendly messages for the frontend UI
    if isinstance(error, TimeoutError):
        return "The request timed out. Please try again."
    if isinstance(error, NetworkError):
        return "Network issue detected. Check your internet connection."
    if isinstance(error, NotFoundError):
        return "The requested item was not found."
    if isinstance(error, UnauthorizedError):
        return "You don't have permission to perform this action."
    if isinstance(error, ValidationError):
        # Show validation details if available
        details = error.details.get("fields")
        if isinstance(details, dict) and details:
            # Example: combine field errors into a single string
            parts = [f"{k}: {v}" for k, v in details.items()]
            return "Invalid input: " + "; ".join(parts)
        return "Invalid input provided. Please check your data."
    if error.status_code and 500 <= error.status_code < 600:
        return "A server error occurred. Please try again later."
    return str(error)
