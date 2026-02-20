#!/usr/bin/env python3
"""
FPL Data Sync Script.

Usage:
    python scripts/sync.py                     # Full sync (bootstrap + current GW)
    python scripts/sync.py --bootstrap         # Bootstrap only (dimensions)
    python scripts/sync.py --gw 15             # Specific gameweek only
    python scripts/sync.py --from-gw 1         # Backfill from GW 1 to current
    python scripts/sync.py --from-gw 1 --to-gw 10  # Backfill range
    python scripts/sync.py --test              # Test connections only
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.pipeline import Pipeline


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main():
    parser = argparse.ArgumentParser(description="FPL Data Sync")

    # Mode flags
    parser.add_argument("--bootstrap", action="store_true",
                        help="Sync bootstrap data only (positions, teams, players, fixtures)")
    parser.add_argument("--test", action="store_true",
                        help="Test connections only")

    # Gameweek selection
    parser.add_argument("--gw", type=int,
                        help="Sync specific gameweek only")
    parser.add_argument("--from-gw", type=int, dest="from_gw",
                        help="Backfill starting from this gameweek")
    parser.add_argument("--to-gw", type=int, dest="to_gw",
                        help="Backfill ending at this gameweek (default: current)")

    # Options
    parser.add_argument("--skip-picks", action="store_true", dest="skip_picks",
                        help="Skip manager squads/transfers (faster for bulk backfill)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = Config.load()
        logger.info(f"League ID: {config.fpl.league_id or 'Not configured'}")
        logger.info(f"Manager ID: {config.fpl.manager_id or 'Not configured'}")

        # Initialize pipeline
        pipeline = Pipeline(config)

        # =================================================================
        # TEST MODE
        # =================================================================
        if args.test:
            logger.info("Testing database connection...")
            if pipeline.db.health_check():
                logger.info("Database connection successful!")
            else:
                logger.error("Database connection failed!")
                sys.exit(1)

            logger.info("Testing FPL API connection...")
            bootstrap = pipeline.fpl.get_bootstrap()
            logger.info(f"FPL API connection successful! "
                       f"({len(bootstrap.get('elements', []))} players)")
            return

        # =================================================================
        # BOOTSTRAP ONLY
        # =================================================================
        if args.bootstrap:
            pipeline.run_bootstrap_sync()
            logger.info("Bootstrap sync complete!")
            return

        # =================================================================
        # DETERMINE GAMEWEEK RANGE
        # =================================================================
        current_gw = pipeline.fpl.get_current_gameweek()
        current_gw_num = current_gw.id if current_gw else 1
        logger.info(f"Current gameweek: {current_gw_num}")

        # Single GW mode
        if args.gw:
            gw_start = args.gw
            gw_end = args.gw
        # Backfill range mode
        elif args.from_gw:
            gw_start = args.from_gw
            gw_end = args.to_gw if args.to_gw else current_gw_num
        # Default: current GW only
        else:
            gw_start = current_gw_num
            gw_end = current_gw_num

        # Validate range
        gw_start = max(1, min(gw_start, 38))
        gw_end = max(1, min(gw_end, current_gw_num))

        if gw_start > gw_end:
            gw_start, gw_end = gw_end, gw_start

        total_gws = gw_end - gw_start + 1

        # =================================================================
        # RUN SYNC
        # =================================================================
        logger.info("=" * 60)
        if total_gws == 1:
            logger.info(f"Syncing GW{gw_start}...")
        else:
            logger.info(f"Syncing GW{gw_start} to GW{gw_end} ({total_gws} gameweeks)...")
        logger.info("=" * 60)

        # Always sync bootstrap first (dimensions + UUID lookups)
        pipeline.run_bootstrap_sync()

        # Sync each gameweek
        for gw in range(gw_start, gw_end + 1):
            logger.info("-" * 40)
            logger.info(f"Processing GW{gw} ({gw - gw_start + 1}/{total_gws})...")
            logger.info("-" * 40)

            # Player stats for this GW
            pipeline.sync_player_gw_stats(gw)

            # League standings snapshot
            pipeline.sync_league_standings(gameweek=gw)

            # Manager squads, history, and transfers
            if not args.skip_picks:
                pipeline.sync_squads(gameweek=gw)
                pipeline.sync_manager_history()
                pipeline.sync_manager_transfers()

            # Rate limit between gameweeks during backfill
            if total_gws > 1 and gw < gw_end:
                logger.info("Waiting 2s before next gameweek...")
                time.sleep(2)

        logger.info("=" * 60)
        logger.info("Sync completed successfully!")
        logger.info("=" * 60)

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Sync interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
