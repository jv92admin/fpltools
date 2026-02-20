"""Alfred FPL — Fantasy Premier League BI agent domain.

Importing this package registers the FPL domain with Alfred's core engine.
"""

from alfred.domain import register_domain


def _register():
    from alfred_fpl.domain import FPL_DOMAIN
    register_domain(FPL_DOMAIN)


_register()
