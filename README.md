# agent-memory

A tiny persistent memory file for local agents — one Python file, stdlib only, no network, no API keys.

Pattern (patterns only, original code): persistent context across sessions (the idea behind today's big memory-layer tools) + never overwrite, supersede (the lesson from every stale-price / stale-decision bug: old facts must be retired visibly, not silently replaced). Each session starts by reading the digest; each session ends by recording what it learned.

## Why it exists

Daily agent cycles re-derive the same facts, decisions and lessons — and worse, they sometimes act on a fact that changed weeks ago. This keeps them in one plain JSON file any later session can read, search and inject into its prompt. The file is human-readable on purpose: `memory.json` is the audit trail.

## The one rule

**Supersede, never edit.** When a fact changes, run `supersede` — the old entry stays in the file but disappears from search results and digests, and the replacement takes its place. Nothing current is ever silently rewritten.

## Usage

```bash
python3 agent_memory.py --db memory.json add --kind fact \
  --text "Shop opens at 8 in Arak" --tags shop,hours
python3 agent_memory.py --db memory.json list --kind lesson
python3 agent_memory.py --db memory.json search "console prices"
python3 agent_memory.py --db memory.json supersede 3 \
  --by "Vigyato daily price carousel is the console-price source"
python3 agent_memory.py --db memory.json digest --days 7
python3 agent_memory.py --db memory.json prune --yes
```

Entry kinds: `fact`, `decision`, `lesson`. Exit codes: 0 ok, 1 nothing found, 2 bad input.

A typical session loop:

```bash
python3 agent_memory.py --db memory.json digest --days 30  # read before work
# ... do the work ...
python3 agent_memory.py --db memory.json add --kind lesson \
  --text "What this session learned" --tags session
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT — see `LICENSE`.

---

# agent-memory (فارسی)

یک فایل حافظه‌ی ماندگار و کوچک برای ایجنت‌های محلی — فقط یک فایل پایتون، فقط کتابخانه استاندارد، بدون شبکه و بدون کلید API.

**الگو:** حافظه‌ی ماندگار بین جلسه‌ها (ایده‌ی ابزارهای حافظه‌ی پرستاره‌ی امروز) + هرگز بازنویسی نکن، «منسوخ» کن: وقتی واقعیتی عوض شد، ورودی قدیمی به‌صورت قابل‌مشاهده کنار گذاشته می‌شود، نه اینکه بی‌صدا جایگزین شود. قیمت یا تصمیم قدیمی نباید دوباره به‌عنوان واقعیت روز برگردد.

**قانون اصلی:** با `supersede` ورودی قدیمی را منسوخ و ورودی تازه را جایگزین کن؛ ورودی قدیمی در فایل می‌ماند ولی از جستجو و خلاصه حذف می‌شود.

## اجرا

```bash
python3 agent_memory.py --db memory.json add --kind fact --text "..." --tags shop
python3 agent_memory.py --db memory.json search "قیمت کنسول"
python3 agent_memory.py --db memory.json supersede 3 --by "متن جایگزین"
python3 agent_memory.py --db memory.json digest --days 7
```

نوع ورودی‌ها: `fact` (واقعیت)، `decision` (تصمیم)، `lesson` (درس).

## تست

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT — see `LICENSE`.
