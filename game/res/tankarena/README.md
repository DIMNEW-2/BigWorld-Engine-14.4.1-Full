# TankArena — серверный прототип BigWorld

Это отдельный пример серверной логики для BigWorld 14.4.1. Код не содержит
оригинальных игровых ресурсов WoT. Он использует BigWorld `Base/Proxy` для
клиентских сессий и `ServiceApp` как авторитетный менеджер одной комнаты.

## Что реализовано

- лобби одной комнаты: хост, распределение по двум командам, готовность;
- одиночный запуск с заполнением свободных мест серверными ботами;
- ограничение до 15 машин на команду;
- проверка последовательности и диапазона команд движения/прицеливания;
- перемещение по упрощённой 2D-арене, таймаут ввода и границы карты;
- серверный луч выстрела, перезарядка, боезапас, условная броня и урон;
- простое поведение ботов, захват базы, уничтожение команды, таймер и итог;
- сетевые события и снимки состояния через `ClientMethods`.

Правила находятся в `scripts/common/battle_rules.py`; BigWorld-адаптер — в
`scripts/service/OfflineBattleService.py`. Клиентский Proxy-шаблон и тип
сущности — `scripts/base/TankPlayer.py` и `scripts/entity_defs/TankPlayer.def`.

Значения машин в `DEMO_VEHICLE_PROFILES` — тестовые параметры, а не точные
характеристики техники WoT. Выстрел пока не учитывает реальную геометрию карты,
препятствия, баллистику, модули и клиентскую модель коллизий. Это основа для
дальнейшей интеграции, не готовый игровой баланс.

## Сборка BigWorld server

Сборка исходного движка по текущим скриптам рассчитана на CentOS/RHEL 7,
Python 2.7 и зависимости из `NOTE`/`Dockerfile`. В корне репозитория:

```bash
./tools/build_server.sh hybrid
# либо debug-сборка:
./tools/build_server.sh debug
```

Скрипт проверяет платформу и версию Python до запуска `make`. `hybrid` кладёт
серверные бинарники в `game/bin/server/el7/server`, `debug` — в
`game/bin/server/el7_debug/server`. Затем после настройки/запуска `bwmachined2`
можно стартовать процессы:

```bash
./game/start-all-server.sh hybrid
# остановка:
./game/stop-all-server.sh hybrid
```

Для Debug используйте `debug` вместо `hybrid`. Логи и PID-файлы сохраняются в
`game/bin/server/<el7-config>/run/`; скрипт остановки проверяет полный путь к
процессу и не делает глобальный `pkill`.

## Подключение ресурсов

Добавьте `game/res/tankarena` в ресурсный путь BigWorld и поставьте его перед
другими игровыми корнями, чтобы выбран был именно `server/bw.xml` этого примера.
Например, `~/.bwmachined.conf` содержит одну строку формата
`MF_ROOT;BW_RES_PATH` (подставьте фактический путь к checkout):

```text
/path/to/BigWorld-Engine-14.4.1-Full/game;/path/to/BigWorld-Engine-14.4.1-Full/game/res/tankarena:/path/to/BigWorld-Engine-14.4.1-Full/game/res/bigworld
```

Список разрешённых компонентов задаётся отдельно в `/etc/bwmachined.conf`:

```text
[Components]
cellApp
baseApp
serviceApp
dbApp
cellAppMgr
baseAppMgr
dbAppMgr
loginApp
```

`server/bw.xml` принимает неизвестные локальные учётные записи как `TankPlayer`,
использует XML DB и запускает `OfflineBattleService` из `services.xml`. Сервис
хранит комнату только в памяти: перезапуск процесса сбрасывает текущую игру.

Клиентский код должен вызывать методы `TankPlayer`: `setVehicle`, `setReady`,
`startBattle`, `resetBattle`, `submitInput`, `submitAim`, `fire`,
`requestSnapshot` и `leaveBattle`. После результата хост вызывает `resetBattle`,
чтобы открыть следующее лобби. Снимки и события приходят через
`onBattleSnapshot` и `onBattleEvent`. Готовность обязательна для всех
подключённых игроков; стартовать и сбрасывать комнату может только её хост.

Это однокомнатный прототип с одним активным фрагментом `OfflineBattleService`.
Не запускайте несколько независимых ServiceApp-фрагментов с этой же логикой:
у каждого будет собственное состояние комнаты.

## Проверки

Правила запускаются на обычном Python 3 без BigWorld runtime:

```bash
python3 -m unittest discover -s tests/tankarena -v
```

## Связь с указанными WoT-репозиториями и ограничения совместимости

- `WoTOfflineHangar0.9.22` эмулирует ангар на стороне клиента; его README прямо
  указывает, что он не содержит BigWorld server и не реализует сетевой сервер.
- `WorldOfTanks-Decompiled` в указанной ветке — клиентские скрипты/описания
  0.9.21; это не серверная реализация WoT 0.9.22.
- `wot-0.9.22-offline-battles` содержит отдельный LAN-сервер и клиентский мод
  для 0.9.22, с собственным протоколом и выделенным клиентом-worker для
  симуляции. Это не BigWorld `baseapp/cellapp` сервер и не сетевой протокол
  розничного WoT.

Поэтому этот проект **не является drop-in заменой официального WoT сервера** и
не обещает прямое подключение немодифицированного клиента 0.9.22. Совпадение
версии BigWorld само по себе не гарантирует совместимость схем сущностей,
RPC, авторизации и wire-протокола. Для WoT-клиента нужен адаптер его клиентских
вызовов к этим API либо восстановление точной схемы/протокола конкретной версии.

Исходные ссылки:

- https://github.com/DIMNEW-2/WoTOfflineHangar0.9.22/tree/arena/ddb3be5f-wotofflinehangar0-9-22
- https://github.com/StranikS-Scan/WorldOfTanks-Decompiled/tree/0.9.21
- https://github.com/colorfulmeans/wot-0.9.22-offline-battles
