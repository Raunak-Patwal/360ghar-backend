"""
Tests for upload endpoints.
"""

from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestUploadFileEndpoint:
    """Tests for POST /api/v1/upload/ endpoint."""

    @pytest.mark.asyncio
    async def test_upload_file_success(self, authenticated_client: AsyncClient):
        """Test successful file upload."""
        with patch(
            "app.api.api_v1.endpoints.upload.storage_service"
        ) as mock_storage:
            mock_storage.upload_and_track = AsyncMock(
                return_value={
                    "public_url": "https://storage.example.com/file.jpg",
                    "path": "users/1/uploads/file.jpg",
                }
            )

            # Create a test file
            file_content = b"test file content"
            files = {"file": ("test.jpg", BytesIO(file_content), "image/jpeg")}

            response = await authenticated_client.post(
                "/api/v1/upload/",
                files=files,
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["public_url"] == "https://storage.example.com/file.jpg"

    @pytest.mark.asyncio
    async def test_upload_file_unauthorized(self, client: AsyncClient):
        """Test upload without authentication."""
        file_content = b"test file content"
        files = {"file": ("test.jpg", BytesIO(file_content), "image/jpeg")}

        response = await client.post(
            "/api/v1/upload/",
            files=files,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_image_file(self, authenticated_client: AsyncClient):
        """Test uploading an image file."""
        with patch(
            "app.api.api_v1.endpoints.upload.storage_service"
        ) as mock_storage:
            mock_storage.upload_and_track = AsyncMock(
                return_value={
                    "public_url": "https://storage.example.com/image.png",
                    "mime_type": "image/png",
                }
            )

            file_content = b"\x89PNG\r\n\x1a\n"  # PNG header
            files = {"file": ("image.png", BytesIO(file_content), "image/png")}

            response = await authenticated_client.post(
                "/api/v1/upload/",
                files=files,
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["public_url"].endswith("image.png")

    @pytest.mark.asyncio
    async def test_upload_pdf_file(self, authenticated_client: AsyncClient):
        """Test uploading a PDF file."""
        with patch(
            "app.api.api_v1.endpoints.upload.storage_service"
        ) as mock_storage:
            mock_storage.upload_and_track = AsyncMock(
                return_value={
                    "public_url": "https://storage.example.com/document.pdf",
                    "mime_type": "application/pdf",
                }
            )

            file_content = b"%PDF-1.4"
            files = {"file": ("document.pdf", BytesIO(file_content), "application/pdf")}

            response = await authenticated_client.post(
                "/api/v1/upload/",
                files=files,
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["public_url"].endswith("document.pdf")
