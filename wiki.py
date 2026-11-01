"""Получение статьи и фотографии с проверкой координат города."""
import math
from urllib.parse import quote

import httpx

from game import City


def near_city(page: dict, city: City) -> bool:
    for coord in page.get("coordinates", []):
        lat1, lat2 = map(math.radians, (city.latitude, coord["lat"]))
        dlat = lat2 - lat1
        dlon = math.radians(coord["lon"] - city.longitude)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        if 12742 * math.asin(min(1, math.sqrt(a))) < 30:
            return True
    return False


class Wikipedia:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=12, headers={
            "User-Agent": "CitiesGameBot/1.0 (educational Telegram city game)"})
        self.cache = {}

    async def close(self):
        await self.client.aclose()

    async def get(self, city: City) -> tuple[str, str | None]:
        if city.id in self.cache:
            return self.cache[city.id]
        for lang, title in (("ru", city.name), ("en", city.english_name)):
            try:
                response = await self.client.get(f"https://{lang}.wikipedia.org/w/api.php", params={
                    "action": "query", "format": "json", "formatversion": 2,
                    "titles": f"{title}|{title} (город)", "redirects": 1,
                    "prop": "pageimages|info|coordinates", "inprop": "url",
                    "piprop": "thumbnail", "pithumbsize": 1000,
                })
                response.raise_for_status()
                for page in response.json().get("query", {}).get("pages", []):
                    if "missing" not in page and near_city(page, city):
                        result = (page["fullurl"], page.get("thumbnail", {}).get("source"))
                        self.cache[city.id] = result
                        return result
            except (httpx.HTTPError, ValueError, KeyError):
                continue
        # Поисковая ссылка честнее ссылки на непроверенную одноимённую статью.
        return ("https://ru.wikipedia.org/w/index.php?search=" + quote(f"{city.name} {city.country}"), None)
