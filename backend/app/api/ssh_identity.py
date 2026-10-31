import sqlite3

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.deps import get_current_user, get_db
from app.services.instances import propagate_ssh_identity_to_live_instances
from app.services.sessions import AuthenticatedUser
from app.services.ssh_identity import get_or_create_identity, regenerate_identity

router = APIRouter()


class SshIdentityResponse(BaseModel):
    public_key: str


class RegenerateSshIdentityResponse(BaseModel):
    public_key: str
    propagation_failures: list[str]


@router.get("/me/ssh-identity", response_model=SshIdentityResponse)
def get_ssh_identity_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> SshIdentityResponse:
    settings = request.app.state.settings
    row = get_or_create_identity(db, settings, user.id)
    return SshIdentityResponse(public_key=row["public_key"])


@router.post("/me/ssh-identity/regenerate", response_model=RegenerateSshIdentityResponse)
async def regenerate_ssh_identity_endpoint(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
) -> RegenerateSshIdentityResponse:
    settings = request.app.state.settings
    runtime = request.app.state.runtime
    row = regenerate_identity(db, settings, user.id)
    failures = await propagate_ssh_identity_to_live_instances(db, runtime, settings, user.id)
    return RegenerateSshIdentityResponse(
        public_key=row["public_key"],
        propagation_failures=[f["instance_id"] for f in failures],
    )
