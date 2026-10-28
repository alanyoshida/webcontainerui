class ConflictError(Exception):
    """Operação recusada por violar uma restrição de unicidade."""


class NotFoundError(Exception):
    """Recurso referenciado não existe."""


class ValidationFailedError(Exception):
    """Entrada recusada por não atender a uma regra de negócio."""


class PermissionDeniedError(Exception):
    """Operação recusada por falta de permissão sobre o recurso."""


class InstanceNotRunningError(Exception):
    """A instância existe e pertence ao usuário, mas não está em execução."""
