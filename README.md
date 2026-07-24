# Kino Ticket Bot

Production-ready Telegram-бот для отслеживания появления билетов на фильмы в
кинотеатрах Казахстана. Бот работает через long polling, хранит подписки в SQLite,
группирует проверки Kino.kz и отправляет одно дедуплицированное уведомление.

> Проект не связан с Kino.kz. Используемый tRPC-интерфейс является внутренним и
> не считается публичным стабильным контрактом. Вся зависимость от него
> изолирована в `app/integrations/kino`.

## Возможности

- поиск фильма с опечатками по русскому и оригинальному названию;
- отслеживание первых билетов, конкретной даты или диапазона;
- выбор всех либо конкретных кинотеатров;
- пауза, возобновление и мягкая отмена подписок;
- групповой worker без отдельной задачи на каждую подписку;
- дедупликация по сеансам и безопасное повторное выполнение циклов;
- private mode, throttling, `/health` и администраторский `/backup`;
- ежедневная согласованная SQLite-копия администратору в Telegram;
- Alembic, тесты, CI, deploy ZIP и дополнительный Docker-вариант.

## Архитектура

- `app/bot` — aiogram FSM, handlers, callbacks, клавиатуры и middleware;
- `app/domain` — DTO, правила подписок, matching, мониторинг и уведомления;
- `app/integrations/kino` — единственный модуль, знающий tRPC Kino.kz;
- `app/persistence` — SQLAlchemy models, repositories, SQLite и backup;
- `app/workers` — общий monitor loop и ежедневный backup scheduler;
- `alembic` — production-миграции;
- `tests` — unit и integration tests с временной SQLite и `respx`.

Все timestamps в БД имеют смысл UTC. При SQLite-соединении включаются foreign
keys, WAL и `busy_timeout=5000`. Запускайте только один экземпляр приложения с
одним bot token.

## Локальная установка

Требуются Python 3.12+ и [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen --all-groups
cp .env.example .env
```

Заполните `.env`. Не вставляйте настоящий токен в код, README, коммиты или ZIP.
Минимальная закрытая конфигурация:

```dotenv
TELEGRAM_BOT_TOKEN=<новый token от BotFather>
ADMIN_TELEGRAM_ID=<ваш Telegram user ID>
PRIVATE_MODE=true
ALLOWED_TELEGRAM_USER_IDS=<ваш Telegram user ID>
BACKUP_SEND_TO_ADMIN=true
```

Создайте схему и запустите:

```bash
uv run alembic upgrade head
uv run python -m app
```

Команда production-запуска:

```text
sh -c "python -m alembic upgrade head && python -m app"
```

## Проверки

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy app scripts
uv run pytest --cov=app
```

Live smoke обращается к реальному внутреннему API и поэтому отделён от тестов:

```bash
uv run python scripts/smoke_kino.py
```

Скрипт выводит только количества объектов и не печатает cookies или секреты.

## Команды бота

- `/start` — главное меню;
- `/watch` — создать отслеживание;
- `/subscriptions` — показать и изменить подписки;
- `/health` — heartbeat worker и последняя успешная связь с Kino.kz;
- `/cancel` — отменить незавершённый FSM-диалог;
- `/backup` — отправить согласованную копию БД администратору.

## Deploy ZIP для JustRunMy.App

Сгенерировать и проверить архив:

```bash
uv run python scripts/build_deploy_zip.py
uv run python scripts/inspect_deploy_zip.py
```

Готовый файл: `dist/kino-ticket-bot.zip`. Файлы лежат прямо в корне архива.
В него не попадают `.env`, `.git`, виртуальное окружение, тесты, локальная БД,
backup, кэши и логи.

В панели JustRunMy.App:

1. Создайте приложение через Zip Upload с runtime Python.
2. Загрузите `dist/kino-ticket-bot.zip`.
3. Укажите startup command:

   ```text
   sh -c "python -m alembic upgrade head && python -m app"
   ```

4. Не добавляйте HTTP port: long polling не принимает входящий HTTP.
5. Подключите постоянное хранилище к `/data`, если это доступно в free tier.
6. Не превышайте 0.15 vCPU, 0.25 GB RAM, 0.3 GB disk и одно приложение.
7. Убедитесь, что расчёт панели остаётся `$0.00/month`.

Environment variables для production:

```dotenv
TELEGRAM_BOT_TOKEN=<новый token от BotFather>
ADMIN_TELEGRAM_ID=<ваш Telegram user ID>
PRIVATE_MODE=true
ALLOWED_TELEGRAM_USER_IDS=<ваш Telegram user ID>

DATA_DIR=/data
DATABASE_URL=sqlite+aiosqlite:////data/bot.db
TIMEZONE=Asia/Almaty
LOG_LEVEL=INFO

KINO_BASE_URL=https://kino.kz
KINO_REQUEST_TIMEOUT_SECONDS=15
KINO_MAX_RETRIES=3

WORKER_TICK_SECONDS=60
PENDING_MOVIE_INTERVAL_SECONDS=3600
FIRST_AVAILABLE_INTERVAL_SECONDS=600
FAR_DATE_INTERVAL_SECONDS=900
NEAR_DATE_INTERVAL_SECONDS=300
NEAR_DATE_DAYS=3
DATE_SELECTION_HORIZON_DAYS=365
DATE_RANGE_MAX_DAYS=31
CATALOG_HORIZON_DAYS=120
FIRST_AVAILABLE_HORIZON_DAYS=120
CATALOG_CACHE_SECONDS=1800
MAX_CONSECUTIVE_ERRORS=5
USER_ERROR_NOTIFICATION_HOURS=24

BACKUP_INTERVAL_HOURS=24
BACKUP_KEEP_COUNT=7
BACKUP_SEND_TO_ADMIN=true
```

Если `/data` недоступен, используйте постоянный диск приложения:

```dotenv
DATA_DIR=./data
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
```

После первого запуска проверьте логи `bot started`, `worker started`, команды
`/start` и `/health`. Создайте тестовую подписку, перезапустите приложение и
убедитесь, что подписка сохранилась. Деплой не завершён, пока БД не переживает
restart.

## Docker

Docker — дополнительный локальный вариант и основа для будущего VPS:

```bash
docker compose build
docker compose up -d
docker compose logs -f bot
```

Порты не публикуются. Контейнер работает от непривилегированного пользователя,
применяет миграции перед запуском и сохраняет `./data` через bind mount.

## Backup и restore

Ручная локальная копия через SQLite backup API:

```bash
uv run python scripts/backup_db.py
```

Для восстановления:

1. остановите приложение;
2. переименуйте текущую повреждённую `bot.db`, не удаляя её;
3. поместите выбранный backup на путь из `DATABASE_URL`;
4. запустите приложение и дождитесь применения миграций;
5. проверьте `/health` и существующие подписки.

Перед каждым обновлением выполните `/backup` и дождитесь файла в Telegram.

## Troubleshooting

- **Invalid bot token** — перевыпустите токен через BotFather и обновите только
  секретную environment variable.
- **Database is locked** — убедитесь, что работает одна реплика и база находится
  на локальном persistent disk, а не на сетевой файловой системе.
- **Kino.kz 429/5xx** — worker применит retry и exponential backoff; не уменьшайте
  интервалы до секунд.
- **Schema changed** — смотрите `KinoSchemaError` в логах и обновляйте только
  адаптер `app/integrations/kino`.
- **Duplicate polling instance** — остановите второй процесс с тем же token.

Никаких платежей, бронирования или автоматической покупки проект не выполняет.

