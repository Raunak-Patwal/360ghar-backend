"""
Google Gemini AI Provider with Vision support.

This module implements the AIProvider interface for Google's Gemini models,
supporting both text and vision (image) inputs.
"""

import json
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.logging import get_logger
from app.services.ai.base import (
    AIMessage,
    AIProvider,
    AIProviderConfig,
    AIProviderError,
    AIRole,
    VisionInput,
)

logger = get_logger(__name__)


class GeminiProvider(AIProvider):
    """
    Google Gemini AI provider with vision support.

    Supports models like:
    - gemini-3-flash-preview (recommended for all tasks including vision)
    """

    # Gemini API base URL
    API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    @property
    def name(self) -> str:
        return "Google Gemini"

    @property
    def supports_vision(self) -> bool:
        return True

    @property
    def supports_json_mode(self) -> bool:
        return True

    def _build_url(self, action: str = "generateContent") -> str:
        """Build the API URL for the configured model."""
        return f"{self.API_BASE_URL}/{self.config.model}:{action}?key={self.config.api_key}"

    def _build_contents(
        self,
        messages: List[AIMessage],
        vision_input: Optional[VisionInput] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build the contents array for Gemini API.

        Gemini uses a different format than OpenAI-style APIs:
        - System messages go into system_instruction
        - User/Assistant messages go into contents
        """
        contents = []

        for msg in messages:
            if msg.role == AIRole.SYSTEM:
                # System messages are handled separately in Gemini
                continue

            role = "user" if msg.role == AIRole.USER else "model"
            parts = []

            # Add text content
            if msg.content:
                parts.append({"text": msg.content})

            # Add vision input only to user messages
            if vision_input and msg.role == AIRole.USER:
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": vision_input.mime_type,
                            "data": vision_input.image_base64,
                        }
                    }
                )

            if parts:
                contents.append({"role": role, "parts": parts})

        return contents

    def _extract_system_instruction(self, messages: List[AIMessage]) -> Optional[str]:
        """Extract system instruction from messages."""
        for msg in messages:
            if msg.role == AIRole.SYSTEM:
                return msg.content
        return None

    def _build_generation_config(self, json_mode: bool = False) -> Dict[str, Any]:
        """Build generation configuration."""
        config = {
            "temperature": self.config.temperature,
            "maxOutputTokens": self.config.max_tokens,
        }
        if json_mode:
            config["responseMimeType"] = "application/json"
        return config

    async def complete(
        self,
        messages: List[AIMessage],
        vision_input: Optional[VisionInput] = None,
    ) -> str:
        """Generate a text completion from Gemini."""
        url = self._build_url()

        payload: Dict[str, Any] = {
            "contents": self._build_contents(messages, vision_input),
            "generationConfig": self._build_generation_config(json_mode=False),
        }

        # Add system instruction if present
        system_instruction = self._extract_system_instruction(messages)
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(url, json=payload)

                if response.status_code >= 400:
                    logger.error(f"Gemini API error {response.status_code}: {response.text}")
                    raise AIProviderError(
                        message=f"API request failed: {response.text}",
                        provider=self.name,
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                data = response.json()

            # Extract text from response
            text = self._extract_text_from_response(data)
            return text

        except httpx.TimeoutException as e:
            logger.error(f"Gemini API timeout: {e}")
            raise AIProviderError(
                message="Request timed out",
                provider=self.name,
            )
        except httpx.RequestError as e:
            logger.error(f"Gemini API request error: {e}")
            raise AIProviderError(
                message=f"Request failed: {str(e)}",
                provider=self.name,
            )

    async def complete_json(
        self,
        messages: List[AIMessage],
        vision_input: Optional[VisionInput] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a structured JSON completion from Gemini."""
        url = self._build_url()

        payload: Dict[str, Any] = {
            "contents": self._build_contents(messages, vision_input),
            "generationConfig": self._build_generation_config(json_mode=True),
        }

        # Add system instruction if present
        system_instruction = self._extract_system_instruction(messages)
        if system_instruction:
            payload["system_instruction"] = {"parts": [{"text": system_instruction}]}

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(url, json=payload)

                if response.status_code >= 400:
                    logger.error(f"Gemini API error {response.status_code}: {response.text}")
                    raise AIProviderError(
                        message=f"API request failed: {response.text}",
                        provider=self.name,
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                data = response.json()

            # Extract text from response
            text = self._extract_text_from_response(data)

            # Parse JSON from response
            return self._parse_json_response(text)

        except httpx.TimeoutException as e:
            logger.error(f"Gemini API timeout: {e}")
            raise AIProviderError(
                message="Request timed out",
                provider=self.name,
            )
        except httpx.RequestError as e:
            logger.error(f"Gemini API request error: {e}")
            raise AIProviderError(
                message=f"Request failed: {str(e)}",
                provider=self.name,
            )

    def _extract_text_from_response(self, data: Dict[str, Any]) -> str:
        """Extract text content from Gemini API response."""
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIProviderError(
                    message="No candidates in response",
                    provider=self.name,
                )

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            if not parts:
                raise AIProviderError(
                    message="No parts in response content",
                    provider=self.name,
                )

            # Concatenate all text parts
            text_parts = [part.get("text", "") for part in parts if "text" in part]
            return "".join(text_parts)

        except (KeyError, IndexError) as e:
            logger.error(f"Failed to extract text from Gemini response: {e}")
            raise AIProviderError(
                message=f"Invalid response structure: {e}",
                provider=self.name,
            )

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from response text."""
        try:
            # First try direct parsing
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in text
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse JSON from Gemini response: {text[:500]}")
        raise AIProviderError(
            message="Failed to parse JSON from response",
            provider=self.name,
            response_body=text[:1000],
        )
