from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class PublicConfigResponse(BaseModel):
    idle_timeout_minutes: int


@router.get("/config", response_model=PublicConfigResponse)
def get_public_config(request: Request) -> PublicConfigResponse:
    """Único dado de configuração que a interface precisa sem estar
    autenticada: o limite de inatividade, para explicar por que uma
    instância aparece parada (ver specs/desktop-instances e tarefa 11.7)."""
    return PublicConfigResponse(idle_timeout_minutes=request.app.state.settings.idle_timeout_minutes)
