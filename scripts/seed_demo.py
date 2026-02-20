#!/usr/bin/env python3
"""
Seed a demo user with manager_links for development.

Creates a Supabase auth user and populates manager_links with the
configured manager ID, rival IDs, and league ID from .env. This
gives the Alfred session bootstrap something to query when it builds
the manager_bridge.

Usage:
    python scripts/seed_demo.py              # Create user + seed links
    python scripts/seed_demo.py --check      # Just check what exists

NOTE: If Supabase has email confirmation enabled, you'll need to either:
  - Disable it: Auth > Settings > Enable email confirmations = OFF
  - Or create the user via Supabase Dashboard (auto-confirms)
    then re-run this script to sign in and seed the links.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.fpl_client import FPLClient
from supabase import create_client

# Dev-only credentials. Not sensitive — this user only exists in your
# local Supabase project and has no privileges beyond RLS-scoped CRUD.
DEMO_EMAIL = "ryesvptest@gmail.com"
DEMO_PASSWORD = "demo-fpl-2025"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_manager_label(fpl: FPLClient, manager_id: int) -> str:
    """Fetch a human-readable label for a manager from the FPL API."""
    try:
        profile = fpl.get_manager(manager_id)
        first = profile.get("player_first_name", "")
        last = profile.get("player_last_name", "")
        name = f"{first} {last}".strip()
        team = profile.get("name", "")
        if name:
            return name
        if team:
            return team
        return f"Manager {manager_id}"
    except Exception:
        return f"Manager {manager_id}"


def get_or_create_demo_user(client):
    """Sign up or sign in the demo user. Returns the user object."""
    # Try sign-up first
    try:
        logger.info(f"Signing up {DEMO_EMAIL}...")
        res = client.auth.sign_up({"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        if res.user and res.session:
            logger.info("Demo user created and signed in")
            return res.user
        # sign_up succeeded but no session = email confirmation required
        if res.user and not res.session:
            logger.warning(
                "User created but email confirmation is required. "
                "Disable email confirmation in Supabase Auth settings, "
                "or confirm the user via the Supabase Dashboard, then re-run."
            )
            sys.exit(1)
    except Exception as e:
        err = str(e)
        if "already registered" in err.lower() or "already been registered" in err.lower():
            logger.info("Demo user already exists, signing in...")
        else:
            logger.warning(f"Sign-up failed ({err}), trying sign-in...")

    # Try sign-in
    try:
        res = client.auth.sign_in_with_password(
            {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
        )
        if res.user:
            logger.info("Signed in as demo user")
            return res.user
    except Exception as e:
        logger.error(f"Sign-in failed: {e}")
        sys.exit(1)

    logger.error("Could not create or sign in demo user")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Seed demo user with manager links")
    parser.add_argument("--check", action="store_true", help="Just check current state")
    args = parser.parse_args()

    config = Config.load()
    client = create_client(config.supabase.url, config.supabase.key)

    if args.check:
        # Check without auth — won't see RLS-protected rows, but shows if table works
        logger.info("Checking manager_links table...")
        try:
            rows = client.table("manager_links").select("*").execute()
            logger.info(f"Found {len(rows.data)} rows (note: RLS may hide rows without auth)")
            for row in rows.data:
                logger.info(f"  {row.get('label')}: FPL ID {row.get('fpl_manager_id')} "
                          f"(primary={row.get('is_primary')})")
        except Exception as e:
            logger.error(f"Error: {e}")
        return

    # ---- Create/sign-in demo user ----
    user = get_or_create_demo_user(client)
    user_id = user.id
    logger.info(f"Demo user ID: {user_id}")

    # ---- Fetch manager labels from FPL API ----
    fpl = FPLClient()
    links = []

    if config.fpl.manager_id:
        label = get_manager_label(fpl, config.fpl.manager_id)
        links.append({
            "user_id": user_id,
            "fpl_manager_id": config.fpl.manager_id,
            "is_primary": True,
            "label": label,
            "league_id": config.fpl.league_id,
        })
        logger.info(f"Primary manager: {label} (ID {config.fpl.manager_id})")
        fpl._rate_limit()

    for rival_id in (config.fpl.rival_ids or []):
        label = get_manager_label(fpl, rival_id)
        links.append({
            "user_id": user_id,
            "fpl_manager_id": rival_id,
            "is_primary": False,
            "label": label,
            "league_id": config.fpl.league_id,
        })
        logger.info(f"Rival: {label} (ID {rival_id})")
        fpl._rate_limit()

    if not links:
        logger.warning("No manager IDs configured in .env — nothing to seed")
        return

    # ---- Upsert manager_links ----
    logger.info(f"Seeding {len(links)} manager links...")
    try:
        result = (
            client.table("manager_links")
            .upsert(links, on_conflict="user_id,fpl_manager_id")
            .execute()
        )
        logger.info(f"Seeded {len(result.data)} manager links:")
        for row in result.data:
            primary = " (PRIMARY)" if row.get("is_primary") else ""
            logger.info(f"  {row['label']}: FPL ID {row['fpl_manager_id']}{primary}")
    except Exception as e:
        logger.error(f"Failed to seed manager_links: {e}")
        logger.error(
            "If this is an RLS error, make sure the user_id in the data "
            "matches the authenticated user (auth.uid())."
        )
        sys.exit(1)

    logger.info("Done! manager_links seeded for demo user.")


if __name__ == "__main__":
    main()
