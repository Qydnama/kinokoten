from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class City:
    id: int
    name: str


CITIES = (
    City(1, "Астана"),
    City(2, "Алматы"),
    City(3, "Актау"),
    City(4, "Актобе"),
    City(5, "Атырау"),
    City(6, "Балхаш"),
    City(7, "Караганда"),
    City(8, "Костанай"),
    City(9, "Кызылорда"),
    City(10, "Павлодар"),
    City(11, "Петропавловск"),
    City(12, "Семей"),
    City(13, "Талдыкорган"),
    City(14, "Тараз"),
    City(15, "Темиртау"),
    City(16, "Уральск"),
    City(17, "Усть-Каменогорск"),
    City(20, "Кокшетау"),
    City(23, "Жанаозен"),
    City(28, "Рудный"),
    City(40, "Жезказган"),
    City(47, "Туркестан"),
)

CITY_BY_ID = {city.id: city for city in CITIES}
