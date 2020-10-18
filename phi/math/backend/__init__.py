from ._backend import Backend
from ._dynamic_backend import DYNAMIC_BACKEND, set_precision, NoBackendFound
from ._scipy_backend import SCIPY_BACKEND, SciPyBackend

DYNAMIC_BACKEND.add_backend(SCIPY_BACKEND)
DYNAMIC_BACKEND.default_backend = SCIPY_BACKEND
math = DYNAMIC_BACKEND
