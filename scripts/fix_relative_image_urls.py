"""Fix relative image URLs in properties and property_images tables.

Relative paths like `hc_properties/.../living_room.webp` were stored before
the Cloudinary migration.  This script converts them to full Cloudinary URLs
or, if the path cannot be resolved, NULLs them out so the app shows a
placeholder instead of constructing a broken localhost URL.

Run:
    cd backend
    source .venv/bin/activate
    python scripts/fix_relative_image_urls.py          # dry-run (default)
    python scripts/fix_relative_image_urls.py --apply   # write to DB
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv(".env.dev")


def _engine():
    from sqlalchemy import create_engine

    url = os.environ["DATABASE_URL"]
    if "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url)


CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_FOLDER = "360ghar"


def _to_cloudinary_url(relative_path: str) -> str | None:
    """Attempt to build a Cloudinary URL from a relative path."""
    if not CLOUD_NAME:
        print("WARNING: CLOUDINARY_CLOUD_NAME not set; cannot build URLs, will NULL instead.")
        return None
    # Standard Cloudinary image delivery URL pattern
    # https://res.cloudinary.com/<cloud>/image/upload/<folder>/<path>
    path = relative_path.lstrip("/")
    # Legacy data may include spurious prefixes that are not part of the
    # Cloudinary public_id.  Strip them so the constructed URL is correct.
    for _prefix in ("media/",):
        if path.startswith(_prefix):
            path = path[len(_prefix):]
    return f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/{CLOUDINARY_FOLDER}/{path}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix relative image URLs in properties/property_images")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default is dry-run)")
    args = parser.parse_args()

    if not CLOUD_NAME and args.apply:
        print("ERROR: CLOUDINARY_CLOUD_NAME env var is required for --apply mode.")
        sys.exit(1)

    from sqlalchemy import text

    engine = _engine()
    with engine.begin() as conn:
        # ── Fix properties.main_image_url ──────────────────────────────
        rows = conn.execute(
            text(
                "SELECT id, main_image_url FROM properties "
                "WHERE main_image_url IS NOT NULL "
                "AND main_image_url NOT LIKE 'http://%' "
                "AND main_image_url NOT LIKE 'https://%'"
            )
        ).fetchall()

        print(f"\n[properties.main_image_url] Found {len(rows)} relative paths.")
        for row in rows:
            prop_id, old_url = row
            new_url = _to_cloudinary_url(old_url)
            action = f"SET '{new_url}'" if new_url else "SET NULL"
            print(f"  property {prop_id}: '{old_url}' -> {action}")
            if args.apply and new_url:
                conn.execute(
                    text("UPDATE properties SET main_image_url = :url WHERE id = :id"),
                    {"url": new_url, "id": prop_id},
                )
            elif args.apply:
                conn.execute(
                    text("UPDATE properties SET main_image_url = NULL WHERE id = :id"),
                    {"id": prop_id},
                )

        # ── Fix property_images.image_url ─────────────────────────────
        img_rows = conn.execute(
            text(
                "SELECT id, property_id, image_url FROM property_images "
                "WHERE image_url IS NOT NULL "
                "AND image_url NOT LIKE 'http://%' "
                "AND image_url NOT LIKE 'https://%'"
            )
        ).fetchall()

        print(f"\n[property_images.image_url] Found {len(img_rows)} relative paths.")
        for row in img_rows:
            img_id, prop_id, old_url = row
            new_url = _to_cloudinary_url(old_url)
            action = f"SET '{new_url}'" if new_url else "SET NULL"
            print(f"  image {img_id} (property {prop_id}): '{old_url}' -> {action}")
            if args.apply and new_url:
                conn.execute(
                    text("UPDATE property_images SET image_url = :url WHERE id = :id"),
                    {"url": new_url, "id": img_id},
                )
            elif args.apply:
                conn.execute(
                    text("UPDATE property_images SET image_url = NULL WHERE id = :id"),
                    {"id": img_id},
                )

        # ── Fix properties.floor_plan_url ──────────────────────────────
        fp_rows = conn.execute(
            text(
                "SELECT id, floor_plan_url FROM properties "
                "WHERE floor_plan_url IS NOT NULL "
                "AND floor_plan_url NOT LIKE 'http://%' "
                "AND floor_plan_url NOT LIKE 'https://%'"
            )
        ).fetchall()

        print(f"\n[properties.floor_plan_url] Found {len(fp_rows)} relative paths.")
        for row in fp_rows:
            prop_id, old_url = row
            new_url = _to_cloudinary_url(old_url)
            action = f"SET '{new_url}'" if new_url else "SET NULL"
            print(f"  property {prop_id}: '{old_url}' -> {action}")
            if args.apply and new_url:
                conn.execute(
                    text("UPDATE properties SET floor_plan_url = :url WHERE id = :id"),
                    {"url": new_url, "id": prop_id},
                )
            elif args.apply:
                conn.execute(
                    text("UPDATE properties SET floor_plan_url = NULL WHERE id = :id"),
                    {"id": prop_id},
                )

        # ── Fix properties.video_tour_url ──────────────────────────────
        vt_rows = conn.execute(
            text(
                "SELECT id, video_tour_url FROM properties "
                "WHERE video_tour_url IS NOT NULL "
                "AND video_tour_url NOT LIKE 'http://%' "
                "AND video_tour_url NOT LIKE 'https://%'"
            )
        ).fetchall()

        print(f"\n[properties.video_tour_url] Found {len(vt_rows)} relative paths.")
        for row in vt_rows:
            prop_id, old_url = row
            new_url = _to_cloudinary_url(old_url)
            action = f"SET '{new_url}'" if new_url else "SET NULL"
            print(f"  property {prop_id}: '{old_url}' -> {action}")
            if args.apply and new_url:
                conn.execute(
                    text("UPDATE properties SET video_tour_url = :url WHERE id = :id"),
                    {"url": new_url, "id": prop_id},
                )
            elif args.apply:
                conn.execute(
                    text("UPDATE properties SET video_tour_url = NULL WHERE id = :id"),
                    {"id": prop_id},
                )

        # ── Fix properties.virtual_tour_url ────────────────────────────
        vtt_rows = conn.execute(
            text(
                "SELECT id, virtual_tour_url FROM properties "
                "WHERE virtual_tour_url IS NOT NULL "
                "AND virtual_tour_url NOT LIKE 'http://%' "
                "AND virtual_tour_url NOT LIKE 'https://%'"
            )
        ).fetchall()

        print(f"\n[properties.virtual_tour_url] Found {len(vtt_rows)} relative paths.")
        for row in vtt_rows:
            prop_id, old_url = row
            new_url = _to_cloudinary_url(old_url)
            action = f"SET '{new_url}'" if new_url else "SET NULL"
            print(f"  property {prop_id}: '{old_url}' -> {action}")
            if args.apply and new_url:
                conn.execute(
                    text("UPDATE properties SET virtual_tour_url = :url WHERE id = :id"),
                    {"url": new_url, "id": prop_id},
                )
            elif args.apply:
                conn.execute(
                    text("UPDATE properties SET virtual_tour_url = NULL WHERE id = :id"),
                    {"id": prop_id},
                )

        if not args.apply:
            print("\n*** DRY RUN — no changes written. Re-run with --apply to commit. ***")
        else:
            print("\n*** Changes committed. ***")

        total = len(rows) + len(img_rows) + len(fp_rows) + len(vt_rows) + len(vtt_rows)
        print(f"Total rows affected: {total}")


if __name__ == "__main__":
    main()
