from .models import FetchRequest, FetchResult, SUPPORTED_FORMATS
from .pipeline import FetchPipeline, fetch


def __getattr__(name):
    if name != "Carnivore":
        raise AttributeError(name)
    from .lib import Carnivore

    globals()[name] = Carnivore
    return Carnivore


__all__ = [
    "Carnivore",
    "FetchPipeline",
    "FetchRequest",
    "FetchResult",
    "SUPPORTED_FORMATS",
    "fetch",
]
