import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.deps import get_db, require_admin
from app.services.access_control import grant, preview_revoke, revoke
from app.services.instances import stop_instance

router = APIRouter(dependencies=[Depends(require_admin)])


class GrantImageRequest(BaseModel):
    image_id: int


class RevokePreviewResponse(BaseModel):
    affected_instance_count: int


@router.post("/groups/{group_id}/images", status_code=status.HTTP_204_NO_CONTENT)
def grant_image_endpoint(
    group_id: int, body: GrantImageRequest, db: sqlite3.Connection = Depends(get_db)
) -> None:
    grant(db, group_id, body.image_id)


@router.get("/groups/{group_id}/images/{image_id}/revoke-preview", response_model=RevokePreviewResponse)
def revoke_preview_endpoint(
    group_id: int, image_id: int, db: sqlite3.Connection = Depends(get_db)
) -> RevokePreviewResponse:
    """Só informa o impacto; não altera nada — a revogação em si exige
    outra chamada, confirmada explicitamente pelo administrador."""
    affected = preview_revoke(db, group_id, image_id)
    return RevokePreviewResponse(affected_instance_count=len(affected))


@router.delete("/groups/{group_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_image_endpoint(
    group_id: int,
    image_id: int,
    request: Request,
    confirm: bool = False,
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    if not confirm:
        # mesma convenção de desktop-instances: operação com perda de
        # acesso exige confirmação explícita, não acontece por padrão.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="revogação requer confirmação explícita"
        )

    affected = revoke(db, group_id, image_id)
    runtime = request.app.state.runtime
    for row in affected:
        await stop_instance(db, runtime, row["id"], row["user_id"])
