import unittest
from unittest.mock import AsyncMock, patch

import httpx
from telegram.error import BadRequest

from bot import card
from game import Atlas, Game, next_letter, normalize
from wiki import Wikipedia, near_city


class GameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlas = Atlas()

    def test_normalization(self):
        self.assertEqual(normalize("  Орёл "), normalize("орел"))
        self.assertEqual(normalize("Санкт-Петербург"), normalize("санкт петербург"))
        self.assertEqual(next_letter("Пермь"), "м")
        self.assertEqual(next_letter("Анадырь"), "р")

    def test_real_city_data(self):
        moscow = self.atlas.find("Москва")
        self.assertIsNotNone(moscow)
        self.assertEqual(moscow.country, "Россия")
        self.assertEqual(moscow.name, "Москва")
        self.assertEqual(self.atlas.find("Санкт-Петербург").name, "Санкт-Петербург")
        self.assertGreater(moscow.population, 1_000_000)
        self.assertIsNotNone(self.atlas.find("Париж"))

    def test_turn_and_repeat(self):
        game = Game()
        player, reply = game.move("Москва", self.atlas)
        self.assertEqual(normalize(reply.name)[0], "а")
        self.assertEqual(game.expected, next_letter(reply.name))
        self.assertEqual(game.turns, 1)
        with self.assertRaisesRegex(ValueError, "уже был"):
            game.move("Москва", self.atlas)

    def test_bad_move_does_not_change_game(self):
        game = Game(expected="я")
        for text in ("это не город", "Москва"):
            with self.assertRaises(ValueError):
                game.move(text, self.atlas)
        self.assertEqual(game.used, set())
        self.assertEqual(game.turns, 0)

    def test_no_bot_city_is_win(self):
        game = Game()
        with patch.object(self.atlas, "choose", return_value=None):
            _, reply = game.move("Москва", self.atlas)
        self.assertIsNone(reply)


class WikipediaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.city = Atlas().find("Москва")
        self.wiki = Wikipedia()

    async def asyncTearDown(self):
        await self.wiki.close()

    async def test_verified_photo(self):
        page = {"fullurl": "https://ru.wikipedia.org/wiki/Москва",
                "coordinates": [{"lat": self.city.latitude, "lon": self.city.longitude}],
                "thumbnail": {"source": "https://example.org/moscow.jpg"}}
        response = httpx.Response(200, json={"query": {"pages": [page]}},
                                  request=httpx.Request("GET", "https://example.org"))
        with patch.object(self.wiki.client, "get", AsyncMock(return_value=response)):
            url, photo = await self.wiki.get(self.city)
        self.assertIn("/wiki/", url)
        self.assertTrue(photo.endswith("moscow.jpg"))

    async def test_network_failure_has_search_link(self):
        with patch.object(self.wiki.client, "get", AsyncMock(side_effect=httpx.ConnectError("offline"))):
            url, photo = await self.wiki.get(self.city)
        self.assertIn("search=", url)
        self.assertIsNone(photo)

    async def test_wrong_coordinates(self):
        self.assertFalse(near_city({"coordinates": [{"lat": 0, "lon": 0}]}, self.city))

    async def test_photo_delivery_fallback(self):
        message = AsyncMock()
        message.reply_photo.side_effect = BadRequest("Photo unavailable")
        wiki = AsyncMock()
        wiki.get.return_value = ("https://ru.wikipedia.org/wiki/Москва", "https://example.org/image.jpg")
        await card(message, self.city, "Город", wiki)
        message.reply_text.assert_awaited_once()
        self.assertIn("Фото сейчас недоступно", message.reply_text.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
