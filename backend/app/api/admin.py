import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.deps import get_db, require_admin
from app.services.audit_log import audit
from app.services.errors import ConflictError, ValidationFailedError
from app.services.sessions import AuthenticatedUser
from app.services.groups import (
    add_member,
    create_group,
    delete_group,
    list_granted_images,
    list_groups,
    list_members,
    remove_member,
    rename_group,
)
from app.services.instances import stop_all_running_for_user
from app.services.users import create_user, disable_user, list_users

router = APIRouter(dependencies=[Depends(require_admin)])


class CreateUserRequest(BaseModel):
    email: str
    password: str
    is_admin: bool = False


class UserResponse(BaseModel):
    id: int
    email: str
    is_admin: bool


class UserListItemResponse(BaseModel):
    id: int
    email: str
    is_admin: bool
    disabled: bool


class GrantedImageResponse(BaseModel):
    id: int
    display_name: str
    repository: str
    tag: str


class GroupMemberResponse(BaseModel):
    id: int
    email: str


class CreateGroupRequest(BaseModel):
    name: str


class RenameGroupRequest(BaseModel):
    name: str


class GroupResponse(BaseModel):
    id: int
    name: str


class AddMemberRequest(BaseModel):
    user_id: int


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    body: CreateUserRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> UserResponse:
    settings = request.app.state.settings
    try:
        user_id = create_user(
            db,
            body.email,
            body.password,
            password_min_length=settings.password_min_length,
            is_admin=body.is_admin,
        )
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit(
        "admin.user.created",
        actor_id=admin.id,
        actor_email=admin.email,
        ip=request.client.host if request.client else None,
        target=body.email,
        outcome="success",
        detail=f"is_admin={body.is_admin}",
    )
    return UserResponse(id=user_id, email=body.email, is_admin=body.is_admin)


@router.get("/users", response_model=list[UserListItemResponse])
def list_users_endpoint(db: sqlite3.Connection = Depends(get_db)) -> list[UserListItemResponse]:
    return [
        UserListItemResponse(
            id=row["id"], email=row["email"], is_admin=bool(row["is_admin"]), disabled=row["disabled_at"] is not None
        )
        for row in list_users(db)
    ]


@router.post("/users/{user_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_user_endpoint(
    user_id: int,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin),
) -> None:
    try:
        disable_user(db, user_id, requester_id=admin.id)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit(
        "admin.user.disabled",
        actor_id=admin.id,
        actor_email=admin.email,
        ip=request.client.host if request.client else None,
        target=str(user_id),
        outcome="success",
        detail="conta desabilitada e sessões revogadas",
    )
    await stop_all_running_for_user(db, request.app.state.runtime, user_id)


@router.get("/groups", response_model=list[GroupResponse])
def list_groups_endpoint(db: sqlite3.Connection = Depends(get_db)) -> list[GroupResponse]:
    return [GroupResponse(id=row["id"], name=row["name"]) for row in list_groups(db)]


@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group_endpoint(
    body: CreateGroupRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> GroupResponse:
    try:
        group_id = create_group(db, body.name)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit("admin.group.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=body.name,
          outcome="success", detail="op=criar")
    return GroupResponse(id=group_id, name=body.name)


@router.patch("/groups/{group_id}", response_model=GroupResponse)
def rename_group_endpoint(
    group_id: int,
    body: RenameGroupRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> GroupResponse:
    try:
        rename_group(db, group_id, body.name)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit("admin.group.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"grupo {group_id}",
          outcome="success", detail=f"op=renomear para {body.name}")
    return GroupResponse(id=group_id, name=body.name)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_endpoint(
    group_id: int,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    delete_group(db, group_id)
    audit("admin.group.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"grupo {group_id}",
          outcome="success", detail="op=excluir")


@router.post("/groups/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
def add_member_endpoint(
    group_id: int,
    body: AddMemberRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    add_member(db, group_id, body.user_id)
    audit("admin.group.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"grupo {group_id}",
          outcome="success", detail=f"op=adicionar membro {body.user_id}")


@router.delete("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member_endpoint(
    group_id: int,
    user_id: int,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    remove_member(db, group_id, user_id)
    audit("admin.group.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"grupo {group_id}",
          outcome="success", detail=f"op=remover membro {user_id}")


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberResponse])
def list_members_endpoint(group_id: int, db: sqlite3.Connection = Depends(get_db)) -> list[GroupMemberResponse]:
    return [GroupMemberResponse(id=row["id"], email=row["email"]) for row in list_members(db, group_id)]


@router.get("/groups/{group_id}/images", response_model=list[GrantedImageResponse])
def list_granted_images_endpoint(
    group_id: int, db: sqlite3.Connection = Depends(get_db)
) -> list[GrantedImageResponse]:
    return [
        GrantedImageResponse(
            id=row["id"], display_name=row["display_name"], repository=row["repository"], tag=row["tag"]
        )
        for row in list_granted_images(db, group_id)
    ]
