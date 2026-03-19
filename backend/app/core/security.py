from fastapi import Depends, HTTPException, Request

from app.core.config import settings


def get_current_user_id(request: Request) -> int:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth.split(" ", 1)[1].strip()
    if token != settings.api_auth_token:
        raise HTTPException(status_code=403, detail="Invalid token")

    # Demo mode: a user id can be provided by the client. If omitted, we default to the seeded user.
    header_user_id = request.headers.get("x-user-id")
    if header_user_id:
        try:
            return int(header_user_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid x-user-id") from e

    return 1


def workspace_user_scope(workspace_user_id: int, current_user_id: int) -> None:
    if workspace_user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Workspace does not belong to user")


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

