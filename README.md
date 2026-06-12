# cupflag - автоматизация захвата флагов

Автоматизация для трёх уровней платформы cupflag (LVL1/LVL2/LVL3). Подробный разбор
решения и найденные уязвимости - в `WRITEUP_LVL1.md`, `WRITEUP_LVL2.md`,
`WRITEUP_LVL3.md`.

## Установка

```bash
python3 -m venv .venv
pip install -r requirements.txt
```

## Запуск

LVL1 - baseline:

```bash
python run_lvl1.py --duration 300
```

LVL2 - капча + пул сессий:

```bash
python run_lvl2.py --duration 300
```

LVL3 - очередь за Cloudflare; нужен запущенный FlareSolverr:

```bash
docker run -d --name flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest
python run_lvl3.py --duration 300
```

Параметр `--duration` - длительность прогона в секундах (без него - до Ctrl-C).
Пойманные флаги пишутся с таймстампами в stdout и в `flags_lvlN.jsonl`; для LVL3
полный трейс запросов/ответов - в `lvl3_io.jsonl`.

## Структура проекта

```
cupflag/                 пакет с кодом
  common/                общие компоненты для всех уровней
    log.py               лог с миллисекундными метками
    flags.py             приёмник флагов: дедупликация, запись в JSONL, отброс decoy
    auth.py              пароль md5(username) и User-Agent
    session.py           PlatformClient - httpx-сессия + логин с ретраями
    scheduling.py        границы целых секунд + трекинг фоновых задач
    runner.py            BaseRunner - общий жизненный цикл капче-петли
    burst.py             BurstRunner - общий RTT-таймированный залп на границе секунды
    cli.py               общий каркас точки входа (аргументы, сигналы, asyncio)
    flaresolverr.py      клиент FlareSolverr (прохождение Cloudflare)
  lvl1/                  LVL1 - baseline
    config.py            настройки уровня
    runner.py            Lvl1Runner (BurstRunner) - залп по общему клиенту
  lvl2/                  LVL2 - капча + пул сессий
    config.py            настройки уровня
    pool.py              SessionPool - пул одноразовых сессий
    runner.py            Lvl2Runner (BurstRunner) - залп из пула сессий
  lvl3/                  LVL3 - очередь за Cloudflare
    config.py            настройки уровня
    protocol.py          подпись claim + разбор SSE-потока
    clearance.py         ClearanceManager - cf_clearance через FlareSolverr
    runner.py            Lvl3Runner

run_lvl1.py              точка входа LVL1
run_lvl2.py              точка входа LVL2
run_lvl3.py              точка входа LVL3
```

Каждый уровень наследует `cupflag.common.BaseRunner`; LVL1/LVL2 дополнительно
используют `BurstRunner` с общим RTT-таймированным залпом на границе секунды.
Уровень задаёт только своё (вход, рабочие петли, строка статистики), а общий
жизненный цикл и тайминг живут один раз в базовых классах.

