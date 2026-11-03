import io
import json
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import board as boardstore
import matching
from inbox import IMAP_HOSTS, read_imap, read_mbox
from pipeline import (
    CATEGORY_NAMES, FIELD_NAMES, TEXT_COLUMN_HINTS, decode_text, format_quantity, guess_column, parse_eml,
    process_email, read_csv, records_table, results_table,
)
from regions import REGIONS

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_CSV = os.path.join(APP_DIR, "samples", "demo_emails.csv")
DEMO_BOARD_CSV = os.path.join(APP_DIR, "samples", "demo_board.csv")
BOARD_COLUMNS = {
    "category": "Type", "vessel_name": "Vessel", "vessel_size": "DWT", "vessel_dwcc": "DWCC", "open_port": "Open port",
    "open_date": "Open date", "loading_port": "Load port", "discharge_port": "Discharge port", "cargo": "Cargo",
    "quantity": "Quantity (t)", "laycan": "Laycan", "start": "From", "end": "To", "region": "Region",
    "confidence": "Confidence", "received": "Received", "source": "Source",
}
CATEGORIES = ["TONNAGE", "CARGO VC", "CARGO TC", "UNKNOWN"]
SHORT_NAMES = {"TONNAGE": "Vessels", "CARGO VC": "Cargo orders", "CARGO TC": "TC enquiries", "UNKNOWN": "Other"}
CATEGORY_COLORS = {"TONNAGE": "blue", "CARGO VC": "green", "CARGO TC": "violet", "UNKNOWN": "gray"}
CONFIDENCE_COLORS = {"High": "green", "Medium": "orange", "Low": "red"}
SAMPLES = {
    "Vessel position": "MV SEA HAWK 58,000 DWT\nOPEN TIANJIN 10-12 DEC\nGEARED 4X30T\nPLS OFFER SUITABLE CARGO",
    "Cargo order": "Pls offer firm for;\nMundra / Chittagong\n12,000 mt bagged sugar\n5-10 Dec\n2000x / 1500x\n2.5% ttl",
    "Vessel list": (
        "Please propose cargoes for our home tonnage:\n"
        "M/V SEA HAWK : 5,200 DWT – Open at Constanta 12-14 Nov.\n"
        "M/V BLUE ARROW : 3,800 DWT – Open at Izmir 15-17 Nov.\n"
        "M/V NORTH STAR : 7,050 DWT – Open at Alexandria 20-22 Nov."
    ),
    "Time charter": "Period enquiry\nDel: Haldia\nRedel: Far East\nPeriod: 11-13 months\nKamsarmax required",
    "Tricky case": (
        "Hi John, we have a vessel available for a crude oil shipment from Houston to Rotterdam. "
        "The vessel is the MV Ocean Star, 150,000 DWT. The laycan is 15-20 October. Freight USD 20/MT."
    ),
    "Normal email": "Hi Sarah,\n\nCould we move the budget review to Thursday afternoon?\n\nThanks,\nDaniel",
}


def format_value(name, value):
    if name == "Vessel Size":
        return f"{int(value):,} DWT"
    return format_quantity(value) if name == "Quantity" else value


def records_frame(records):
    frame = pd.DataFrame(records)
    frame = frame.dropna(axis=1, how="all").fillna("")
    for name in ("Vessel Size", "Quantity"):
        if name in frame:
            frame[name] = [format_value(name, v) if v else "" for v in frame[name]]
    frame.index = range(1, len(frame) + 1)
    return frame


def result_card(result, compact=False):
    # compact: the card sits in a half-width column, so badges and fields stack instead of sitting side by side.
    with st.container(border=True):
        if compact:
            st.badge(CATEGORY_NAMES[result["category"]].capitalize(), color=CATEGORY_COLORS[result["category"]])
            st.badge(f"{result['confidence']} confidence", color=CONFIDENCE_COLORS[result["confidence"]])
        else:
            badges = st.columns([3, 2], vertical_alignment="center")
            with badges[0]:
                st.badge(CATEGORY_NAMES[result["category"]].capitalize(), color=CATEGORY_COLORS[result["category"]])
                st.caption(f"Category: {result['category']}")
            with badges[1]:
                st.badge(f"{result['confidence']} confidence", color=CONFIDENCE_COLORS[result["confidence"]])

        if result["needs_review"]:
            st.warning(result["reason"], icon=":material/visibility:")
        else:
            st.write(result["reason"])

        found = [(name, value) for name, value in result["fields"].items() if value]
        if found and compact:
            st.markdown("\n".join(f"- **{name}:** {format_value(name, value)}" for name, value in found))
        elif found:
            columns = st.columns(min(len(found), 3))
            for i, (name, value) in enumerate(found):
                columns[i % len(columns)].metric(name, format_value(name, value))
        elif result["category"] != "UNKNOWN":
            st.info("The category was recognised, but no fields could be extracted.")

        if len(result["records"]) > 1:
            noun = "vessel positions" if result["category"] == "TONNAGE" else "cargo orders"
            st.caption(f"{len(result['records'])} {noun} found in this email (the first is shown above):")
            st.dataframe(records_frame(result["records"]), width="stretch")


def load_sample(name):
    st.session_state["email_text"] = SAMPLES[name]
    st.session_state["auto_process"] = True


def read_uploads(uploads):
    sources, texts = [], []
    for upload in uploads:
        raw = upload.getvalue()
        name = upload.name.lower()
        try:
            if name.endswith(".eml"):
                sources.append(upload.name)
                texts.append(parse_eml(raw))
            elif name.endswith(".txt"):
                sources.append(upload.name)
                texts.append(decode_text(raw))
            else:
                frame = read_csv(raw)
                if frame.empty:
                    st.warning(f"{upload.name} has no rows.")
                    continue
                columns = list(frame.columns)
                left, right = st.columns(2)
                text_column = left.selectbox(
                    f"Email text column in {upload.name}", columns,
                    index=columns.index(guess_column(columns, TEXT_COLUMN_HINTS)),
                    key=f"text-{upload.name}",
                )
                subject_options = ["(none)"] + columns
                has_subject = any("subject" in c.lower() for c in columns)
                subject_column = right.selectbox(
                    f"Subject column in {upload.name} (optional)", subject_options,
                    index=subject_options.index(guess_column(columns, ["subject"]) if has_subject else "(none)"),
                    key=f"subject-{upload.name}",
                )
                for i, row in frame.iterrows():
                    text = row[text_column]
                    if subject_column != "(none)":
                        text = f"Subject: {row[subject_column]}\n\n{text}"
                    sources.append(f"{upload.name} row {i + 2}")
                    texts.append(text)
        except Exception as error:
            st.error(f"Could not read {upload.name}: {error}")
    return sources, texts


def demo_batch():
    with open(DEMO_CSV, "rb") as f:
        frame = read_csv(f.read())
    return [f"demo row {i + 2}" for i in range(len(frame))], list(frame["email_text"])


def positions():
    # One board per browser session (in memory) unless POSITIONS_DB points at a file on your own machine.
    if "board" not in st.session_state:
        st.session_state["board"] = boardstore.connect(os.environ.get("POSITIONS_DB", ":memory:"))
    return st.session_state["board"]


def add_to_board(items):
    added = boardstore.add(positions(), items)
    st.success(f"Added {added} new vessel positions and cargo orders to the positions board"
               + ("" if added else " (all were already there)") + ".")


def load_demo_board():
    with open(DEMO_BOARD_CSV, "rb") as f:
        frame = read_csv(f.read())
    items = [(row["id"], row["email_text"], process_email(row["email_text"]), date.today())
             for _, row in frame.iterrows()]
    boardstore.add(positions(), items)


def board_label(row):
    if row["category"] == "TONNAGE":
        size = f"{row['vessel_size']:,} DWT" if row["vessel_size"] else (
            f"{row['vessel_dwcc']:,} DWCC" if row["vessel_dwcc"] else "size ?")
        return f"{row['vessel_name'] or 'Unnamed vessel'} · {size} · open {row['open_port'] or '?'} {row['open_date'] or ''}"
    quantity = format_quantity(row["quantity"]) if row["quantity"] else "? t"
    return (f"{quantity} {row['cargo'] or 'cargo'} · {row['loading_port'] or '?'} → {row['discharge_port'] or '?'}"
            f" · laycan {row['laycan'] or '?'}")


def excel_bytes(frame):
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False, sheet_name="Positions board")
    return buffer.getvalue()


st.set_page_config(page_title="Email Segregation", page_icon=":material/mail:", layout="wide")

with st.sidebar:
    st.header("About")
    st.write(
        "Sorts shipbroker emails into four types and pulls out the key details, "
        "so a chartering desk can see positions and orders at a glance."
    )
    st.markdown(
        "- **Vessel position** (TONNAGE): a ship looking for cargo – name, DWT, open port\n"
        "- **Voyage cargo order** (CARGO VC): a cargo looking for a ship – load and discharge port\n"
        "- **Time-charter enquiry** (CARGO TC): a ship wanted on hire – delivery, redelivery, duration\n"
        "- **Not chartering** (UNKNOWN): everything else"
    )
    st.subheader("Reading the confidence")
    st.markdown(
        "- **High** – strong, unambiguous evidence\n"
        "- **Medium** – probably right\n"
        "- **Low** – close call or weak evidence; check it yourself"
    )
    st.subheader("How well it works")
    st.markdown(
        "On 30 fresh real broker circulars not seen during development: **83%** sorted correctly, "
        "**66%** of details extracted correctly, **96%** of vessel/cargo counts right. "
        "On 300 normal emails, 1 was wrongly flagged.\n\n"
        "Rule-based, so every decision can be explained. Matches are suggestions to check, not fixtures."
    )

st.title("Chartering Email Segregation")
st.caption("IME Innovation Challenge – sort broker emails, build a positions board, and match vessels to cargoes.")

single_tab, batch_tab, inbox_tab, board_tab, match_tab = st.tabs(
    ["Single email", "Batch upload", "Inbox", "Positions board", "Matches"])

with single_tab:
    st.write("Try a sample:")
    sample_columns = st.columns(len(SAMPLES))
    for column, name in zip(sample_columns, SAMPLES):
        column.button(name, on_click=load_sample, args=(name,), width="stretch")

    with st.form("single-email"):
        email_text = st.text_area("Email text", height=220, key="email_text",
                                  placeholder="Paste a chartering email here…")
        submitted = st.form_submit_button("Process email", type="primary")

    if submitted or st.session_state.pop("auto_process", False):
        if email_text.strip():
            result = process_email(email_text)
            result_card(result)
            with st.expander("Technical details"):
                output = {
                    "Category": result["category"],
                    "Confidence": result["confidence"],
                    "Reason": result["reason"],
                    "Scores": result["scores"],
                    "Extracted Data": {name: value for name, value in result["fields"].items() if value},
                }
                st.json(output)
                st.download_button("Download JSON", data=json.dumps(output, indent=4), file_name="output.json")
        else:
            st.warning("Paste an email or pick a sample first.")

with batch_tab:
    uploads = st.file_uploader(
        "Upload .txt or .eml files (one email each), or a .csv with one email per row",
        type=["txt", "eml", "csv"],
        accept_multiple_files=True,
    )
    demo_on = st.toggle("Include the 42 demo emails", key="demo_batch",
                        help="Hand-written sample emails covering all four types, from samples/demo_emails.csv")

    sources, texts = read_uploads(uploads or [])
    if demo_on:
        demo_sources, demo_texts = demo_batch()
        sources, texts = sources + demo_sources, texts + demo_texts
    pairs = [(source, text) for source, text in zip(sources, texts) if text and text.strip()]

    if not pairs:
        st.info("Upload emails or switch on the demo emails to see results.")
    else:
        sources = [source for source, _ in pairs]
        texts = [text for _, text in pairs]
        results = [process_email(text) for text in texts]
        table = results_table(sources, results)

        counts = table["Category"].value_counts()
        metrics = st.columns(len(CATEGORIES) + 2)
        metrics[0].metric("Emails", len(table))
        for column, category in zip(metrics[1:], CATEGORIES):
            column.metric(SHORT_NAMES[category], int(counts.get(category, 0)))
        metrics[-1].metric("To review", int(table["Needs Review"].sum()))

        left, middle, right = st.columns([3, 1, 1], vertical_alignment="bottom")
        chosen = left.multiselect("Show", CATEGORIES, default=CATEGORIES,
                                  format_func=lambda c: CATEGORY_NAMES[c].capitalize())
        review_only = middle.toggle("Needs review only")
        all_columns = right.toggle("All columns")

        view = table[table["Category"].isin(chosen)]
        if review_only:
            view = view[view["Needs Review"]]
        view = view.sort_values("Needs Review", ascending=False, kind="stable")
        if all_columns:
            view = view.dropna(axis=1, how="all").fillna("")
        else:
            view = view[["Source", "Category", "Confidence", "Needs Review", "Records", "Key Details", "Why"]]
            view = view.assign(Records=view["Records"].fillna("").astype(str).str.replace(".0", "", regex=False))
            view = view.assign(Category=view["Category"].map(lambda c: CATEGORY_NAMES[c].capitalize()))

        if view.empty:
            st.info("No emails match these filters.")
        else:
            st.caption("Click a row to read the email and its result. Emails that need review are listed first.")
            selection = st.dataframe(
                view,
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "Needs Review": st.column_config.CheckboxColumn("Review", width="small"),
                    "Confidence": st.column_config.TextColumn(width="small"),
                    "Key Details": st.column_config.TextColumn(width="large"),
                    "Why": st.column_config.TextColumn(width="large"),
                },
            )
            rows = selection.selection.rows
            if rows:
                index = view.index[rows[0]]
                st.subheader(sources[index])
                left, right = st.columns(2)
                left.text_area("Email", texts[index], height=260, disabled=True, key=f"view-{index}")
                with right:
                    result_card(results[index], compact=True)

        batch_records = records_table(sources, results).dropna(axis=1, how="all")
        downloads = st.columns(3)
        downloads[0].download_button(
            "Download results CSV (one row per email)",
            data=table.to_csv(index=False).encode("utf-8-sig"),
            file_name="email_segregation_results.csv",
            mime="text/csv",
        )
        downloads[1].download_button(
            f"Download records CSV ({len(batch_records)} vessels and cargoes)",
            data=batch_records.to_csv(index=False).encode("utf-8-sig"),
            file_name="positions_board.csv",
            mime="text/csv",
            disabled=batch_records.empty,
        )
        if downloads[2].button("Add to positions board", type="primary", disabled=batch_records.empty):
            add_to_board([(source, text, result, None) for source, text, result in zip(sources, texts, results)])

with inbox_tab:
    st.write("Read emails straight from a mailbox. Results go to the **Positions board** and **Matches** tabs.")
    left, right = st.columns(2)
    with left:
        st.subheader("Upload an exported mailbox")
        st.caption("Export a folder as .mbox from Gmail (Google Takeout), Thunderbird or Apple Mail. "
                   "Nothing leaves this app session and no password is needed.")
        mbox = st.file_uploader("Mailbox file (.mbox)", type=["mbox"], key="mbox")
        if mbox is not None and st.button("Read mailbox file"):
            try:
                st.session_state["inbox_items"] = read_mbox(mbox.getvalue())
            except Exception as error:
                st.error(f"Could not read {mbox.name}: {error}")
    with right:
        st.subheader("Connect by IMAP (read-only)")
        st.caption("The folder is opened read-only: nothing is deleted, moved or marked as read. "
                   "Use an **app password** (Gmail: Google Account → Security → App passwords), never your "
                   "normal password, and prefer running this app on your own computer: on a shared "
                   "deployment, the server you type into belongs to whoever hosts it. Credentials are used for "
                   "this request only and are not stored.")
        with st.form("imap"):
            provider = st.selectbox("Provider", list(IMAP_HOSTS) + ["Other"])
            host = st.text_input("IMAP server", placeholder="imap.example.com",
                                 help="Only needed for 'Other'; otherwise the provider's server is used.")
            user = st.text_input("Email address")
            password = st.text_input("App password", type="password")
            folder = st.text_input("Folder", value="INBOX")
            days = st.slider("Emails from the last … days", 1, 30, 7)
            limit = st.number_input("At most this many emails", 10, 500, 100, step=10)
            connect_now = st.form_submit_button("Read inbox (read-only)")
        if connect_now:
            server = host.strip() if provider == "Other" else IMAP_HOSTS[provider]
            if not (server and user and password):
                st.warning("Fill in the server, email address and app password.")
            else:
                try:
                    with st.spinner("Reading the mailbox…"):
                        st.session_state["inbox_items"] = read_imap(server, user, password, folder, days, int(limit))
                except Exception as error:
                    st.error(f"Could not read the mailbox: {error}")
                finally:
                    password = None

    items = st.session_state.get("inbox_items")
    if items is not None:
        results = [process_email(item["text"]) for item in items]
        shipping = sum(r["category"] != "UNKNOWN" for r in results)
        st.subheader(f"{len(items)} emails read · {shipping} chartering emails")
        inbox_table = pd.DataFrame([{
            "Received": item["received"], "Email": item["source"],
            "Type": CATEGORY_NAMES[r["category"]].capitalize(), "Confidence": r["confidence"],
            "Records": len(r["records"]) or "", "Why": r["reason"],
        } for item, r in zip(items, results)])
        st.dataframe(inbox_table, width="stretch", hide_index=True)
        if st.button("Add chartering emails to the positions board", type="primary", disabled=not shipping):
            add_to_board([(item["source"], item["text"], r, item["received"])
                          for item, r in zip(items, results) if r["records"]])

with board_tab:
    conn = positions()
    all_rows = boardstore.frame(conn)
    top = st.columns([3, 1, 1], vertical_alignment="bottom")
    top[0].write(f"**{len(all_rows)}** vessel positions and cargo orders on the board (this session). "
                 "Add emails from the Batch upload or Inbox tabs.")
    if top[1].button("Load demo board", help="Invented tonnage lists and cargo orders that match each other"):
        load_demo_board()
        st.rerun()
    if top[2].button("Clear board", disabled=all_rows.empty):
        boardstore.clear(conn)
        st.rerun()

    if all_rows.empty:
        st.info("The board is empty. Load the demo board, or add emails from the Batch upload or Inbox tabs.")
    else:
        filters = st.columns([1, 2, 1, 1, 1])
        kind = filters[0].selectbox("Show", ["All", "Vessels", "Cargo orders"])
        text = filters[1].text_input("Search", placeholder="vessel, port, cargo…")
        region = filters[2].selectbox("Region", ["Any"] + list(REGIONS))
        min_size = filters[3].number_input("Min DWT / tonnes", 0, 500000, 0, step=1000)
        max_size = filters[4].number_input("Max DWT / tonnes", 0, 500000, 0, step=1000, help="0 = no limit")
        use_dates = st.toggle("Only dates between")
        window = None
        if use_dates:
            window = st.date_input("Open date / laycan between", (date.today(), date.today() + timedelta(days=30)))
        start, end = (window if isinstance(window, tuple) and len(window) == 2 else (None, None))
        rows = boardstore.search(
            conn, category={"Vessels": "TONNAGE", "Cargo orders": "CARGO VC"}.get(kind), text=text.strip(),
            region=None if region == "Any" else region, start=start, end=end,
            min_size=min_size or None, max_size=max_size or None)
        view = rows[list(BOARD_COLUMNS)].rename(columns=BOARD_COLUMNS)
        view["Type"] = view["Type"].map({"TONNAGE": "Vessel", "CARGO VC": "Cargo"}).fillna(view["Type"])
        view = view.dropna(axis=1, how="all")
        for column in view.columns:
            if column in ("DWT", "DWCC"):
                view[column] = [f"{int(v):,}" if pd.notna(v) else "" for v in pd.to_numeric(view[column], errors="coerce")]
            else:
                view[column] = view[column].astype(object).where(view[column].notna(), "")
        st.caption(f"{len(view)} of {len(all_rows)} shown.")
        st.dataframe(view, width="stretch", hide_index=True)
        downloads = st.columns(2)
        downloads[0].download_button("Download board as Excel", data=excel_bytes(view), file_name="positions_board.xlsx",
                                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        downloads[1].download_button("Download board as CSV", data=view.to_csv(index=False).encode("utf-8-sig"),
                                     file_name="positions_board.csv", mime="text/csv")

with match_tab:
    conn = positions()
    vessels = matching.latest_positions(boardstore.records(boardstore.search(conn, category="TONNAGE")))
    cargoes = boardstore.records(boardstore.search(conn, category="CARGO VC"))
    if not vessels or not cargoes:
        st.info("Matching needs both vessels and cargo orders on the positions board. "
                "Try **Load demo board** on the Positions board tab.")
    else:
        st.caption("Each pair scores up to +3 for dates (vessel opens within or just before the laycan), "
                   "+3 for size (cargo fills 70-95% of DWT, or up to 100% of DWCC) and +3 for location "
                   "(open at the load port; +2 same region, +1 neighbouring region, −2 far away). Pairs that "
                   "cannot work (vessel opens after the laycan or over 30 days before it, or cargo too big) "
                   "are left out; reposted vessels use their latest position. Suggestions to check, not fixtures.")
        direction = st.radio("Find", ["Vessels for a cargo", "Cargoes for a vessel"], horizontal=True)
        show_weak = st.toggle("Show weak matches (score 0 or less)")
        if direction == "Vessels for a cargo":
            target = st.selectbox("Cargo order", cargoes, format_func=board_label)
            ranked = matching.rank(target, vessels, target_is_cargo=True, limit=20)
        else:
            target = st.selectbox("Vessel", vessels, format_func=board_label)
            ranked = matching.rank(target, cargoes, target_is_cargo=False, limit=20)
        ranked = [r for r in ranked if show_weak or r[0] > 0]
        if not ranked:
            st.info("No workable matches on the board for this one.")
        else:
            # Verdicts are kept per vessel-cargo pair for this session, so a broker can review
            # several cargoes and download everything at the end.
            verdicts = st.session_state.setdefault("verdicts", {})
            pairs = []
            for rank_number, (score, candidate, reasons) in enumerate(ranked, start=1):
                vessel, cargo = (candidate, target) if direction == "Vessels for a cargo" else (target, candidate)
                pair = f"{vessel['key']}|{cargo['key']}"
                verdict, comment = verdicts.get(pair, ("", ""))
                pairs.append({"pair": pair, "Score": score, "Match": board_label(candidate),
                              "Why": " · ".join(reasons), "Verdict": verdict, "Comment": comment,
                              "_record": (rank_number, vessel, cargo, score, reasons)})
            st.caption("Optional: record a verdict for each suggestion (e.g. with a broker). "
                       "Verdicts stay in this session until you download them.")
            edited = st.data_editor(
                pd.DataFrame([{k: v for k, v in p.items() if k != "_record"} for p in pairs]),
                width="stretch", hide_index=True, key=f"editor-{target['key']}-{direction}",
                disabled=["pair", "Score", "Match", "Why"],
                column_order=["Score", "Match", "Verdict", "Comment", "Why"],
                column_config={
                    "Score": st.column_config.ProgressColumn(min_value=-4, max_value=9, format="%+d", width="small"),
                    "Match": st.column_config.TextColumn(width="medium"),
                    "Why": st.column_config.TextColumn(width="large"),
                    "Verdict": st.column_config.SelectboxColumn(options=["Good fit", "Possible", "Not workable"],
                                                                width="small"),
                    "Comment": st.column_config.TextColumn(width="medium"),
                })
            for pair_info, (_, row) in zip(pairs, edited.iterrows()):
                verdict = row["Verdict"] if isinstance(row["Verdict"], str) else ""
                comment = row["Comment"] if isinstance(row["Comment"], str) else ""
                if verdict or comment:
                    verdicts[pair_info["pair"]] = (verdict, comment)
                    st.session_state.setdefault("verdict_rows", {})[pair_info["pair"]] = pair_info["_record"]
                else:
                    verdicts.pop(pair_info["pair"], None)

        recorded = st.session_state.get("verdicts", {})
        if recorded:
            records_by_pair = st.session_state.get("verdict_rows", {})
            export = pd.DataFrame([{
                "Verdict": verdict, "Comment": comment,
                "Rank": records_by_pair[pair][0], "Score": records_by_pair[pair][3],
                "Cargo order": board_label(records_by_pair[pair][2]), "Vessel": board_label(records_by_pair[pair][1]),
                "System's reasons": " · ".join(records_by_pair[pair][4]),
            } for pair, (verdict, comment) in recorded.items() if pair in records_by_pair])
            counts = export["Verdict"].value_counts()
            st.write(f"**{len(export)} verdict{'s' if len(export) != 1 else ''} recorded:** " + ", ".join(f"{v} {counts.get(v, 0)}" for v in
                                                                         ["Good fit", "Possible", "Not workable"]))
            st.download_button("Download verdicts CSV", data=export.to_csv(index=False).encode("utf-8-sig"),
                               file_name="match_verdicts.csv", mime="text/csv")
