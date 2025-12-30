#!/usr/bin/env python3
"""
FPL Data Sync Script.

Usage:
    python scripts/sync.py                 # Full sync
    python scripts/sync.py --bootstrap     # Bootstrap only (dimensions)
    python scripts/sync.py --gameweek 15   # Specific gameweek only
    python scripts/sync.py --test          # Test connection only
"""

import argparse
import logging
import sys
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
    parser.add_argument("--bootstrap", action="store_true", 
                        help="Sync bootstrap data only")
    parser.add_argument("--gameweek", type=int, 
                        help="Sync specific gameweek")
    parser.add_argument("--test", action="store_true",
                        help="Test connection only")
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
        
        # Test mode
        if args.test:
            logger.info("Testing database connection...")
            if pipeline.db.health_check():
                logger.info("✅ Database connection successful!")
            else:
                logger.error("❌ Database connection failed!")
                sys.exit(1)
            
            logger.info("Testing FPL API connection...")
            bootstrap = pipeline.fpl.get_bootstrap()
            logger.info(f"✅ FPL API connection successful! "
                       f"({len(bootstrap.get('elements', []))} players)")
            return
        
        # Run sync
        if args.bootstrap:
            results = pipeline.run_bootstrap_sync()
        elif args.gameweek:
            results = pipeline.run_gameweek_sync(args.gameweek)
        else:
            results = pipeline.run_full_sync()
        
        logger.info("=" * 60)
        logger.info("Sync completed successfully!")
        logger.info("=" * 60)
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

