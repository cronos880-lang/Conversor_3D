"""Errores de etapa legibles, manteniendo compatibilidad con ValueError."""
class PipelineError(ValueError):
    code = 'pipeline_rejected'


class NativeWorkerError(PipelineError):
    code = 'native_worker_rejected'


class FinalValidationError(PipelineError):
    code = 'final_validation_rejected'
