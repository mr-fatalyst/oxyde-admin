from oxyde_admin._version import __version__
from oxyde_admin.config import Preset, PrimaryColor, Surface


def _make_stub(name, package):
    class _Stub:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                f"{name} requires '{package}'. Install it with: pip install {package}"
            )

    _Stub.__name__ = _Stub.__qualname__ = name
    return _Stub


try:
    from oxyde_admin.adapters._fastapi import FastAPIAdmin
except ImportError:
    FastAPIAdmin = _make_stub("FastAPIAdmin", "fastapi")

try:
    from oxyde_admin.adapters._litestar import LitestarAdmin
except ImportError:
    LitestarAdmin = _make_stub("LitestarAdmin", "litestar")

try:
    from oxyde_admin.adapters._sanic import SanicAdmin
except ImportError:
    SanicAdmin = _make_stub("SanicAdmin", "sanic")

try:
    from oxyde_admin.adapters._quart import QuartAdmin
except ImportError:
    QuartAdmin = _make_stub("QuartAdmin", "quart")

try:
    from oxyde_admin.adapters._falcon import FalconAdmin
except ImportError:
    FalconAdmin = _make_stub("FalconAdmin", "falcon")


__all__ = [
    "__version__",
    "Preset",
    "PrimaryColor",
    "Surface",
    "FastAPIAdmin",
    "LitestarAdmin",
    "SanicAdmin",
    "QuartAdmin",
    "FalconAdmin",
]
