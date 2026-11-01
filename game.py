"""Географический справочник и правила, без обращения к Telegram."""
from dataclasses import dataclass, field, replace
import random
import re
import unicodedata

import geonamescache
from babel import Locale


# В GeoNames кириллические варианты не разделены по языкам. Для ходов бота
# используем явно заданные русские имена, чтобы не выбирать чужое написание.
BOT_NAMES = """Москва|Санкт-Петербург|Новосибирск|Екатеринбург|Казань|Нижний Новгород|
Самара|Омск|Уфа|Красноярск|Пермь|Воронеж|Волгоград|Краснодар|Саратов|Тюмень|
Тольятти|Ижевск|Барнаул|Иркутск|Хабаровск|Ярославль|Владивосток|Махачкала|
Томск|Оренбург|Кемерово|Новокузнецк|Рязань|Астрахань|Пенза|Липецк|Киров|
Чебоксары|Калининград|Тула|Курск|Ставрополь|Улан-Удэ|Тверь|Магнитогорск|
Сочи|Иваново|Брянск|Белгород|Сургут|Владимир|Архангельск|Чита|Калуга|
Смоленск|Орёл|Вологда|Якутск|Саранск|Череповец|Мурманск|Тамбов|Нальчик|
Благовещенск|Элиста|Абакан|Анапа|Анадырь|Йошкар-Ола|Находка|Норильск|
Новороссийск|Ростов-на-Дону|Петрозаводск|Псков|Ухта|Дербент|Елец|Ейск|
Лондон|Париж|Берлин|Рим|Мадрид|Лиссабон|Вена|Прага|Варшава|Осло|Стокгольм|
Хельсинки|Копенгаген|Амстердам|Брюссель|Афины|Белград|Будапешт|Бухарест|
София|Загреб|Любляна|Таллин|Рига|Вильнюс|Минск|Киев|Одесса|Тбилиси|
Ереван|Баку|Астана|Алматы|Ташкент|Самарканд|Бишкек|Душанбе|Ашхабад|
Пекин|Шанхай|Токио|Осака|Киото|Сеул|Дели|Мумбаи|Бангкок|Ханой|Сингапур|
Джакарта|Манила|Катманду|Анкара|Стамбул|Измир|Тегеран|Багдад|Дамаск|
Бейрут|Иерусалим|Амман|Эр-Рияд|Дубай|Доха|Каир|Александрия|Тунис|Алжир|
Рабат|Касабланка|Дакар|Найроби|Лагос|Аккра|Луанда|Кейптаун|Претория|
Нью-Йорк|Вашингтон|Бостон|Чикаго|Сиэтл|Лос-Анджелес|Майами|Даллас|Хьюстон|
Торонто|Оттава|Монреаль|Ванкувер|Мехико|Гавана|Панама|Богота|Лима|Кито|
Каракас|Сантьяго|Буэнос-Айрес|Монтевидео|Бразилиа|Сан-Паулу|Рио-де-Жанейро|
Сидней|Мельбурн|Канберра|Перт|Аделаида|Окленд|Веллингтон"""


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    return re.sub(r"[\s‐‑–—-]+", " ", text).strip()


def next_letter(name: str) -> str:
    return next(c for c in reversed(normalize(name)) if c.isalpha() and c not in "ьъы")


@dataclass(frozen=True)
class City:
    id: str
    name: str
    english_name: str
    country: str
    population: int
    latitude: float
    longitude: float
    aliases: tuple[str, ...]


class Atlas:
    def __init__(self):
        self.cities = []
        self.by_name = {}
        countries = Locale("ru").territories
        for key, data in geonamescache.GeonamesCache().get_cities().items():
            russian = sorted({n for n in data["alternatenames"]
                              if re.fullmatch(r"[А-ЯЁа-яё][А-ЯЁа-яё \-]+", n)},
                             key=lambda n: (not n[0].isupper(), len(n), n))
            if not russian:
                continue
            city = City(str(key), russian[0], data["name"],
                        countries.get(data["countrycode"], data["countrycode"]),
                        data["population"], data["latitude"], data["longitude"],
                        tuple(dict.fromkeys(normalize(n) for n in russian)))
            self.cities.append(city)
            for alias in city.aliases:
                self.by_name.setdefault(alias, []).append(city)
        for matches in self.by_name.values():
            matches.sort(key=lambda city: city.population, reverse=True)
        self.preferred = {}
        for name in BOT_NAMES.replace("\n", "").split("|"):
            matches = self.by_name.get(normalize(name), [])
            if matches:
                self.preferred[matches[0].id] = name
        self.cities = [replace(c, name=self.preferred[c.id]) for c in self.cities
                       if c.id in self.preferred]

    def find(self, text: str):
        matches = self.by_name.get(normalize(text), [])
        if not matches:
            return None
        city = matches[0]
        return replace(city, name=self.preferred.get(city.id, text.strip()))

    def choose(self, letter: str, used: set[str]):
        candidates = [c for c in self.cities
                      if normalize(c.name).startswith(letter) and c.id not in used
                      and not used.intersection(c.aliases)]
        # Чаще отвечаем узнаваемыми городами, но не всегда одним и тем же.
        candidates.sort(key=lambda city: city.population, reverse=True)
        return random.choice(candidates[:20]) if candidates else None


@dataclass
class Game:
    used: set[str] = field(default_factory=set)
    expected: str = ""
    turns: int = 0

    def move(self, text: str, atlas: Atlas):
        city = atlas.find(text)
        if not city:
            raise ValueError("Не нашёл такой город в справочнике. Напиши название по-русски, без слова «город».")
        if city.id in self.used or self.used.intersection(city.aliases):
            raise ValueError("Этот город уже был! Попробуй другой.")
        if self.expected and not normalize(text).startswith(self.expected):
            raise ValueError(f"Сейчас нужен город на букву «{self.expected.upper()}».")
        self.used.update((city.id, *city.aliases))
        self.turns += 1
        reply = atlas.choose(next_letter(text), self.used)
        if reply:
            self.used.update((reply.id, *reply.aliases))
            self.expected = next_letter(reply.name)
        return city, reply
