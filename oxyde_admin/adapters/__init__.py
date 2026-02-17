try:
    from oxyde_admin.adapters._fastapi import FastAPIAdmin
except ImportError:
    pass

try:
    from oxyde_admin.adapters._litestar import LitestarAdmin
except ImportError:
    pass

__all__ = ["FastAPIAdmin", "LitestarAdmin"]
