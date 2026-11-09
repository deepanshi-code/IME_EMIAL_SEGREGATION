"""HTML building blocks for the Streamlit app.

Every function returns an HTML string for st.html. Anything that comes from an email is passed
through esc(), because broker emails are untrusted input and must never be rendered as markup.
Colours are mid-tone accents on translucent backgrounds and text inherits the theme colour, so the
same markup reads correctly in the light and the dark theme.
"""
from html import escape

CATEGORY_LABELS = {"TONNAGE": "Vessel position", "CARGO VC": "Voyage cargo order",
                   "CARGO TC": "Time-charter enquiry", "UNKNOWN": "Not a chartering email"}
CATEGORY_ACCENTS = {"TONNAGE": "#2B8CC4", "CARGO VC": "#2E9E6B", "CARGO TC": "#8A63D2", "UNKNOWN": "#8A99A8"}
CONFIDENCE_ACCENTS = {"High": "#2E9E6B", "Medium": "#D99A1E", "Low": "#D2544B"}
CONFIDENCE_STEPS = {"High": 3, "Medium": 2, "Low": 1}
CONFIDENCE_TEXT = {"High": "clear evidence", "Medium": "probably right", "Low": "close call, check it"}

# Streamlit already loads the Material Symbols font for its own icons; st.html strips inline SVG.
ICON_NAMES = {"ship": "directions_boat", "box": "inventory_2", "clock": "schedule", "mail": "mail",
              "pin": "location_on", "calendar": "calendar_month", "weight": "scale", "anchor": "anchor"}
CATEGORY_ICON = {"TONNAGE": "ship", "CARGO VC": "box", "CARGO TC": "clock", "UNKNOWN": "mail"}


def esc(value):
    return escape(str(value), quote=True)


def icon(name, size=18):
    return f'<span class="ime-ico" style="font-size:{size}px" aria-hidden="true">{ICON_NAMES[name]}</span>'


def value_or_dash(value):
    return esc(value) if value else '<span class="ime-missing">not found</span>'


def tonnes(value):
    return "–".join(f"{int(part):,}" for part in str(value).split("-")) + " t"


STYLE = """
<style>
.ime-hero{position:relative;overflow:hidden;border-radius:16px;padding:28px 30px 34px;margin:0 0 6px;
  background:radial-gradient(1200px 300px at 85% -40%,#1f6f9a 0%,transparent 60%),
  linear-gradient(135deg,#0B2236 0%,#0F2A3D 55%,#123a55 100%);color:#EAF2F7;
  display:flex;flex-wrap:wrap;gap:22px 36px;align-items:flex-end;justify-content:space-between}
.ime-hero h1{font-size:2.05rem;line-height:1.15;font-weight:700;margin:4px 0 8px;padding:0;color:#fff;letter-spacing:-.01em}
.ime-hero p{margin:0;max-width:640px;font-size:1rem;color:#C9D8E3}
.ime-eyebrow{font-size:.78rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:#7FD0F2;
  display:flex;align-items:center;gap:8px}
.ime-steps{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px;align-items:center}
.ime-step{display:inline-flex;align-items:center;gap:7px;padding:6px 12px;border-radius:999px;font-size:.88rem;
  background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);color:#EAF2F7}
.ime-step b{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;
  background:#7FD0F2;color:#0B2236;font-size:.75rem}
.ime-arrow{color:#7FD0F2;opacity:.7}
.ime-stats{display:flex;gap:10px;flex-wrap:wrap;position:relative;z-index:1}
.ime-stat{min-width:112px;padding:12px 14px;border-radius:12px;background:rgba(255,255,255,.07);
  border:1px solid rgba(255,255,255,.13)}
.ime-stat strong{display:block;font-size:1.45rem;color:#fff;font-weight:700;line-height:1.1}
.ime-stat span{font-size:.78rem;color:#C9D8E3}
.ime-hero::after{content:"";position:absolute;left:-5%;right:-5%;bottom:-18px;height:56px;pointer-events:none;
  background:radial-gradient(40% 32px at 20% 100%,rgba(127,208,242,.16),transparent 72%),
  radial-gradient(45% 36px at 62% 100%,rgba(127,208,242,.11),transparent 72%),
  radial-gradient(35% 28px at 95% 100%,rgba(127,208,242,.14),transparent 72%)}
.ime-ico{font-family:"Material Symbols Rounded";font-weight:400;font-style:normal;line-height:1;letter-spacing:normal;
  text-transform:none;white-space:nowrap;direction:ltr;font-feature-settings:"liga";-webkit-font-smoothing:antialiased;
  display:inline-block;vertical-align:middle}

.ime-panel{border:1px solid rgba(127,150,170,.32);border-radius:14px;padding:18px 18px 16px;margin-bottom:12px;
  background:rgba(127,150,170,.05)}
.ime-result{border-left:5px solid var(--accent)}
.ime-head{display:flex;flex-wrap:wrap;align-items:center;gap:12px 16px;justify-content:space-between}
.ime-head-main{display:flex;align-items:center;gap:12px}
.ime-badge{display:grid;place-items:center;width:44px;height:44px;border-radius:12px;flex:none;
  background:color-mix(in srgb,var(--accent) 18%,transparent);color:var(--accent)}
.ime-kicker{font-size:.72rem;font-weight:600;letter-spacing:.09em;text-transform:uppercase;opacity:.72}
.ime-title{font-size:1.3rem;font-weight:700;line-height:1.2}
.ime-conf{display:flex;flex-direction:column;align-items:flex-start;gap:5px}
.ime-meter{display:flex;gap:4px}
.ime-meter i{width:26px;height:7px;border-radius:4px;background:rgba(127,150,170,.3)}
.ime-meter i.on{background:var(--conf)}
.ime-conf-label{font-size:.85rem}
.ime-conf-label b{color:inherit}
.ime-reason{margin:14px 0 4px;font-size:.95rem;line-height:1.5}
.ime-review{margin:14px 0 4px;padding:10px 12px;border-radius:10px;font-size:.93rem;line-height:1.5;
  background:color-mix(in srgb,#D99A1E 14%,transparent);border:1px solid color-mix(in srgb,#D99A1E 45%,transparent)}
.ime-section{margin:16px 0 8px;font-size:.78rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;opacity:.72}
.ime-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.ime-card{border:1px solid rgba(127,150,170,.3);border-radius:12px;padding:12px 14px;background:rgba(127,150,170,.06)}
.ime-card-top{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px 8px;margin-bottom:8px}
.ime-name{font-weight:700;font-size:1.02rem;letter-spacing:.01em;display:inline-flex;align-items:center;gap:6px;white-space:nowrap;max-width:100%;overflow:hidden;text-overflow:ellipsis}
.ime-tag{font-size:.78rem;font-weight:600;padding:2px 8px;border-radius:999px;white-space:nowrap;
  background:color-mix(in srgb,var(--accent) 16%,transparent)}
.ime-row{display:flex;align-items:center;gap:8px;font-size:.9rem;margin-top:5px}
.ime-row .ime-ico{opacity:.65;flex:none}
.ime-missing{opacity:.55;font-style:italic}
.ime-route{display:flex;align-items:center;gap:10px;margin:2px 0 8px}
.ime-port{display:flex;flex-direction:column;font-weight:700;font-size:.98rem;min-width:0}
.ime-port small{font-size:.68rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;opacity:.65}
.ime-port.end{text-align:right;align-items:flex-end}
.ime-line{flex:1;min-width:30px;height:2px;position:relative;
  background:repeating-linear-gradient(90deg,var(--accent) 0 6px,transparent 6px 11px)}
.ime-line::after{content:"";position:absolute;right:-2px;top:-4px;border-left:8px solid var(--accent);
  border-top:5px solid transparent;border-bottom:5px solid transparent}
.ime-note{font-size:.88rem;opacity:.8;margin-top:6px}

.ime-bars{display:grid;grid-template-columns:minmax(110px,auto) 1fr 30px;gap:8px 10px;align-items:center;font-size:.88rem}
.ime-bar{position:relative;height:10px;border-radius:6px;background:rgba(127,150,170,.2)}
.ime-bar i{position:absolute;left:0;top:0;bottom:0;border-radius:6px;background:var(--accent)}
.ime-bar em{position:absolute;top:-4px;bottom:-4px;width:2px;background:currentColor;opacity:.45}
.ime-bars b{text-align:right}
.ime-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.ime-chip{font-size:.8rem;padding:3px 10px;border-radius:999px;border:1px solid rgba(127,150,170,.38);
  background:rgba(127,150,170,.08)}
.ime-foot{font-size:.8rem;opacity:.7;margin-top:10px}

.ime-dist{display:flex;height:12px;border-radius:7px;overflow:hidden;margin:4px 0 8px;background:rgba(127,150,170,.2)}
.ime-dist i{display:block;height:100%}
.ime-legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.84rem}
.ime-legend span{display:inline-flex;align-items:center;gap:6px}
.ime-legend span::before{content:"";width:10px;height:10px;border-radius:3px;background:var(--accent)}

.ime-match{display:grid;grid-template-columns:auto 1fr auto;gap:14px;align-items:start}
.ime-rank{font-weight:700;font-size:.85rem;padding:4px 9px;border-radius:8px;
  background:color-mix(in srgb,var(--accent) 16%,transparent)}
.ime-score{text-align:center;min-width:64px}
.ime-score strong{display:block;font-size:1.7rem;line-height:1;font-weight:700}
.ime-score span{font-size:.75rem;opacity:.7}
.ime-subs{display:flex;flex-wrap:wrap;gap:8px 18px;margin:8px 0 4px}
.ime-sub{display:flex;align-items:center;gap:7px;font-size:.84rem}
.ime-dots{display:flex;gap:3px}
.ime-dots i{width:9px;height:9px;border-radius:3px;background:rgba(127,150,170,.3)}
.ime-dots i.on{background:#2E9E6B}
.ime-dots i.neg{background:#D2544B}
.ime-why{margin:6px 0 0;padding-left:18px;font-size:.86rem;line-height:1.5;opacity:.88}
@media (max-width:640px){
  .ime-hero{padding:20px 18px 30px}.ime-hero h1{font-size:1.5rem}.ime-hero p{font-size:.92rem}
  .ime-stats{display:grid;grid-template-columns:repeat(3,1fr);width:100%;gap:6px}
  .ime-stat{min-width:0;padding:8px 9px}.ime-stat strong{font-size:1.1rem}.ime-stat span{font-size:.7rem;line-height:1.25;display:block}
  .ime-arrow{display:none}.ime-steps{gap:6px;margin-top:12px}.ime-step{font-size:.8rem;padding:4px 10px}
  .ime-conf{align-items:flex-start}.ime-match{grid-template-columns:1fr auto}.ime-rank{display:none}
}
</style>
"""


def hero(stats):
    tiles = "".join(f'<div class="ime-stat"><strong>{esc(value)}</strong><span>{esc(label)}</span></div>'
                    for value, label in stats)
    steps = '<span class="ime-arrow">→</span>'.join(
        f'<span class="ime-step"><b>{n}</b>{label}</span>'
        for n, label in [(1, "Sort each email"), (2, "Extract every vessel and cargo"), (3, "Match vessels to cargoes")])
    return f"""
<div class="ime-hero">
  <div>
    <div class="ime-eyebrow">{icon("anchor", 15)} Chartering desk assistant</div>
    <h1>Chartering Email Segregation</h1>
    <p>Turns dense shipbroker circulars into a searchable positions board, then suggests which open
    vessels fit which cargo orders, with a reason for every decision.</p>
    <div class="ime-steps">{steps}</div>
  </div>
  <div class="ime-stats" aria-label="Results on held-out real emails">{tiles}</div>
</div>"""


def confidence_meter(level):
    steps = CONFIDENCE_STEPS[level]
    bars = "".join(f'<i class="{"on" if i < steps else ""}"></i>' for i in range(3))
    return (f'<div class="ime-conf" style="--conf:{CONFIDENCE_ACCENTS[level]}">'
            f'<div class="ime-meter" role="img" aria-label="{level} confidence">{bars}</div>'
            f'<div class="ime-conf-label"><b>{level} confidence</b> · {CONFIDENCE_TEXT[level]}</div></div>')


def vessel_card(record):
    size = (f'{int(record["Vessel Size"]):,} DWT' if record.get("Vessel Size") else
            f'{int(record["Cargo Capacity"]):,} DWCC' if record.get("Cargo Capacity") else "")
    tag = f'<span class="ime-tag">{esc(size)}</span>' if size else ""
    return f"""<div class="ime-card"><div class="ime-card-top">
  <span class="ime-name">{icon("ship", 16)} {value_or_dash(record.get("Vessel Name"))}</span>{tag}</div>
  <div class="ime-row">{icon("pin", 16)} Open at&nbsp;<b>{value_or_dash(record.get("Open Port"))}</b></div>
  <div class="ime-row">{icon("calendar", 16)} {value_or_dash(record.get("Open Date"))}</div></div>"""


def route(start_label, start, end_label, end):
    return f"""<div class="ime-route">
  <div class="ime-port"><small>{start_label}</small>{value_or_dash(start)}</div>
  <div class="ime-line" aria-hidden="true"></div>
  <div class="ime-port end"><small>{end_label}</small>{value_or_dash(end)}</div></div>"""


def cargo_card(record):
    quantity = tonnes(record["Quantity"]) if record.get("Quantity") else None
    return f"""<div class="ime-card">{route("Load", record.get("Loading Port"), "Discharge", record.get("Discharge Port"))}
  <div class="ime-row">{icon("weight", 16)} {value_or_dash(quantity)} · {value_or_dash(record.get("Cargo"))}</div>
  <div class="ime-row">{icon("calendar", 16)} Laycan&nbsp;{value_or_dash(record.get("Laycan"))}</div></div>"""


def charter_card(fields):
    size = f'<div class="ime-row">{icon("ship", 16)} {int(fields["Vessel Size"]):,} DWT</div>' if fields.get("Vessel Size") else ""
    return f"""<div class="ime-card">{route("Delivery", fields.get("Delivery Port"), "Redelivery", fields.get("Redelivery Port"))}
  <div class="ime-row">{icon("clock", 16)} Period&nbsp;{value_or_dash(fields.get("Duration"))}</div>{size}</div>"""


def result_card(result):
    category = result["category"]
    if category == "TONNAGE":
        records = result["records"] or [result["fields"]]
        noun = "vessel position" if len(records) == 1 else "vessel positions"
        cards = "".join(vessel_card(r) for r in records)
    elif category == "CARGO VC":
        records = result["records"] or [result["fields"]]
        noun = "cargo order" if len(records) == 1 else "cargo orders"
        cards = "".join(cargo_card(r) for r in records)
    elif category == "CARGO TC":
        records, noun, cards = [result["fields"]], "enquiry", charter_card(result["fields"])
    else:
        records, noun, cards = [], "", ""
    reason_class = "ime-review" if result["needs_review"] else "ime-reason"
    details = (f'<div class="ime-section">Extracted · {len(records)} {noun}</div><div class="ime-grid">{cards}</div>'
               if cards else '<div class="ime-note">Nothing to extract: this email is not a vessel position, '
                             'cargo order or time-charter enquiry.</div>')
    return f"""<div class="ime-panel ime-result" style="--accent:{CATEGORY_ACCENTS[category]}">
  <div class="ime-head"><div class="ime-head-main"><div class="ime-badge">{icon(CATEGORY_ICON[category], 24)}</div>
    <div><div class="ime-kicker">Classified as</div><div class="ime-title">{CATEGORY_LABELS[category]}</div></div></div>
    {confidence_meter(result["confidence"])}</div>
  <div class="{reason_class}">{esc(result["reason"])}</div>{details}</div>"""


def evidence_panel(scores, winner, labels, threshold):
    top = max(max(scores.values()), threshold * 2)
    rows = []
    for category, score in sorted(scores.items(), key=lambda item: -item[1]):
        width = max(score, 0) / top * 100
        rows.append(f'<span>{CATEGORY_LABELS[category]}</span>'
                    f'<div class="ime-bar" style="--accent:{CATEGORY_ACCENTS[category]}"><i style="width:{width:.0f}%"></i>'
                    f'<em style="left:{threshold / top * 100:.0f}%"></em></div><b>{score}</b>')
    chips = "".join(f'<span class="ime-chip">{esc(label)}</span>' for label in labels)
    chip_block = (f'<div class="ime-section">Evidence found for {CATEGORY_LABELS[winner].lower()}</div>'
                  f'<div class="ime-chips">{chips}</div>') if chips else ""
    return f"""<div class="ime-panel"><div class="ime-kicker">How it decided</div>
  <div class="ime-bars" style="margin-top:12px">{"".join(rows)}</div>{chip_block}
  <div class="ime-foot">Each rule that fires adds points to a type. The highest total wins; below
  {threshold} points (the line) the email counts as not chartering.</div></div>"""


def distribution(counts, names):
    total = sum(counts.values()) or 1
    segments = "".join(f'<i style="width:{counts.get(c, 0) / total * 100:.2f}%;background:{CATEGORY_ACCENTS[c]}" '
                       f'title="{names[c]}: {counts.get(c, 0)}"></i>' for c in names)
    legend = "".join(f'<span style="--accent:{CATEGORY_ACCENTS[c]}">{names[c]} · <b>{counts.get(c, 0)}</b></span>'
                     for c in names)
    return f'<div class="ime-dist" role="img" aria-label="Emails by type">{segments}</div><div class="ime-legend">{legend}</div>'


def dots(points):
    if points is None:
        points = 0
    cells = "".join(f'<i class="{"neg" if points < 0 and i < -points else "on" if i < points else ""}"></i>'
                    for i in range(3))
    return f'<span class="ime-dots" aria-hidden="true">{cells}</span>'


def match_card(rank, score, label, parts, reasons, maximum=9):
    accent = "#2E9E6B" if score >= 6 else "#D99A1E" if score >= 3 else "#8A99A8"
    # Darker shades for the score number: >= 3:1 (large text) on both the light and the dark panel.
    number = "#23855A" if score >= 6 else "#B26B00" if score >= 3 else "#6B7C8C"
    subs = "".join(f'<span class="ime-sub">{name} {dots(points)} <b>{points:+d}</b></span>'
                   for name, points in parts)
    why = "".join(f"<li>{esc(reason)}</li>" for reason in reasons)
    return f"""<div class="ime-panel" style="--accent:{accent}"><div class="ime-match">
  <span class="ime-rank">#{rank}</span>
  <div><div class="ime-name">{esc(label)}</div><div class="ime-subs">{subs}</div><ul class="ime-why">{why}</ul></div>
  <div class="ime-score"><strong style="color:{number}">{score:+d}</strong><span>of {maximum}</span></div></div></div>"""
