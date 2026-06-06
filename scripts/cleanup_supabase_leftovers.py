#!/usr/bin/env python3
"""Clean up remaining supabase.co URLs that can't be migrated (expired signed URLs)."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger, setup_logging
from app.services.cloudinary import cloudinary_service

setup_logging()
logger = get_logger("cleanup")


async def main():
    # Upload a placeholder image
    placeholder_b64 = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    placeholder_bytes = base64.b64decode(placeholder_b64)

    result = cloudinary_service.upload_file(
        file_bytes=placeholder_bytes,
        public_id="placeholder",
        folder="misc",
        content_type="image/gif",
        is_image=True,
    )
    placeholder_url = result["secure_url"]
    logger.info("Placeholder uploaded: %s", placeholder_url)

    async with AsyncSessionLocal() as db:
        # Update remaining supabase property_images
        r = await db.execute(
            text("UPDATE property_images SET image_url = :url WHERE image_url LIKE '%%supabase.co%%' RETURNING id"),
            {"url": placeholder_url}
        )
        count = len(r.all())
        logger.info("Updated %d property_images to placeholder", count)

        # Clear supabase user profile
        r2 = await db.execute(
            text("UPDATE users SET profile_image_url = NULL WHERE profile_image_url LIKE '%%supabase.co%%' RETURNING id")
        )
        count2 = len(r2.all())
        logger.info("Cleared %d user profiles", count2)

        # Clear supabase property URLs
        r3 = await db.execute(
            text("UPDATE properties SET main_image_url = NULL WHERE main_image_url LIKE '%%supabase.co%%' RETURNING id")
        )
        count3 = len(r3.all())
        logger.info("Cleared %d property URLs", count3)

        await db.commit()

    # Upload remaining hc_properties
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            text("SELECT id, property_id, image_url FROM property_images WHERE image_url LIKE 'media/hc_properties/%%'")
        )).all()

    if rows:
        logger.info("Uploading %d remaining hc_property images...", len(rows))
        seed_dir = Path(__file__).resolve().parent.parent / "seed_data" / "hardcoded" / "properties"
        uploaded = 0
        failed = 0

        for r in rows:
            try:
                parts = r.image_url.split("/")
                hc_idx = parts.index("hc_properties")
                prop_dir = parts[hc_idx + 1]
                filename = parts[-1]
                local_path = seed_dir / prop_dir / "listing_images" / filename
                if not local_path.exists():
                    logger.warning("File not found: %s", local_path)
                    failed += 1
                    continue

                stem = Path(filename).stem
                result = cloudinary_service.upload_local_file(
                    str(local_path),
                    public_id=stem,
                    folder=f"properties/{r.property_id}",
                )

                async with AsyncSessionLocal() as db:
                    await db.execute(
                        text("UPDATE property_images SET image_url = :url WHERE id = :id"),
                        {"url": result["secure_url"], "id": r.id},
                    )
                    await db.commit()
                uploaded += 1
                if uploaded % 10 == 0:
                    logger.info("Progress: %d/%d", uploaded, len(rows))
            except Exception as e:
                logger.error("Failed pi_id=%d: %s", r.id, e)
                failed += 1

        logger.info("hc_properties done: uploaded=%d failed=%d", uploaded, failed)
    else:
        logger.info("No hc_property images remaining")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
