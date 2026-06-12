# WRITEUP - LVL3

## Запуск

Нужен запущенный FlareSolverr (headless-браузер для прохождения Cloudflare):

```bash
docker run -d --name flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr:latest
python run_lvl3.py --duration 300
```

Флаги - в stdout и `flags_lvl3.jsonl`. Полный трейс запросов/ответов - в
`lvl3_io.jsonl`.

## Архитектура решения

Код - в `cupflag/lvl3/`: `protocol.py` (подпись claim + разбор SSE), `clearance.py`
(`ClearanceManager` - вся работа с Cloudflare/FlareSolverr), `runner.py`, `config.py`.

**Реальная защита уровня - Cloudflare managed JS-challenge** на всём поддомене:
`/login` и `/v1/queue/*` отдают `403` «Just a moment…». Имитация TLS-отпечатка
браузера не помогает - нужен настоящий браузер для выдачи cookie `cf_clearance`
(привязан к IP+User-Agent, TTL ~30 мин). На LVL1/LVL2 такого нет.

**Прохождение гейта.** `ClearanceManager` один раз прогоняет челлендж через
**FlareSolverr**, забирает `cf_clearance` и точный User-Agent и переиспользует их в
`httpx`-клиенте c **HTTP/2**; при `403`/по истечении TTL - пересолвит.

**Протокол очереди** (реверс из `capture.js`+`guard.js`, подтверждён вживую):

```
POST /v1/queue/join                 -> {queue_token, ttl_sec:30}
GET  /v1/queue/wait?queue_token=...   (SSE: joined / tick / open / closed)
POST /v1/queue/claim {queue_token, book_key, captcha_token, timestamp, signature}
```

Событие `open` возвращает `server_time`, `claim_at`, `window_ms`, `book_key`. Claim
должен **долететь** в окно `[claim_at, claim_at + window_ms]`.

- **Подпись claim подделывается** ключом из `guard.js`:
  `signature = HMAC_SHA256("00000-0000-0000", f"{queue_token}:{timestamp}")` -
  подделанная подпись принимается и даёт настоящий флаг.
- **Капча не проверяется** (как на LVL2) - dummy-токен.

**Тайминг claim.**

- **HTTP/2.** SSE-стрим `wait` держит соединение; claim **мультиплексируется в то
  же тёплое соединение** (без нового TLS-хендшейка), и RTT claim'а падает с
  ~300–400 мс до ~65 мс. Это и сделало захваты возможными. (Проверено: пул держит
  одно соединение, claim не блокируется открытым SSE-стримом.)
- **Расчёт задержки.** Целимся в раннюю часть окна:
  `wait = (claim_at − server_time) + margin − RTT`. Скос часов сокращается, RTT -
  **медиана** последних claim'ов. По I/O-логу
  выяснено, что claim принимается, только если прилетел в **первую ~четверть**
  окна, поэтому `margin = min(25 мс, 0.25 × window)` - небольшое упреждение в
  начало окна, не в середину.
- **cycle_timeout.** Если за ~28 c в `wait` не пришло `open`/`closed`, обрываем
  поток и пере-джойнимся (защита от зависания, когда слот не открывается).

Очередь **глобальная** - параллельные циклы получают те же `book_key` и
сталкиваются, поэтому один поток (`concurrency=1`).

**I/O-лог.** Каждый `join`, каждое SSE-событие и каждый claim (запрос+ответ) с
таймингом пишутся в `lvl3_io.jsonl` - по нему калибруется тайминг и видно причину
каждого промаха.

**Результат:** ~3–4 флага/мин при конверсии claim'ов ~55–67% (зависит от сети).
Остаточные промахи - окна короче мгновенного RTT, что
неустранимо.

> Эндпоинт `claim` тоже лимитируется (токен-бакет): при плотном потоке окон
> claim'ы иногда ловят `rate_limited` с `retry_after`. Это редко и не критично.

## Найденные уязвимости

1. **Подделываемая подпись claim - клиентский HMAC-ключ** `atob("MDAwMDAtMDAwMC0wMDAw")`
   = `"00000-0000-0000"`.
2. **Капча не проверяется и здесь** - `captcha_token` любой непустой.
3. **Единственная реальная защита - Cloudflare-челлендж.** Всё прикладное (auth,
   капча, подпись) обходится; реально мешает только managed challenge, и тот
   снимается готовым headless-прокси (FlareSolverr).
4. **Наследуется:** пароль `md5(username)`; флаги/расписание глобальные.
