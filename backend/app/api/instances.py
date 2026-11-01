import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.deps import get_current_user, get_db
from app.services.errors import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.services.instances import create_instance, delete_instance, list_instances_for_user, stop_instance
from app.services.sessions import AuthenticatedUser

router = APIRouter()


class CreateInstanceRequest(BaseModel):
    image_id: int


class InstanceResponse(BaseModel):
    id: str
    image_id: int
    image_display_name: str
    image_repository: str
    image_tag: str
    state: str
    error_message: str | None
    mcp_validation_errors: list[str] = []


def _to_response(row: sqlite3.Row) -> InstanceResponse:
    return InstanceResponse(
        id=row["id"],
        image_id=row["image_id"],
        image_display_name=row["image_display_name"],
        image_repository=row["image_repository"],
        image_tag=row["image_tag"],
        state=row["state"],
        error_message=row["error_message"],
        mcp_validation_errors=json.loads(row["mcp_validation_errors"])
        if row["mcp_validation_errors"]
        else [],
    )


@router.post("/instances", response_model=InstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_instance_endpoint(
    body: CreateInstanceRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> InstanceResponse:
    settings = request.app.state.settings
    runtime = request.app.state.runtime
    try:
        row = await create_instance(db, runtime, settings, user.id, body.image_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return _to_response(row)


@router.get("/instances", response_model=list[InstanceResponse])
def list_instances_endpoint(
    user: AuthenticatedUser = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
) -> list[InstanceResponse]:
    return [_to_response(row) for row in list_instances_for_user(db, user.id)]


@router.post("/instances/{instance_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_instance_endpoint(
    instance_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    try:
        await stop_instance(db, request.app.state.runtime, instance_id, user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instance_endpoint(
    instance_id: str,
    request: Request,
    confirm: bool = False,
    user: AuthenticatedUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    try:
        await delete_instance(db, request.app.state.runtime, instance_id, user.id, confirmed=confirm)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
