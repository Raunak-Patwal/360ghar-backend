#!/usr/bin/env python3
"""Migrate all files from Supabase Storage to Cloudinary.

Usage:
    uv run python scripts/migrate_to_cloudinary.py
    uv run python scripts/migrate_to_cloudinary.py --dry-run
    uv run python scripts/migrate_to_cloudinary.py --skip-phase2
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger, setup_logging
from app.services.cloudinary import cloudinary_service

setup_logging()
logger = get_logger("migrate_to_cloudinary")

DOWNLOAD_SEM = asyncio.Semaphore(20)
UPLOAD_SEM = asyncio.Semaphore(10)

SEED_DIR = Path(__file__).resolve().parent.parent / "seed_data"
HARDCODED_PROPERTIES_DIR = SEED_DIR / "hardcoded" / "properties"

CSV_HEADER = ["table", "record_id", "column", "old_url", "new_url"]

SUPABASE_SCAN_SPEC: list[dict[str, Any]] = [
    {"table": "property_images", "id_col": "id", "url_cols": ["image_url"]},
    {"table": "users", "id_col": "id", "url_cols": ["profile_image_url"]},
    {"table": "blog_posts", "id_col": "id", "url_cols": ["cover_image_url", "og_image_url"]},
    {"table": "properties", "id_col": "id", "url_cols": ["main_image_url", "floor_plan_url", "video_tour_url", "virtual_tour_url"]},
]

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg"})


def _rel_path(parts: list[str]) -> str:
    return "/".join(parts)


def supabase_url_to_cloudinary_folder(url: str) -> tuple[str, str]:
    """Parse a Supabase Storage URL into (folder_path, public_id).

    Recognised URL path patterns (after the bucket name):
      users/{uid}/properties/{pid}/.../{file} → folder=properties/{pid}, public_id={uuid8}-{sanitized}
      users/{uid}/avatars/{file}              → folder=avatars/{uid},     public_id={filename}
      blog-covers/{file}                      → folder=blog-covers,       public_id=blog_{stem}
      fallback                                → folder=migrated,          public_id={uuid8}-{safe_name}
    """
    filename = Path(urlparse(url).path).name or "file"
    name_stem = Path(filename).stem
    safe_name = filename.replace(" ", "_").lower()

    try:
        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")
        try:
            public_idx = path_parts.index("public")
            rel_parts = path_parts[public_idx + 2:]  # skip bucket name too
        except ValueError:
            rel_parts = path_parts[-3:] if len(path_parts) >= 3 else path_parts[-2:]
    except Exception:
        return "migrated", f"{uuid.uuid4().hex[:8]}-{safe_name}"

    if not rel_parts:
        return "migrated", f"{uuid.uuid4().hex[:8]}-{safe_name}"

    rel_path_str = _rel_path(rel_parts)

    # users/{uid}/properties/{pid}/.../{file}
    if rel_parts[0] == "users" and "/properties/" in rel_path_str:
        try:
            prop_idx = rel_parts.index("properties")
            if prop_idx + 1 < len(rel_parts):
                property_id = rel_parts[prop_idx + 1]
                sanitized = name_stem.replace(" ", "_").lower()
                public_id = f"{uuid.uuid4().hex[:8]}-{sanitized}"
                return f"properties/{property_id}", public_id
        except ValueError:
            pass

    # users/{uid}/avatars/{file}
    if rel_parts[0] == "users" and ("/avatars/" in rel_path_str or rel_parts[-2] == "avatars"):
        try:
            user_id = rel_parts[1]
            return f"avatars/{user_id}", filename
        except IndexError:
            pass

    # blog-covers/{file}
    if rel_parts[0] == "blog-covers":
        return "blog-covers", f"blog_{name_stem}"

    return "migrated", f"{uuid.uuid4().hex[:8]}-{safe_name}"


async def download_file(url: str, timeout: int = 120) -> bytes | None:
    """Download a file from URL with rate limiting."""
    async with DOWNLOAD_SEM:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            logger.error("Download failed: %s — %s", url, e)
            return None


async def process_supabase_record(
    table: str,
    record_id: Any,
    column: str,
    old_url: str,
    dry_run: bool,
    csv_rows: list[dict[str, str]],
    stats: dict[str, int],
) -> None:
    """Download from Supabase URL, upload to Cloudinary, update DB."""
    if dry_run:
        folder, public_id = supabase_url_to_cloudinary_folder(old_url)
        logger.info(
            "[DRY RUN] Would migrate %s.%s[%s]: %s → folder=%s pid=%s",
            table, column, record_id, old_url[:60], folder, public_id,
        )
        stats["dry_run_skipped"] += 1
        return

    file_bytes = await download_file(old_url)
    if file_bytes is None:
        stats["download_failed"] += 1
        return

    folder, public_id = supabase_url_to_cloudinary_folder(old_url)
    ext = Path(urlparse(old_url).path).suffix.lower()
    is_image = ext in IMAGE_EXTENSIONS

    try:
        async with UPLOAD_SEM:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: cloudinary_service.upload_file(
                    file_bytes,
                    public_id=public_id,
                    folder=folder,
                    is_image=is_image,
                    overwrite=True,
                ),
            )
        new_url = result["secure_url"]
    except Exception as e:
        logger.error("Upload failed for %s: %s", old_url, e)
        stats["upload_failed"] += 1
        return

    async with AsyncSessionLocal() as db:
        try:
            quoted_table = f'"{table}"'
            quoted_col = f'"{column}"'
            stmt = text(f"UPDATE {quoted_table} SET {quoted_col} = :new_url WHERE \"id\" = :record_id")
            await db.execute(stmt, {"new_url": new_url, "record_id": record_id})
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error("DB update failed for %s.%s[%s]: %s", table, column, record_id, e)
            stats["db_update_failed"] += 1
            return

    csv_rows.append({"table": table, "record_id": str(record_id), "column": column, "old_url": old_url, "new_url": new_url})
    stats["migrated"] += 1
    if stats["migrated"] % 50 == 0:
        logger.info("Progress: %d records migrated", stats["migrated"])


async def phase1_migrate_supabase_files(
    dry_run: bool,
    csv_rows: list[dict[str, str]],
    stats: dict[str, int],
) -> None:
    """Phase 1 — Migrate existing Supabase Storage files to Cloudinary."""
    logger.info("=== Phase 1: Migrating Supabase Storage files ===")

    for spec in SUPABASE_SCAN_SPEC:
        table = spec["table"]
        id_col = spec["id_col"]
        url_cols = spec["url_cols"]

        conditions = " OR ".join(
            f'"{c}" LIKE \'%supabase.co%\' AND "{c}" IS NOT NULL' for c in url_cols
        )
        selected = ", ".join(
            [f'"{id_col}" AS _id'] + [f'"{c}"' for c in url_cols]
        )
        query = f"SELECT {selected} FROM \"{table}\" WHERE {conditions}"

        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(text(query))
                rows = result.fetchall()
            except Exception as e:
                logger.error("Query failed for table %s: %s", table, e)
                continue

        if not rows:
            logger.info("  Table %s: no supabase URLs found", table)
            continue

        logger.info("  Table %s: found %d records with supabase URLs", table, len(rows))

        tasks: list[asyncio.Task[None]] = []
        for row in rows:
            record_id = row._mapping["_id"]
            for col in url_cols:
                url = row._mapping[col]
                if url and "supabase.co" in str(url):
                    tasks.append(
                        asyncio.create_task(
                            process_supabase_record(table, record_id, col, str(url), dry_run, csv_rows, stats)
                        )
                    )

        batch_size = 20
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            await asyncio.gather(*batch)

    logger.info("Phase 1 complete: %s", _summary_str(stats))


async def phase2_upload_hc_property_images(
    dry_run: bool,
    csv_rows: list[dict[str, str]],
    stats: dict[str, int],
) -> None:
    """Phase 2 — Upload missing seed property images to Cloudinary.

    Scans property_images where image_url LIKE 'media/hc_properties/%',
    reads the corresponding local file and uploads it.
    """
    logger.info("=== Phase 2: Uploading hardcoded property images ===")

    query = """
        SELECT pi."id", pi."image_url", pi."property_id"
        FROM property_images pi
        WHERE pi."image_url" LIKE 'media/hc_properties/%'
    """

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(text(query))
            rows = result.fetchall()
        except Exception as e:
            logger.error("Phase 2 query failed: %s", e)
            return

    if not rows:
        logger.info("  No hardcoded property images found")
        return

    logger.info("  Found %d hardcoded property images to upload", len(rows))

    for row in rows:
        row_id = row._mapping["id"]
        image_url = row._mapping["image_url"]
        property_id = row._mapping["property_id"]

        if dry_run:
            logger.info(
                "[DRY RUN] Would upload hc_property image %s[%s]: %s",
                row_id, property_id, image_url,
            )
            stats["dry_run_skipped"] += 1
            continue

        # Parse URL: media/hc_properties/{prop_dir}/listing_images/{filename}
        url_path = image_url.split("?")[0]
        parts = url_path.strip("/").split("/")

        if len(parts) < 4:
            logger.warning("  Cannot parse URL, skipping: %s", image_url)
            stats["parse_failed"] += 1
            continue

        # parts = ['media', 'hc_properties', '<prop_dir>', 'listing_images', '<filename>']
        # or: ['media', 'hc_properties', '<prop_dir>', 'floor_plan.png']
        try:
            hc_idx = parts.index("hc_properties")
        except ValueError:
            logger.warning("  No hc_properties in path, skipping: %s", image_url)
            stats["parse_failed"] += 1
            continue

        prop_dir = parts[hc_idx + 1] if hc_idx + 1 < len(parts) else ""
        filename = parts[-1] if parts else ""

        if not prop_dir or not filename:
            logger.warning("  Cannot extract prop_dir/filename, skipping: %s", image_url)
            stats["parse_failed"] += 1
            continue

        local_file = HARDCODED_PROPERTIES_DIR / prop_dir / "listing_images" / filename
        if not local_file.exists():
            logger.warning("  Local file not found: %s (for URL: %s)", local_file, image_url)
            stats["local_file_missing"] += 1
            continue

        public_id = Path(filename).stem

        file_bytes = local_file.read_bytes()
        ext = Path(filename).suffix.lower()
        is_image = ext in IMAGE_EXTENSIONS
        try:
            async with UPLOAD_SEM:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda fb=file_bytes, pid=public_id, fold=f"properties/{property_id}", img=is_image: cloudinary_service.upload_file(
                        fb,
                        public_id=pid,
                        folder=fold,
                        is_image=img,
                        overwrite=True,
                    ),
                )
            new_url = result["secure_url"]
        except Exception as e:
            logger.error("Upload failed for %s: %s", image_url, e)
            stats["upload_failed"] += 1
            continue

        async with AsyncSessionLocal() as db:
            try:
                stmt = text('UPDATE property_images SET "image_url" = :new_url WHERE "id" = :row_id')
                await db.execute(stmt, {"new_url": new_url, "row_id": row_id})
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error("DB update failed for property_images[%s]: %s", row_id, e)
                stats["db_update_failed"] += 1
                continue

        csv_rows.append({
            "table": "property_images",
            "record_id": str(row_id),
            "column": "image_url",
            "old_url": image_url,
            "new_url": new_url,
        })
        stats["migrated"] += 1
        if stats["migrated"] % 50 == 0:
            logger.info("Progress: %d records migrated", stats["migrated"])

    logger.info("Phase 2 complete: %s", _summary_str(stats))


def _summary_str(stats: dict[str, int]) -> str:
    return (
        f"migrated={stats['migrated']}, "
        f"download_failed={stats['download_failed']}, "
        f"upload_failed={stats['upload_failed']}, "
        f"db_update_failed={stats['db_update_failed']}, "
        f"dry_run_skipped={stats['dry_run_skipped']}, "
        f"parse_failed={stats.get('parse_failed', 0)}, "
        f"local_file_missing={stats.get('local_file_missing', 0)}"
    )


def write_csv(csv_rows: list[dict[str, str]], filepath: str) -> None:
    logger.info("Writing CSV mapping to %s", filepath)
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(csv_rows)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate files from Supabase Storage to Cloudinary")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without uploading")
    parser.add_argument("--skip-phase2", action="store_true", help="Skip Phase 2 (hardcoded property images)")
    args = parser.parse_args()

    csv_rows: list[dict[str, str]] = []
    stats: dict[str, int] = {
        "migrated": 0,
        "download_failed": 0,
        "upload_failed": 0,
        "db_update_failed": 0,
        "dry_run_skipped": 0,
    }

    logger.info("Starting migration (dry_run=%s, skip_phase2=%s)", args.dry_run, args.skip_phase2)

    await phase1_migrate_supabase_files(args.dry_run, csv_rows, stats)

    if not args.skip_phase2:
        await phase2_upload_hc_property_images(args.dry_run, csv_rows, stats)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = f"cloudinary_migration_{timestamp}.csv"
    write_csv(csv_rows, csv_path)

    print()
    print("=" * 60)
    print("  MIGRATION COMPLETE")
    print("=" * 60)
    print(f"  {'Migrated/DRY:':<20} {stats['migrated'] + stats['dry_run_skipped']}")
    print(f"  {'Download failed:':<20} {stats['download_failed']}")
    print(f"  {'Upload failed:':<20} {stats['upload_failed']}")
    print(f"  {'DB update failed:':<20} {stats['db_update_failed']}")
    print(f"  {'CSV mapping:':<20} {csv_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
