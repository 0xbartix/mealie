"""
Small client for Open Food Facts (https://world.openfoodfacts.org), the open food products database.

Search by name uses the search service (fast, searched as you type); the classic search on the Polish site
is only a fallback – it is rate limited (about 10 requests a minute) and often answers 503. Products with a
Polish barcode (590…) are listed first. Barcode lookups use the product API. Results are cached in memory.
"""

import re
import time
from collections import OrderedDict

import httpx

from mealie.core.root_logger import get_logger
from mealie.schema.diet.tracking import DietOffProduct, DietProductUnit

USER_AGENT = "MealiePlanDiety/1.0 (private Mealie fork; github.com/0xbartix/mealie)"
CLASSIC_SEARCH = "https://pl.openfoodfacts.org/cgi/search.pl"
SEARCH_SERVICE = "https://search.openfoodfacts.org/search"
PRODUCT = "https://world.openfoodfacts.org/api/v2/product/{code}"
FIELDS = "code,product_name,product_name_pl,generic_name_pl,brands,quantity,nutriments,serving_size,serving_quantity"
CACHE_SECONDS = 24 * 3600
CACHE_SIZE = 500
KJ_PER_KCAL = 4.184

logger = get_logger()


class OffUnavailable(Exception):
    """Open Food Facts could not be reached or refused the request."""


def _number(value: object) -> float | None:
    try:
        number = float(str(value).replace(",", "."))
    except TypeError, ValueError:
        return None
    return number if number >= 0 else None


def parse_product(raw: dict) -> DietOffProduct | None:
    """Turns an Open Food Facts product into our shape; None when it lacks a name or calories."""
    code = str(raw.get("code") or "").strip()
    name = (raw.get("product_name_pl") or raw.get("product_name") or raw.get("generic_name_pl") or "").strip()
    nutriments = raw.get("nutriments") or {}
    kcal = _number(nutriments.get("energy-kcal_100g"))
    if kcal is None:
        kj = _number(nutriments.get("energy-kj_100g") or nutriments.get("energy_100g"))
        kcal = round(kj / KJ_PER_KCAL, 1) if kj is not None else None
    if not code or not name or kcal is None:
        return None

    brands = raw.get("brands")
    if isinstance(brands, list):
        brand = next((str(b).strip() for b in brands if str(b).strip()), None)
    else:
        brand = next((b.strip() for b in str(brands or "").split(",") if b.strip()), None)

    quantity = str(raw.get("quantity") or "").strip() or None
    unit = DietProductUnit.ml if quantity and re.search(r"\d\s*(ml|l|cl)\b", quantity.lower()) else DietProductUnit.g

    portion_grams = _number(raw.get("serving_quantity"))
    portion_name = str(raw.get("serving_size") or "").strip() or None

    return DietOffProduct(
        code=code,
        name=name,
        brand=brand,
        quantity=quantity,
        unit=unit,
        kcal=round(kcal, 1),
        protein=round(_number(nutriments.get("proteins_100g")) or 0, 1),
        fat=round(_number(nutriments.get("fat_100g")) or 0, 1),
        carbs=round(_number(nutriments.get("carbohydrates_100g")) or 0, 1),
        portion_name=portion_name if portion_grams else None,
        portion_grams=portion_grams or None,
    )


class OpenFoodFactsClient:
    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout
        self._cache: OrderedDict[str, tuple[float, list[DietOffProduct]]] = OrderedDict()

    def _get(self, url: str, params: dict | None = None) -> dict:
        try:
            response = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise OffUnavailable(str(e)) from e
        if response.status_code == 404:
            return {}
        if response.status_code != 200:
            raise OffUnavailable(f"HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as e:
            raise OffUnavailable("not a JSON response") from e

    def search(self, query: str, limit: int = 20) -> list[DietOffProduct]:
        key = query.strip().lower()
        cached = self._cache.get(key)
        if cached and time.time() - cached[0] < CACHE_SECONDS:
            return cached[1]

        try:
            # "pl,en": many Polish products keep their Polish name in the main (English) field
            data = self._get(SEARCH_SERVICE, {"q": query, "page_size": 50, "langs": "pl,en", "fields": FIELDS})
            raw_products = data.get("hits") or []
        except OffUnavailable as e:
            logger.info(f"Open Food Facts search service failed ({e}), using the classic search")
            data = self._get(
                CLASSIC_SEARCH,
                {
                    "search_terms": query,
                    "search_simple": 1,
                    "json": 1,
                    "page_size": 50,
                    "sort_by": "unique_scans_n",
                    "fields": FIELDS,
                },
            )
            raw_products = data.get("products") or []

        products = [p for p in (parse_product(raw) for raw in raw_products) if p is not None]
        products.sort(key=lambda p: not p.code.startswith("590"))  # stable: keeps the search order otherwise
        products = products[:limit]
        self._cache[key] = (time.time(), products)
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return products

    def by_barcode(self, code: str) -> DietOffProduct | None:
        data = self._get(PRODUCT.format(code=code), {"fields": FIELDS})
        if not data or data.get("status") != 1 or not data.get("product"):
            return None
        return parse_product({"code": code, **data["product"]})


_client: OpenFoodFactsClient | None = None


def get_off_client() -> OpenFoodFactsClient:
    global _client
    if _client is None:
        _client = OpenFoodFactsClient()
    return _client
