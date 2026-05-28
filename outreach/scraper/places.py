"""Google Places API (New) client.

Uses the *Text Search* endpoint with a field mask so a single request returns
everything we need to qualify a lead.

Docs: https://developers.google.com/maps/documentation/places/web-service/text-search
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.internationalPhoneNumber",
        "places.googleMapsUri",
        "places.primaryType",
        "places.types",
        "places.businessStatus",
    ]
)


@dataclass(slots=True)
class PlaceResult:
    """Normalised representation of a single Places API result."""

    place_id: str
    business_name: str
    address: Optional[str]
    website: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    phone: Optional[str]
    google_maps_url: Optional[str]
    category: Optional[str]


def _normalise(raw: dict) -> PlaceResult:
    """Convert one raw Places API place dict into a :class:`PlaceResult`."""
    return PlaceResult(
        place_id=raw.get("id", ""),
        business_name=(raw.get("displayName") or {}).get("text", ""),
        address=raw.get("formattedAddress"),
        website=raw.get("websiteUri"),
        rating=raw.get("rating"),
        review_count=raw.get("userRatingCount"),
        phone=raw.get("internationalPhoneNumber"),
        google_maps_url=raw.get("googleMapsUri"),
        category=raw.get("primaryType"),
    )


class PlacesClient:
    """Thin async wrapper around Google Places API (New)."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.google_places_api_key
        if not self._api_key:
            raise RuntimeError(
                "GOOGLE_PLACES_API_KEY is not set; cannot call the Places API."
            )
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def text_search(
        self,
        query: str,
        page_size: int = 20,
        language_code: str = "en",
        region_code: str = "NG",
    ) -> list[PlaceResult]:
        """Search Places by free-text query.

        Args:
            query: Natural-language query, e.g. ``"salon in Lekki, Lagos"``.
            page_size: Max results per page (1-20).
            language_code: ISO language for ``displayName``.
            region_code: ISO 3166-1 alpha-2 region bias.

        Returns:
            List of :class:`PlaceResult`. May be empty.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        payload = {
            "textQuery": query,
            "pageSize": min(max(page_size, 1), 20),
            "languageCode": language_code,
            "regionCode": region_code,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                PLACES_TEXT_SEARCH_URL, headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()

        return [_normalise(p) for p in data.get("places", [])]
