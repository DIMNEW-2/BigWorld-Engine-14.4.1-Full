# Docker: WorldEditor, BigWorld server и ресурсы клиента

Пошаговая инструкция для этого checkout. Здесь используются два разных окружения:

- Linux/CentOS 7 Docker-контейнер — для Linux-сервера BigWorld;
- Windows с MSVC — для GUI-инструмента WorldEditor.

**Один CentOS-контейнер из `Dockerfile` не может собрать WorldEditor.** В корневом `Dockerfile` подготовлена среда сборки сервера, а не Windows-приложений.

Ниже предполагается, что корень репозитория смонтирован в Linux-контейнер как `/src`, а в Windows-контейнере — как `C:\src`.

## 0. Где находится собранный сервер

Разделённый архив с `origin/main` (`server.z01`–`server.z36` и `server.zip`) уже извлечён в:

```text
game/bin/server/el7/
```

В каталоге находятся Linux x86-64 серверные процессы, инструменты и тесты. Архив проверен 7-Zip: 37 томов, 48 файлов, около 2,3 GiB после распаковки. Папка `game/bin/server/` добавлена в `.gitignore`, поэтому бинарники остаются локальными — **не добавляйте их принудительно в Git**. GitHub отклоняет отдельные файлы больше 100 MiB.

Если нужно распаковать архив в другом клоне: сложите все 37 частей рядом и извлеките именно `server.zip` 7-Zip в `game/bin`:

```powershell
7z x .\server.zip -o.\game\bin
```

Не распаковывайте каждую часть отдельно и не склеивайте их вручную. ZIP не хранит Unix executable bits для этих файлов; после извлечения на Windows и монтирования checkout в Linux-контейнер выполните из корня репозитория:

```bash
find game/bin/server/el7 -type f ! -name '*.txt' -exec chmod a+x {} +
test -x game/bin/server/el7/server/baseapp
```

## 1. Сборка WorldEditor

### 1.1. Почему текущий Dockerfile не подходит

`programming/bigworld/CMakeLists.txt` разрешает обычную сборку инструментов только под Windows. Набор `BW_CMAKE_TARGET=tools` содержит цель `worldeditor`; она собирает Windows GUI-приложение с MFC и DirectX 9. В частности, проект использует переменную `DXSDK_DIR` для заголовков и библиотек DirectX.

Поэтому:

- `Dockerfile` с `FROM centos:7.9.2009` подходит для серверных ELF-бинарников;
- запуск `cmake` в этом Linux-контейнере не создаст Linux-версию WorldEditor — такой платформы у этой цели нет;
- Linux-контейнер нельзя превратить в Windows-сборщик установкой дополнительных `yum`-пакетов.

Если Docker Engine работает в Linux-режиме, WorldEditor собирайте на Windows-хосте с установленным Visual Studio либо на отдельном Windows-билдере. Windows-контейнер возможен только на Windows-хосте при переключённом Docker Desktop в режим **Windows containers**. Он соберёт `.exe`, но не покажет графический интерфейс: запуск редактора выполняйте на Windows-хосте.

### 1.2. Требования к Windows-билдеру

Для описанного ниже варианта подготовьте Windows-образ/окружение, в котором доступны:

1. Visual Studio Build Tools 2022 или Visual Studio 2022 с C++ Desktop workload, Windows SDK, MFC и ATL.
2. Совместимый старый toolset **v141_xp**. Именно его задаёт генератор `vc17_win64` в `programming/bigworld/build/bigworld_cmake.py`; обычного toolset v143 может быть недостаточно. Генератор Win64 помечен в проекте как experimental.
3. DirectX SDK с D3DX9 (обычно legacy DirectX SDK June 2010). В контейнере задайте `DXSDK_DIR`, например `C:\DXSDK\`.
4. Python 3. В репозитории уже лежит CMake 3.23 для Windows: `programming/bigworld/third_party/cmake-win32-x86/bin/cmake.exe`.
5. Доступ к checkout и к Windows SDK/DirectX SDK из контейнера.

В репозитории **нет готового `Dockerfile.worldeditor`**: текущий Linux `Dockerfile` не содержит Windows/MSVC/MFC/DirectX компонентов. Поэтому команда запуска ниже предполагает, что у вас уже есть Windows-образ, например `bw-worldeditor-builder`, в котором эти требования установлены. Тег/версию Windows-образа нужно подбирать под версию Windows-хоста.

### 1.3. Запуск Windows-контейнера и сборка

В PowerShell на Windows, из корня репозитория, смонтируйте checkout в контейнер. Замените `bw-worldeditor-builder` на свой подготовленный Windows-образ:

```powershell
$repo = (Resolve-Path .).Path

docker run --rm -it `
  --mount "type=bind,source=$repo,target=C:\src" `
  --workdir C:\src `
  bw-worldeditor-builder powershell
```

Внутри контейнера выполните конфигурацию и сборку только цели WorldEditor:

```powershell
$env:DXSDK_DIR = 'C:\DXSDK\'
Set-Location C:\src\programming\bigworld\build

# Генератор vc17_win64 создаёт проект VS 2022 x64 и выбирает toolset v141_xp.
python .\bigworld_cmake.py --target tools --generator vc17_win64
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$cmake = 'C:\src\programming\bigworld\third_party\cmake-win32-x86\bin\cmake.exe'
$buildDir = 'C:\src\programming\build_tools_vc17_win64'
& $cmake --build $buildDir --config Hybrid --target worldeditor --parallel 8
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

`bigworld_cmake.py` создаёт build-каталог `programming/build_tools_vc17_win64`; он не переключает текущую Git-ветку. В конфигурации `Hybrid` ожидаемый результат:

```text
game/bin/tools/worldeditor/win64/worldeditor.exe
```

Сборка `Debug` создаёт вариант с суффиксом `_d`. Не переносите один `.exe` отдельно от его DLL и ресурсов: запускайте собранный каталог вместе с `game/bin/tools/worldeditor/resources` и остальными зависимостями, созданными/скопированными CMake. Сам WorldEditor запускается на Windows-хосте, а не в Linux-контейнере.

Перед запуском редактора на Windows задайте ресурсные корни (пример для демонстрационного проекта):

```powershell
$env:MF_ROOT = 'C:\src\game'
$env:BW_RES_PATH = 'C:\src\game\res\fantasydemo;C:\src\game\res\bigworld'
& 'C:\src\game\bin\tools\worldeditor\win64\worldeditor.exe'
```

Если требуется открыть другой проект/карту, поставьте его ресурсный корень первым в `BW_RES_PATH`. При проблемах конфигурации сначала проверьте наличие MFC, `v141_xp`, DirectX SDK и корректность `DXSDK_DIR`; ошибки на этих шагах не исправляются настройкой CentOS-контейнера.

## 2. Запуск сервера в Linux Docker

### 2.1. Создать или открыть контейнер

Из корня репозитория на хосте соберите образ среды из имеющегося Dockerfile (если он ещё не собран):

```powershell
$repo = (Resolve-Path .).Path
docker build -t bigworld-el7 -f Dockerfile .
docker run --rm -it --name bw-server `
  --mount "type=bind,source=$repo,target=/src" `
  --workdir /src `
  bigworld-el7 bash
```

Если серверный образ уже есть, повторите только `docker run`. Внутри контейнера проверьте файлы:

```bash
cd /src
test -x game/bin/server/el7/server/baseapp
test -x game/bin/server/el7/tools/bwmachined2
```

Архивные бинарники предназначены для 64-битного Linux совместимого с CentOS/RHEL 7. Если вместо архива сервер собирается из исходников, из корня checkout запустите `./tools/build_server.sh hybrid`; этот вариант использует Python 2.7 и зависимости из `NOTE`/`Dockerfile`.

### 2.2. Настроить resource path

Серверу нужны корень BigWorld (`MF_ROOT`) и список ресурсных корней (`BW_RES_PATH`). Для TankArena поставьте её каталог первым, чтобы выбрался `game/res/tankarena/server/bw.xml`, а общие ресурсы BigWorld — следом:

```bash
export MF_ROOT=/src/game
export BW_RES_PATH=/src/game/res/tankarena:/src/game/res/bigworld
printf '%s;%s:%s\n' \
  "$MF_ROOT" \
  /src/game/res/tankarena \
  /src/game/res/bigworld \
  > "$HOME/.bwmachined.conf"
```

В `.bwmachined.conf` точка с запятой отделяет `MF_ROOT` от `BW_RES_PATH`, а двоеточие разделяет несколько Linux resource roots. Если работаете не под `root`, файл должен находиться в домашнем каталоге именно того пользователя, от которого запускаются процессы.

Задайте разрешённые типы процессов для `bwmachined2`:

```bash
cat >/etc/bwmachined.conf <<'EOF'
[Components]
cellApp
baseApp
serviceApp
dbApp
cellAppMgr
baseAppMgr
dbAppMgr
loginApp

[TimingMethod]
gettime
EOF
```

### 2.3. Запустить `bwmachined2` и приложения

Контейнер обычно не запускает `systemd`, поэтому запустите `bwmachined2` напрямую в foreground-режиме, оставив процесс в фоне текущей shell-сессии:

```bash
mkdir -p /var/run/bigworld
nohup /src/game/bin/server/el7/tools/bwmachined2 \
  --foreground --pid /tmp/bwmachined2.pid \
  >/tmp/bwmachined2.log 2>&1 </dev/null &
echo $! >/tmp/bwmachined2.shell.pid
sleep 2
kill -0 "$(cat /tmp/bwmachined2.shell.pid)"
```

Затем запустите серверные процессы из корня checkout:

```bash
cd /src
./game/start-all-server.sh hybrid
```

`hybrid` использует бинарники из `game/bin/server/el7/server`. Скрипт стартует `dbappmgr`, `cellappmgr`, `baseappmgr`, `loginapp`, `dbapp`, `cellapp`, `serviceapp` и `baseapp`; он **не** запускает `bwmachined2` автоматически.

Проверить состояние и журналы можно так:

```bash
ps -ef | grep -E 'bwmachined2|/(dbapp|cellapp|baseapp|loginapp|serviceapp)' | grep -v grep
ls -lh game/bin/server/el7/run/
tail -n 100 game/bin/server/el7/run/*.log
```

Для остановки сначала выключите приложения, затем остановите daemon:

```bash
cd /src
./game/stop-all-server.sh hybrid
if [ -r /tmp/bwmachined2.shell.pid ]; then
  kill -TERM "$(cat /tmp/bwmachined2.shell.pid)" 2>/dev/null || true
fi
```

Логи и PID-файлы приложений остаются в `game/bin/server/el7/run/`. Не закрывайте интерактивный контейнер, пока работаете с сервером: при выходе из `docker run --rm -it` Docker остановит контейнер и его процессы.

### 2.4. Сеть и границы прототипа

Запуск процессов внутри контейнера проверяет серверную конфигурацию, но сам по себе не открывает доступ с игрового клиента на хосте. Для подключения извне отдельно настройте адрес, который сервер сообщает клиентам, зафиксируйте/проверьте используемые порты и опубликуйте их через Docker (`--publish`); набор портов зависит от `bw.xml`, конфигурации приложений и схемы сети. Не публикуйте случайный небольшой диапазон портов без проверки фактической конфигурации.

`game/res/tankarena` — демонстрационный серверный прототип, а не сервер World of Tanks. Даже успешно запущенный `loginapp` не обеспечивает совместимость с немодифицированным WoT-клиентом, его авторизацией, RPC и сетевой схемой.

## 3. Подготовка и адаптация клиентской папки `res`

### 3.1. Важное ограничение

Копирование клиентской `res` целиком не создаёт сервер. В `res` клиента могут находиться клиентские скрипты, GUI, эффекты, шейдеры, звук, текстуры, модели и уже скомпилированные данные карты. Серверу дополнительно нужны собственные серверные Python-скрипты, Entity definitions, конфигурация приложений, DB-схема и подготовленные данные пространства. Этих частей обычно нет в обычной клиентской папке.

BigWorld Server 14.4.1 и ресурсы конкретной игры/версии клиента не становятся совместимыми только потому, что у файлов похожие расширения. Нужны ресурсы, полученные законно, и именно те форматы/схемы, которые понимает используемая версия BigWorld.

### 3.2. Сохранить оригинал и проверить формат

1. Зафиксируйте точную версию клиента и сделайте резервную копию его `res`. Не редактируйте исходную папку клиента.
2. Храните оригинальные ресурсы вне публичного Git-репозитория, например на хосте как read-only каталог. Не добавляйте их в публичный PR: клиентские файлы могут быть проприетарными и значительно увеличить размер репозитория.
3. Если клиент хранит ресурсы в `.pkg` или собственных архивах, сначала используйте совместимый с этой версией клиента способ распаковки. `7z` для серверного split-архива и BigWorld `res_packer` — не универсальные распаковщики клиентских игровых пакетов.
4. Получите обычное дерево файлов и сохраните его структуру/регистр имён. Linux resource manager чувствителен к регистру: `Maps/Map.dds` и `maps/map.dds` — разные пути.
5. Составьте список файлов, их размеров и контрольных сумм; не копируйте всё подряд в `game/res`.

Для примера, после монтирования исходной папки в контейнер как `/client-res`:

```bash
find /client-res -type f | sort >/tmp/client-res-files.txt
wc -l /tmp/client-res-files.txt
du -sh /client-res
```

### 3.3. Разделить ресурсы по назначению

Создайте отдельный проектный resource root и оставьте общий корень BigWorld неизменённым. Например:

```text
game/res/tankarena/             # server/bw.xml, scripts, entity_defs
  scripts/base/
  scripts/cell/
  scripts/entity_defs/
  scripts/service/
  scripts/services.xml
  server/bw.xml
  spaces/<имя-карты>/             # только подготовленная карта
  client_assets/                  # необязательно, выбранные и проверенные assets
```

Содержимое клиента разбирайте по категориям:

- **Серверная логика.** Создайте/адаптируйте свои Base/Cell/Service скрипты, `scripts/entity_defs/*.def`, `scripts/entities.xml`, DB и service-конфигурацию. Клиентские Python-скрипты часто завязаны на GUI, renderer, клиентские модули и не работают на сервере без переписывания.
- **Пространство/карта.** Для игрового пространства нужны согласованные `space.settings`, `.chunk`, `.cdata`, данные terrain и, если задействована навигация, navmesh. Ссылки внутри этих файлов должны указывать на доступные файлы. Проверяйте/пересохраняйте пространство WorldEditor и соответствующими инструментами именно той версии движка, на которой работает сервер.
- **Визуальные ресурсы.** Текстуры, модели, материалы и эффекты нужны только тогда, когда их действительно запрашивает серверная логика или клиентское приложение. Форматы `.model`, `.visual`, `.primitives`, `.mfm`, `.dds` могут требовать правильной версии Asset Pipeline и экспортёра; простое переименование расширения не является конвертацией.
- **Клиентские presentation-only файлы.** GUI, меню, звук, шейдеры, эффекты и настройки клиента не нужны серверной логике, если сервер явно их не загружает. Не переносите их в runtime без причины.

Для структуры валидной BigWorld-карты используйте sample из репозитория, например `game/res/fantasydemo/spaces/arctic`, и соответствующие инструменты WorldEditor/`navgen`. Наличие клиентской папки с похожими `spaces` не гарантирует совпадение формата `.chunk`/`.cdata` с данным сервером.

### 3.4. Подключить ресурсы в контейнер

Самый безопасный вариант — монтировать оригинальный клиентский каталог read-only и добавлять только нужные файлы в отдельный curated overlay. Например, дополнительно смонтировать каталог хоста в контейнер как `/client-res`, затем задать внутри Linux-контейнера:

```bash
export MF_ROOT=/src/game
export BW_RES_PATH=/src/game/res/tankarena:/src/game/res/tankarena/client_assets:/src/game/res/bigworld:/client-res
printf '%s;%s:%s:%s:%s\n' \
  "$MF_ROOT" \
  /src/game/res/tankarena \
  /src/game/res/tankarena/client_assets \
  /src/game/res/bigworld \
  /client-res \
  > "$HOME/.bwmachined.conf"
```

Оставляйте `game/res/tankarena` первым: там находится нужный `server/bw.xml`. Порядок root-ов влияет на то, какой файл будет найден при совпадающих относительных путях. В `BW_RES_PATH` для Linux разделитель — `:`; Windows-пример выше для WorldEditor использует `;`.

Проверка основных путей перед стартом:

```bash
test -f /src/game/res/tankarena/server/bw.xml
test -f /src/game/res/bigworld/server/development_defaults.xml
```

Не добавляйте raw client root перед проектом: одноимённые конфиги или скрипты клиента могут затенить серверные файлы. После тестирования уменьшите `BW_RES_PATH` до минимального списка реально используемых каталогов.

### 3.5. Для чего нужен `res_packer`

В извлечённом Linux-наборе есть `game/bin/server/el7/tools/res_packer`. Это BigWorld-инструмент упаковки/обработки поддерживаемых движком типов ресурсов, а не конвертер любой версии клиента, не импортёр исходных `.max`/`.fbx` и не распаковщик `.pkg`.

Для пакетной обработки список содержит относительные пути от входного корня, по одному ресурсу на строку. Общая форма CLI из исходников:

```text
res_packer --list <asset_list.txt> --in <input_root> --out <output_root> \
           --err <error_log> --res <search_paths>
```

В параметре `--res` сам `res_packer` ожидает список search paths, разделённый `;` (заключайте значение в кавычки в shell). Это отдельный формат аргумента; не путайте его с Linux-переменной `BW_RES_PATH`, где корни разделены `:`. Сначала тестируйте один заведомо поддерживаемый ресурс во временный `--out`, изучайте error log и сверяйте результат на Windows-клиенте/WorldEditor. Не запускайте пакетную обработку на всей чужой `res` без списка и резервной копии.

### 3.6. Проверка результата и совместимости

Перед расширением прототипа проверьте последовательно:

1. Выбранный первый root действительно содержит требуемый `server/bw.xml`.
2. Все пути из XML, Python и Entity definitions существуют с тем же регистром букв.
3. Серверные Entity definitions совпадают с реализацией Base/Cell/Service и схемой сообщений, которую будет вызывать клиент.
4. Карта загружается и содержит collision/navigation данные, которые использует игровая логика.
5. В логах нет `Resource not found`, ошибок разбора `.def`/XML, отсутствующих Python-модулей и несовместимых типов.
6. Python-правила существующего TankArena-прототипа проходят тесты:

```bash
python3 -m unittest discover -s tests/tankarena -v
```

Даже после этих проверок это будет ваш собственный сервер/адаптер, а не автоматическая реконструкция официального сервера игры. Для прямой поддержки конкретного WoT-клиента отдельно требуются соответствующие версии Entity schema, сетевого протокола, login/auth flow, игровых сервисов и серверной логики; одной клиентской папки `res` для этого недостаточно.
