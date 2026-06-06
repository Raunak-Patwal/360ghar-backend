#!/usr/bin/env python3
"""Fast upload remaining hardcoded property images to Cloudinary."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger, setup_logging
from app.services.cloudinary import cloudinary_service

setup_logging()
logger = get_logger("upload_hc")

UPLOAD_SEM = asyncio.Semaphore(20)
SEED_DIR = Path(__file__).resolve().parent.parent / "seed_data"
HARDCODED_DIR = SEED_DIR / "hardcoded" / "properties"


async def process_one(pi_id: int, property_id: int, image_url: str, stats: dict) -> None:
    async with UPLOAD_SEM:
        try:
            # media/hc_properties/{prop_dir}/listing_images/{filename}
            parts = image_url.split("/")
            hc_idx = parts.index("hc_properties")
            prop_dir = parts[hc_idx + 1]
            filename = parts[-1]

            local_path = HARDCODED_DIR / prop_dir / "listing_images" / filename
            if not local_path.exists():
                logger.warning("File not found: %s", local_path)
                stats["missing"] += 1
                return

            stem = Path(filename).stem
            folder = f"properties/{property_id}"

            result = cloudinary_service.upload_local_file(
                str(local_path),
                public_id=stem,
                folder=folder,
            )

            async with AsyncSessionLocal() as db:
                await db.execute(
                    text("UPDATE property_images SET image_url = :url WHERE id = :id"),
                    {"url": result["secure_url"], "id": pi_id},
                )
                await db.commit()

            stats["uploaded"] += 1
            if stats["uploaded"] % 50 == 0:
                logger.info("Progress: %d / %d uploaded", stats["uploaded"], stats["total"])

        except Exception as e:
            logger.error("Failed pi_id=%d: %s", pi_id, e)
            stats["failed"] += 1


async def main():
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            text("SELECT id, property_id, image_url FROM property_images WHERE image_url LIKE 'media/hc_properties/%'")
        )).all()

    stats = {"uploaded": 0, "failed": 0, "missing": 0, "total": len(rows)}
    logger.info("Found %d hardcoded property images to upload", len(rows))

    tasks = [process_one(r.id, r.property_id, r.image_url, stats) for r in rows]
    await asyncio.gather(*tasks)

    logger.info("Done: uploaded=%d failed=%d missing=%d total=%d",
                stats["uploaded"], stats["failed"], stats["missing"], stats["total"])


if __name__ == "__main__":
    asyncio.run(main())
