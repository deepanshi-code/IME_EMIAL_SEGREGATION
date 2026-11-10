import hashlib
import io
import json
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import board as boardstore
import matching
import ui
from classifier import MIN_SCORE, evidence
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
EDITABLE_COLUMNS = {
    "Vessel": "Vessel Name", "DWT": "Vessel Size", "DWCC": "Cargo Capacity", "Open port": "Open Port",
    "Open date": "Open Date", "Load port": "Loading Port", "Discharge port": "Discharge Port", "Cargo": "Cargo",
    "Quantity (t)": "Quantity", "Laycan": "Laycan",
}
CATEGORIES = ["TONNAGE", "CARGO VC", "CARGO TC", "UNKNOWN"]
SHORT_NAMES = {"TONNAGE": "Vessels", "CARGO VC": "Cargo orders", "CARGO TC": "TC enquiries", "UNKNOWN": "Other"}
REPO_URL = "https://github.com/deepanshi-code/IME_EMIAL_SEGREGATION"
CATEGORY_ICONS = {"TONNAGE": ":material/directions_boat:", "CARGO VC": ":material/inventory_2:",
                  "CARGO TC": ":material/schedule:", "UNKNOWN": ":material/mail:"}
SAMPLE_ICONS = {"Vessel position": ":material/directions_boat:", "Cargo order": ":material/inventory_2:",
                "Vessel list": ":material/format_list_bulleted:", "Time charter": ":material/schedule:",
                "Tricky case": ":material/help:", "Normal email": ":material/mail:"}
CONFIDENCE_ICONS = {"High": ":material/check_circle:", "Medium": ":material/radio_button_partial:",
                    "Low": ":material/warning:"}
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


@st.cache_data(show_spinner=False, max_entries=20000)
def analyse(text):
    # Same email text, same result: cached so filters and clicks do not re-process a whole batch.
    return process_email(text)


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


def result_card(result):
    st.html(ui.result_card(result))
    if len(result["records"]) > 1:
        with st.expander(f"Show the {len(result['records'])} records as a table"):
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
    items = [(row["id"], row["email_text"], analyse(row["email_text"]), date.today())
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


st.set_page_config(page_title="Chartering Email Segregation", page_icon=":material/sailing:", layout="wide")

st.html(ui.STYLE)

with st.sidebar:
    st.subheader(":material/sailing: About")
    st.write("Sorts shipbroker emails, pulls out every vessel and cargo, and suggests which vessels fit "
             "which cargoes, so a chartering desk sees positions and orders at a glance.")
    st.markdown(
        f"{CATEGORY_ICONS['TONNAGE']} **Vessel position** – a ship looking for cargo\n\n"
        f"{CATEGORY_ICONS['CARGO VC']} **Voyage cargo order** – a cargo looking for a ship\n\n"
        f"{CATEGORY_ICONS['CARGO TC']} **Time-charter enquiry** – a ship wanted on hire\n\n"
        f"{CATEGORY_ICONS['UNKNOWN']} **Not chartering** – everything else"
    )
    st.subheader(":material/verified: Confidence")
    st.markdown("**High** – clear evidence · **Medium** – probably right · "
                "**Low** – close call, check it yourself")
    st.subheader(":material/query_stats: About the numbers")
    st.caption("The figures at the top come from 30 real broker circulars collected after the rules were "
               "frozen, and 300 ordinary emails. Matches are suggestions to check, not fixtures.")
    st.markdown(f"[:material/code: Code on GitHub]({REPO_URL}) · [:material/description: How it was tested]"
                f"({REPO_URL}/blob/main/docs/EVALUATION.md)")

st.html(ui.hero([("83%", "right type, real emails"), ("96%", "vessels and cargoes counted"),
                 ("1 / 300", "false alarms, normal email")]))

single_tab, batch_tab, inbox_tab, board_tab, match_tab = st.tabs([
    ":material/mail: Single email", ":material/upload_file: Batch upload", ":material/inbox: Inbox",
    ":material/table_chart: Positions board", ":material/join_inner: Matches"])

with single_tab:
    left, right = st.columns([5, 6], gap="large")
    with left:
        st.markdown("**Try a sample**")
        with st.container(horizontal=True):
            for name in SAMPLES:
                st.button(name, on_click=load_sample, args=(name,), width="content", icon=SAMPLE_ICONS[name])
        with st.form("single-email"):
            email_text = st.text_area("Email text", height=260, key="email_text",
                                      placeholder="Paste a chartering email here…")
            submitted = st.form_submit_button("Process email", type="primary", icon=":material/bolt:")
        if submitted or st.session_state.pop("auto_process", False):
            if email_text.strip():
                st.session_state["single_result"] = (email_text, analyse(email_text))
            else:
                st.session_state.pop("single_result", None)
                st.warning("Paste an email or pick a sample first.")

    with right:
        if "single_result" not in st.session_state:
            st.html('<div class="ime-panel"><div class="ime-kicker">Result</div>'
                    '<div class="ime-reason">Pick a sample or paste an email, then press <b>Process email</b>. '
                    'The type, confidence and every vessel or cargo found will appear here, with the evidence '
                    'behind the decision.</div></div>')
        else:
            text, result = st.session_state["single_result"]
            result_card(result)
            winner = result["category"] if result["category"] != "UNKNOWN" else max(result["scores"], key=result["scores"].get)
            st.html(ui.evidence_panel(result["scores"], winner, evidence(text, winner), MIN_SCORE))
            with st.expander("Technical details (JSON)"):
                output = {
                    "Category": result["category"],
                    "Confidence": result["confidence"],
                    "Reason": result["reason"],
                    "Scores": result["scores"],
                    "Extracted Data": {name: value for name, value in result["fields"].items() if value},
                    "Records": [{k: v for k, v in r.items() if v} for r in result["records"]],
                }
                st.json(output)
                st.download_button("Download JSON", data=json.dumps(output, indent=4), file_name="output.json",
                                   icon=":material/download:")

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
        st.info("Upload emails or switch on the demo emails to see results.", icon=":material/upload_file:")
    else:
        sources = [source for source, _ in pairs]
        texts = [text for _, text in pairs]
        results = [analyse(text) for text in texts]
        table = results_table(sources, results)

        counts = table["Category"].value_counts()
        record_count = sum(len(r["records"]) for r in results)
        metrics = st.columns(4)
        metrics[0].metric("Emails", len(table), border=True)
        metrics[1].metric("Chartering emails", int(len(table) - counts.get("UNKNOWN", 0)), border=True)
        metrics[2].metric("Vessels and cargoes", record_count, border=True)
        metrics[3].metric("To review", int(table["Needs Review"].sum()), border=True)
        st.html(ui.distribution({c: int(counts.get(c, 0)) for c in CATEGORIES}, SHORT_NAMES))

        left, middle, right = st.columns([3, 1, 1], vertical_alignment="bottom")
        chosen = left.multiselect("Show", CATEGORIES, default=CATEGORIES, format_func=SHORT_NAMES.get)
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
            st.info("No emails match these filters.", icon=":material/filter_alt_off:")
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
                    result_card(results[index])

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
        results = [analyse(item["text"]) for item in items]
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

    with st.expander("Restore a saved board", icon=":material/restore:"):
        backup_file = st.file_uploader("Board backup (.json, made with Save board)", type=["json"], key="restore")
        if backup_file is not None and st.button("Restore board"):
            try:
                added = boardstore.restore(conn, json.loads(backup_file.getvalue().decode("utf-8")))
                st.session_state["restored"] = added
                st.rerun()
            except (ValueError, UnicodeDecodeError) as error:
                st.error(f"Could not restore {backup_file.name}: {error}")
    if "restored" in st.session_state:
        st.success(f"Restored {st.session_state.pop('restored')} records.", icon=":material/restore:")

    if all_rows.empty:
        st.info("The board is empty. Load the demo board, add emails from the Batch upload or Inbox tabs, "
                "or restore a saved board.", icon=":material/table_chart:")
    else:
        overview = st.columns([1, 1, 1, 3], vertical_alignment="center")
        kinds = all_rows["category"].value_counts()
        overview[0].metric("Vessels", int(kinds.get("TONNAGE", 0)), border=True)
        overview[1].metric("Cargo orders", int(kinds.get("CARGO VC", 0)), border=True)
        region_names = all_rows["region"].fillna("").replace("", "Unknown")
        overview[2].metric("Regions", int(region_names[region_names != "Unknown"].nunique()), border=True)
        by_region = (all_rows.assign(kind=all_rows["category"].map({"TONNAGE": "Vessels", "CARGO VC": "Cargo orders"}),
                                     region=region_names)
                     .dropna(subset=["kind"]).pivot_table(index="region", columns="kind", aggfunc="size", fill_value=0))
        for column in ("Vessels", "Cargo orders"):
            if column not in by_region:
                by_region[column] = 0
        with overview[3]:
            st.bar_chart(by_region[["Vessels", "Cargo orders"]], horizontal=True, height=200,
                         color=["#2B8CC4", "#2E9E6B"], x_label="", y_label="")
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
        hide_reposts = st.toggle("Hide reposts (keep the latest post of each vessel or cargo)",
                                 help="Brokers circulate the same ship or order to many desks. Vessels: same name. "
                                      "Cargoes: same load and discharge port, overlapping quantity and dates.")
        rows = boardstore.search(
            conn, category={"Vessels": "TONNAGE", "Cargo orders": "CARGO VC"}.get(kind), text=text.strip(),
            region=None if region == "Any" else region, start=start, end=end,
            min_size=min_size or None, max_size=max_size or None)
        post_counts, is_latest = boardstore.repost_groups(all_rows)
        if hide_reposts:
            rows = rows[rows["key"].map(is_latest)]
        view = rows[list(BOARD_COLUMNS)].rename(columns=BOARD_COLUMNS)
        view.index = rows["key"]
        view.insert(view.columns.get_loc("From"), "Posts", [post_counts.get(k, 1) for k in rows["key"]])
        view["Type"] = view["Type"].map({"TONNAGE": "Vessel", "CARGO VC": "Cargo"}).fillna(view["Type"])
        editable = [c for c in EDITABLE_COLUMNS if c in view.columns]
        view = view.drop(columns=[c for c in view.columns if c not in editable and view[c].isna().all()])
        for column in view.columns:
            if column in ("DWT", "DWCC"):
                view[column] = [f"{int(v):,}" if pd.notna(v) else "" for v in pd.to_numeric(view[column], errors="coerce")]
            elif column != "Posts":
                view[column] = view[column].astype(object).where(view[column].notna(), "").astype(str)
        st.caption(f"{len(view)} of {len(all_rows)} shown. **Click a cell to correct a wrong value**: dates, region "
                   "and matches update, and every correction is kept so it can be used as labelled test data.")
        signature = hashlib.sha1(view.to_json().encode("utf-8")).hexdigest()[:12]
        edited = st.data_editor(
            view, width="stretch", hide_index=True, key=f"board-editor-{signature}",
            disabled=[c for c in view.columns if c not in editable],
            column_config={"Posts": st.column_config.NumberColumn(
                help="How many records on the board look like the same vessel or cargo (reposts)", width="small")})
        changed = []
        for key, row in edited.iterrows():
            for column in editable:
                new, old = str(row[column] if pd.notna(row[column]) else "").strip(), view.at[key, column]
                if new != old:
                    changed.append((key, column, old, new))
        if changed:
            try:
                originals = rows.set_index("key")
                for key, column, old, new in changed:
                    field = EDITABLE_COLUMNS[column]
                    boardstore.update(conn, key, {boardstore.FIELD_COLUMNS[field]: new})
                    log = st.session_state.setdefault("corrections", {})
                    entry = log.setdefault((key, field), {
                        "source": originals.at[key, "source"], "category": originals.at[key, "category"],
                        "record_key": key, "field": field, "extracted": old, "text": originals.at[key, "text"]})
                    entry["corrected"] = new
                st.rerun()
            except ValueError as error:
                st.error(f"Not saved: {error}")
        corrections = [c for c in st.session_state.get("corrections", {}).values() if c["corrected"] != c["extracted"]]
        if corrections:
            st.success(f"{len(corrections)} correction{'s' if len(corrections) != 1 else ''} made in this session.",
                       icon=":material/edit_note:")
        downloads = st.columns(4)
        downloads[2].download_button(
            f"Download corrections ({len(corrections)})", disabled=not corrections, icon=":material/edit_note:",
            data=json.dumps(corrections, indent=2, ensure_ascii=False), file_name="corrections.json",
            mime="application/json", help="Each correction with the email text: labelled data for testing the rules")
        downloads[3].download_button(
            "Save board (backup)", icon=":material/save:", data=json.dumps(boardstore.backup(conn), ensure_ascii=False),
            file_name="positions_board_backup.json", mime="application/json",
            help="The board lives only in this browser session. Save it to your computer and restore it later.")
        downloads[0].download_button("Download board as Excel", data=excel_bytes(view), file_name="positions_board.xlsx",
                                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        downloads[1].download_button("Download board as CSV", data=view.to_csv(index=False).encode("utf-8-sig"),
                                     file_name="positions_board.csv", mime="text/csv")

with match_tab:
    conn = positions()
    vessels = matching.latest_positions(boardstore.records(boardstore.search(conn, category="TONNAGE")))
    _, is_latest = boardstore.repost_groups(boardstore.frame(conn))
    cargoes = [c for c in boardstore.records(boardstore.search(conn, category="CARGO VC")) if is_latest.get(c["key"], True)]
    if not vessels or not cargoes:
        st.info("Matching needs both vessels and cargo orders on the positions board. "
                "Try **Load demo board** on the Positions board tab.", icon=":material/join_inner:")
    else:
        with st.expander("How matches are scored", icon=":material/info:"):
            st.markdown("Each pair scores up to **+3 for dates** (vessel opens within or just before the laycan), "
                        "**+3 for size** (cargo fills 70-95% of DWT, or up to 100% of DWCC) and **+3 for location** "
                        "(open at the load port; +2 same region, +1 neighbouring region, −2 far away). Pairs that "
                        "cannot work (vessel opens after the laycan or over 30 days before it, or cargo too big) "
                        "are left out; reposted vessels and cargoes use their latest post. These are suggestions to "
                        "check, not fixtures.")
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
            st.info("No workable matches on the board for this one.", icon=":material/search_off:")
        else:
            st.markdown(f"**Best {min(3, len(ranked))} of {len(ranked)} suggestions**")
            for rank_number, (score, candidate, reasons) in enumerate(ranked[:3], start=1):
                vessel, cargo = (candidate, target) if direction == "Vessels for a cargo" else (target, candidate)
                parts = [(name, check(vessel, cargo)[0] or 0) for name, check in
                         (("Dates", matching.date_fit), ("Size", matching.size_fit), ("Location", matching.place_fit))]
                if (matching.type_fit(vessel, cargo)[0] or 0) < 0:
                    parts.append(("Type", matching.type_fit(vessel, cargo)[0]))
                st.html(ui.match_card(rank_number, score, board_label(candidate), parts, reasons))
            st.markdown("**All suggestions** · record a verdict for each one (e.g. with a broker)")
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
            st.caption("Verdicts stay in this session until you download them.")
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
