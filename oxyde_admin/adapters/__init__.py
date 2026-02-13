try:
    from oxyde_admin.adapters._fastapi import FastAPIAdmin
except ImportError:
    pass

__all__ = ["FastAPIAdmin"]
