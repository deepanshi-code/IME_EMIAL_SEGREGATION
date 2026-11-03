import calendar
import re
from datetime import date, timedelta

MONTHS = {name: number for number, names in enumerate(
    [None, ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",),
     ("jun", "june"), ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"),
     ("oct", "october"), ("nov", "november"), ("dec", "december")]) if names for name in names}
M = r"(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b\.?"
D = r"(\d{1,2})(?:st|nd|rd|th)?"
Y = r"(?:[ ,]*(20\d\d))?"
SEP = r"[ \t]*(?:-|–|/|_|to|till|until)[ \t]*"
PERIODS = [
    (r"early[ -]+(?:to[ -]+)?mid(?:dle)?", 1, 20), (r"first[ \t]+half", 1, 15), (r"second[ \t]+half", 16, 31),
    (r"early|beg(?:inning)?|ely", 1, 10), (r"mid(?:dle)?", 11, 20), (r"end|late", 21, 31),
]


def last_day(year, month):
    return calendar.monthrange(year, month)[1]


def make(year, month, day):
    return date(year, month, min(day, last_day(year, month)))


def pick_year(month, day, reference):
    # Broker dates rarely give the year: take the one that puts the date nearest to the email,
    # allowing up to two months in the past ("open 27 Dec" written on 2 Jan is last year's).
    candidates = [make(reference.year + offset, month, day) for offset in (-1, 0, 1)]
    future = [c for c in candidates if (c - reference).days >= -60]
    return min(future, key=lambda c: abs((c - reference).days)).year


def full(day, month_name, year, reference):
    month = MONTHS[month_name]
    year = int(year) if year else pick_year(month, int(day), reference)
    return make(year, month, int(day))


def parse_range(text, reference=None):
    """Turn a broker date phrase into (start, end) dates, or None when there is no date."""
    if not text:
        return None
    reference = reference or date.today()
    t = " ".join(str(text).lower().replace(",", " ").split())
    onwards = re.search(r"\bonw(?:ards?)?\b|\bonward\b|\bafter\b|\bfrom\b", t)

    def finish(start, end):
        if end < start:
            end = make(end.year + 1, end.month, end.day)
        if onwards and start == end:
            end = start + timedelta(days=14)
        return start, end

    # "29 Oct - 05 Nov", "22 Oct / 15 Nov 2026", "sep 28-oct 5"
    match = re.search(D + r"[ \t]*" + M + Y + SEP + D + r"[ \t]*" + M + Y, t)
    if match:
        d1, m1, y1, d2, m2, y2 = match.groups()
        end = full(d2, m2, y2, reference)
        return finish(full(d1, m1, y1 or (y2 if MONTHS[m1] <= MONTHS[m2] else None), reference), end)
    match = re.search(M + r"[ \t]*" + D + SEP + M + r"[ \t]*" + D + Y, t)
    if match:
        m1, d1, m2, d2, y = match.groups()
        return finish(full(d1, m1, y, reference), full(d2, m2, y, reference))
    # "12-14 Nov", "27-28/oct", "22/25 October", "25 to 30 Oct", "9-10th nov"
    match = re.search(D + SEP + D + r"[ \t/]*" + M + Y, t)
    if match:
        d1, d2, m, y = match.groups()
        return finish(full(d1, m, y, reference), full(d2, m, y, reference))
    # "nov 1-10", "Nov 15-20 2026"
    match = re.search(M + r"[ \t]*" + D + SEP + D + Y, t)
    if match:
        m, d1, d2, y = match.groups()
        return finish(full(d1, m, y, reference), full(d2, m, y, reference))
    # "31 October 2026", "19 oct", "03/nov", "27th September"
    match = re.search(D + r"[ \t/]*" + M + Y, t)
    if match:
        day = full(*match.groups(), reference)
        return finish(day, day)
    match = re.search(M + r"[ \t]*" + D + r"\b" + Y, t)
    if match:
        m, d, y = match.groups()
        day = full(d, m, y, reference)
        return finish(day, day)
    # Numeric: "1-10/11", "31.10/2.11", "16.11", "25.10.2026"
    match = re.search(r"\b(\d{1,2})[.](\d{1,2})[ \t]*/[ \t]*(\d{1,2})[.](\d{1,2})\b", t)
    if match:
        d1, m1, d2, m2 = map(int, match.groups())
        if 1 <= m1 <= 12 and 1 <= m2 <= 12:
            return finish(make(pick_year(m1, d1, reference), m1, d1), make(pick_year(m2, d2, reference), m2, d2))
    match = re.search(r"\b(\d{1,2})[ \t]*[-–][ \t]*(\d{1,2})[ \t]*/[ \t]*(\d{1,2})\b", t)
    if match:
        d1, d2, m = map(int, match.groups())
        if 1 <= m <= 12:
            year = pick_year(m, d1, reference)
            return finish(make(year, m, d1), make(year, m, d2))
    match = re.search(r"\b(\d{1,2})[.](\d{1,2})(?:[.](20\d\d))?\b", t)
    if match:
        d, m = int(match.group(1)), int(match.group(2))
        if 1 <= m <= 12:
            day = make(int(match.group(3)) if match.group(3) else pick_year(m, d, reference), m, d)
            return finish(day, day)
    # "mid Oct", "early-middle Nov", "first half of November", "end of November"
    for words, first, last in PERIODS:
        match = re.search(r"\b(?:" + words + r")[ \t-]*(?:of[ \t]+)?" + M + Y, t)
        if match:
            m, y = match.groups()
            month = MONTHS[m]
            year = int(y) if y else pick_year(month, first, reference)
            return finish(make(year, month, first), make(year, month, last))
    if re.search(r"\b(?:spot|prompt|ppt|asap|ready)\b", t):
        return reference, reference + timedelta(days=7)
    if re.search(r"\bnext[ \t]+week\b", t):
        return reference + timedelta(days=7), reference + timedelta(days=14)
    match = re.search(r"\b" + M + Y, t)
    if match:
        m, y = match.groups()
        month = MONTHS[m]
        year = int(y) if y else pick_year(month, 15, reference)
        return finish(make(year, month, 1), make(year, month, last_day(year, month)))
    return None
