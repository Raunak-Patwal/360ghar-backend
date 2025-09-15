"""
Page data populator for creating/updating CMS-like pages from JSON
"""
from __future__ import annotations

import json
import os
from typing import Optional, List, Dict, Any

from sqlalchemy import select, delete, update

# Ensure project root is on path (similar to other populators)
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.logging import get_logger
from app.models.models import Page
from app.models.enums import PageFormat
from .base import BasePopulator


logger = get_logger(__name__)


class PagePopulator(BasePopulator):
    """Populates pages from a JSON file."""

    def __init__(self):
        super().__init__()

    def _default_pages_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # populate_data/
        return os.path.join(base_dir, "data", "pages.json")

    def _load_pages_from_file(self, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        path = file_path or self._default_pages_path()
        if not os.path.exists(path):
            raise FileNotFoundError(f"Pages JSON not found at: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("pages.json must contain a list of page objects")
        return data

    async def populate(
        self,
        count: Optional[int] = None,
        file_path: Optional[str] = None,
        update_existing: bool = False,
    ) -> int:
        """
        Create (and optionally update) pages from JSON.

        Args:
            count: Unused. Present for BasePopulator compatibility.
            file_path: Optional path to pages.json. Defaults to populate_data/data/pages.json
            update_existing: If True, update existing pages instead of skipping.

        Returns:
            Number of pages created (not counting updates).
        """
        pages_data = self._load_pages_from_file(file_path)
        created_count = 0
        updated_count = 0

        async with await self.get_db_session() as session:
            try:
                for page in pages_data:
                    unique_name = page.get("unique_name")
                    if not unique_name:
                        self.logger.warning("Skipping page without 'unique_name'")
                        continue

                    # Normalize/validate format
                    fmt_value = page.get("format", "html")
                    try:
                        page_format = PageFormat(fmt_value)
                    except Exception:
                        self.logger.warning(
                            f"Invalid format '{fmt_value}' for page '{unique_name}'; defaulting to 'html'"
                        )
                        page_format = PageFormat.html

                    # Check existing by unique_name
                    result = await session.execute(
                        select(Page).where(Page.unique_name == unique_name)
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        if update_existing:
                            # Prepare update fields
                            update_fields: Dict[str, Any] = {
                                "title": page.get("title", existing.title),
                                "content": page.get("content", existing.content),
                                "format": page_format,
                                "is_active": page.get("is_active", existing.is_active),
                                "is_draft": page.get("is_draft", existing.is_draft),
                                "is_private": page.get("is_private", getattr(existing, "is_private", True)),
                            }
                            if "custom_config" in page:
                                update_fields["custom_config"] = page.get("custom_config")

                            await session.execute(
                                update(Page)
                                .where(Page.id == existing.id)
                                .values(**update_fields)
                            )
                            updated_count += 1
                            self.logger.debug(f"Updated page: {unique_name}")
                        else:
                            self.logger.debug(
                                f"Page '{unique_name}' already exists, skipping (use --update to update)."
                            )
                        continue

                    # Create new page
                    new_page = Page(
                        unique_name=unique_name,
                        title=page.get("title", unique_name.replace("-", " ").title()),
                        content=page.get("content", ""),
                        format=page_format,
                        custom_config=page.get("custom_config"),
                        is_active=page.get("is_active", True),
                        is_draft=page.get("is_draft", False),
                        is_private=page.get("is_private", True),
                    )
                    session.add(new_page)
                    created_count += 1
                    self.logger.debug(f"Created page: {unique_name}")

                await session.commit()
                self.logger.info(
                    f"Pages processed. Created: {created_count}, Updated: {updated_count}"
                )
                return created_count

            except Exception as e:
                await session.rollback()
                self.logger.error(f"Failed to populate pages: {str(e)}")
                raise

    async def clear_all(self) -> int:
        """Delete all pages."""
        try:
            async with await self.get_db_session() as session:
                result = await session.execute(delete(Page))
                deleted = result.rowcount or 0
                await session.commit()
                self.logger.info(f"Deleted {deleted} pages")
                return deleted
        except Exception as e:
            logger.error(f"Failed to clear pages: {str(e)}")
            return 0
