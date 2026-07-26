# Кинокотён

[![CI](https://github.com/Qydnama/kinokoten/actions/workflows/ci.yml/badge.svg)](https://github.com/Qydnama/kinokoten/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)

Telegram-бот, который следит за расписанием кинотеатров Казахстана и сообщает,
когда на нужный фильм появляются билеты.

Можно выбрать конкретную дату, диапазон или просто дождаться старта продаж.
Бот учитывает только выбранные кинотеатры и сообщает о продаже в два этапа:
сначала — когда сеансы появляются в расписании, затем — когда Kino.kz открывает
выбор мест и в зале остаётся хотя бы одно свободное место. Между уведомлениями
отслеживание продолжается автоматически.

> Проект использует внутренний API Kino.kz и не связан с компанией Kino.kz.
> Если формат API изменится, интеграцию тоже придётся обновить.

## Что умеет

- искать фильмы даже с небольшой опечаткой в названии;
- следить за всеми или только выбранными кинотеатрами;
- отдельно сообщать о появлении расписания и об открытии продажи билетов;
- работать с конкретной датой, диапазоном и режимом «первые билеты»;
- показывать город, даты, кинотеатры и состояние каждой подписки;
- приостанавливать и возобновлять отслеживание;
- сохранять подписки после перезапуска;
- делать резервные копии SQLite и отправлять их администратору.

Бот ничего не покупает и не бронирует — уведомление ведёт на страницу фильма
на Kino.kz.

## Быстрый старт

Нужны Python 3.12+ и [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Qydnama/kinokoten.git
cd kinokoten
uv sync --frozen
```

Создайте `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=token_from_botfather
ADMIN_TELEGRAM_ID=123456789

PRIVATE_MODE=false
ALLOWED_TELEGRAM_USER_IDS=123456789

DATA_DIR=./data
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
```

Запустите бота:

```bash
uv run python -m app
```

Миграции применяются автоматически перед запуском Telegram polling.

В один момент должен работать только один экземпляр бота с этим токеном.

## Команды

| Команда | Назначение |
| --- | --- |
| `/start` | Главное меню |
| `/watch` | Создать новое отслеживание |
| `/subscriptions` | Посмотреть и изменить подписки |
| `/health` | Состояние фоновой проверки |
| `/cancel` | Закрыть текущий диалог |
| `/backup` | Отправить копию БД администратору |

## Конфигурация

Основные настройки задаются через environment variables.

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `PRIVATE_MODE` | `true` | Пускать только пользователей из allowlist |
| `ALLOWED_TELEGRAM_USER_IDS` | — | Telegram ID через запятую |
| `TIMEZONE` | `Asia/Almaty` | Часовой пояс дат и уведомлений |
| `WORKER_TICK_SECONDS` | `60` | Частота запуска фонового цикла |
| `FIRST_AVAILABLE_INTERVAL_SECONDS` | `600` | Интервал режима первых билетов |
| `NEAR_DATE_INTERVAL_SECONDS` | `300` | Проверка ближайших дат |
| `BACKUP_SEND_TO_ADMIN` | `true` | Отправлять ежедневную копию SQLite |

Остальные интервалы и лимиты перечислены в `app/config.py`.

## Деплой на JustRunMy.App

Откройте приложение в панели, перейдите в **Deployment → Deploy from Git**,
скопируйте выданную команду и выполните её из корня репозитория:

```bash
git push -u <адрес-из-панели> HEAD:deploy
```

Run command в настройках приложения оставьте пустой: контейнер использует
команду из `Dockerfile`, сам подготавливает постоянное хранилище в `/app` и
применяет миграции перед запуском бота.

Для публичного бота установите `PRIVATE_MODE=false`. Значение `true` включает
allowlist и разрешает пользоваться ботом только администратору и ID из
`ALLOWED_TELEGRAM_USER_IDS`.

Публичный порт не нужен: бот работает через Telegram long polling. После первого
запуска создайте подписку, перезапустите приложение и проверьте, что она
сохранилась.

## Docker

```bash
docker compose build
docker compose up -d
docker compose logs -f bot
```

Данные сохраняются в `./data`. Порты контейнера наружу не публикуются.

## Разработка

```bash
uv sync --frozen --all-groups
uv run ruff format --check .
uv run ruff check .
uv run mypy app scripts
uv run pytest
```

Проверить текущий ответ Kino.kz отдельно от тестов:

```bash
uv run python scripts/smoke_kino.py
```

## Как устроен проект

```text
app/bot/                Telegram handlers, FSM и клавиатуры
app/domain/             правила подписок и мониторинг
app/integrations/kino/  клиент внутреннего API Kino.kz
app/persistence/        SQLite, SQLAlchemy и repositories
app/workers/            фоновые проверки и backup
alembic/                миграции
tests/                  unit и integration tests
```

SQLite запускается с foreign keys, WAL и `busy_timeout`. Запросы к Kino.kz
группируются по городу и датам, поэтому количество подписок не превращается в
такое же количество одинаковых HTTP-запросов.
