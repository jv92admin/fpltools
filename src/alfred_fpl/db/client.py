"""Supabase client wrapper.

The Supabase client satisfies Alfred's DatabaseAdapter protocol —
it has .table() and .rpc() methods. No wrapper class needed.

Two client types:
- Service client: bypasses RLS, for pipeline/background tasks
- Authenticated client: respects RLS, for user requests
"""

from supabase import create_client

_service_client = None


def get_service_client():
    """Return Supabase service client (bypasses RLS)."""
    global _service_client
    if _service_client is None:
        from alfred_fpl.config import settings
        if settings.supabase_service_role_key:
            _service_client = create_client(
                settings.supabase_url, settings.supabase_service_role_key
            )
        else:
            _service_client = create_client(
                settings.supabase_url, settings.supabase_key
            )
    return _service_client


def get_client():
    """Return the default Supabase client (matches DatabaseAdapter protocol)."""
    return get_service_client()
