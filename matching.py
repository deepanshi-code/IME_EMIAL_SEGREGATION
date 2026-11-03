import re
from datetime import date

from regions import proximity, region_of

# A vessel usually needs a few days to ballast to the load port; earlier than this and it will
# probably be fixed elsewhere before the cargo is ready.
EARLY_DAYS = 10


def as_date(value):
    return date.fromisoformat(value) if isinstance(value, str) and value else None


def date_fit(vessel, cargo):
    open_start, open_end = as_date(vessel.get("start")), as_date(vessel.get("end"))
    lay_start, lay_end = as_date(cargo.get("start")), as_date(cargo.get("end"))
    if not (open_start and lay_start):
        return 0, "dates unknown"
    if open_start > lay_end:
        return None, f"opens {open_start:%d %b}, after the laycan ends ({lay_end:%d %b})"
    if open_end >= lay_start:
        window = f"{open_start:%d %b}" if open_start == open_end else f"{open_start:%d %b}-{open_end:%d %b}"
        return 3, f"open {window}, overlaps the laycan ({lay_start:%d %b}-{lay_end:%d %b})"
    gap = (lay_start - open_end).days
    if gap <= EARLY_DAYS:
        return 2, f"opens {gap} days before the laycan"
    return 0, f"opens {gap} days before the laycan (may be fixed elsewhere first)"


LIQUID = re.compile(r"\b(?:crude|fuel ?oil|fueloil|gasoil|diesel|jet fuel|naphtha|lpg|lng|vegoil|veg oil|palm oil|"
                    r"chemicals?|uan|methanol|ethanol|molasses|ppm product|dpp|cpp)\b", re.IGNORECASE)


def size_fit(vessel, cargo):
    # Compare with the cargo capacity (DWCC) when it is stated; deadweight also counts fuel and stores,
    # so a cargo needs to stay under about 95% of DWT.
    dwcc, dwt = vessel.get("vessel_dwcc"), vessel.get("vessel_size")
    capacity, unit, limit = (dwcc, "DWCC", 1.0) if dwcc else (dwt, "DWT", 0.95)
    quantity = cargo.get("qty_max") or cargo.get("qty_min")
    if not capacity or not quantity:
        return 0, "size unknown"
    use = quantity / capacity
    if use > limit:
        return None, f"{quantity:,} t is too much for {capacity:,} {unit}"
    if use >= 0.7:
        return 3, f"{quantity:,} t fills {use:.0%} of {capacity:,} {unit}"
    if use >= 0.4:
        return 1, f"{quantity:,} t is a part cargo for {capacity:,} {unit} ({use:.0%})"
    return -1, f"{capacity:,} {unit} is much bigger than {quantity:,} t ({use:.0%})"


def type_fit(vessel, cargo):
    # The tonnage on broker boards is almost all dry cargo; liquid cargoes need a tanker.
    if LIQUID.search(cargo.get("cargo") or "") and not LIQUID.search(vessel.get("source") or ""):
        return -3, "liquid cargo needs a tanker; check the vessel type"
    return 0, None


def place_fit(vessel, cargo):
    open_port, load_port = vessel.get("open_port"), cargo.get("loading_port")
    score = proximity(open_port, load_port)
    if score == 3:
        return 3, f"opens at the load port ({load_port})"
    if score == 2:
        return 2, f"same region ({region_of(load_port)})"
    if score == 1:
        return 1, f"neighbouring region ({region_of(open_port)} → {region_of(load_port)})"
    if score == -1:
        return -2, f"far away ({region_of(open_port)} → {region_of(load_port)})"
    return 0, "location unknown"


def score_pair(vessel, cargo):
    """(score, reasons) for one vessel and one cargo, or (None, reasons) when it cannot work."""
    total, reasons = 0, []
    for check in (date_fit, size_fit, place_fit, type_fit):
        points, reason = check(vessel, cargo)
        if reason:
            reasons.append(reason)
        if points is None:
            return None, reasons
        total += points
    return total, reasons


def rank(target, candidates, target_is_cargo=True, limit=10):
    """Candidates for one cargo (or one vessel), best first, skipping impossible pairs."""
    ranked = []
    for candidate in candidates:
        vessel, cargo = (candidate, target) if target_is_cargo else (target, candidate)
        score, reasons = score_pair(vessel, cargo)
        if score is not None:
            ranked.append((score, candidate, reasons))
    ranked.sort(key=lambda item: -item[0])
    return ranked[:limit]
