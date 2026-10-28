class ContainerNotFoundError(Exception):
    """O container referenciado não existe no runtime."""


class RuntimeOperationError(Exception):
    """A operação de runtime falhou por um motivo que não é ausência do recurso."""
