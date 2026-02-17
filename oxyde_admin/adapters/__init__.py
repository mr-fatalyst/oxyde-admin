__all__: list[str] = []

try:
    from oxyde_admin.adapters._fastapi import FastAPIAdmin

    __all__.append("FastAPIAdmin")
except ImportError:
    pass

try:
    from oxyde_admin.adapters._litestar import LitestarAdmin

    __all__.append("LitestarAdmin")
except ImportError:
    pass
