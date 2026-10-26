import json
import os

import streamlit as st

from pipeline import (
    CATEGORY_NAMES, FIELD_NAMES, TEXT_COLUMN_HINTS, decode_text, guess_column, parse_eml, process_email,
    read_csv, results_table,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_CSV = os.path.join(APP_DIR, "samples", "demo_emails.csv")
CATEGORIES = ["TONNAGE", "CARGO VC", "CARGO TC", "UNKNOWN"]
SHORT_NAMES = {"TONNAGE": "Vessels", "CARGO VC": "Cargo orders", "CARGO TC": "TC enquiries", "UNKNOWN": "Other"}
CATEGORY_COLORS = {"TONNAGE": "blue", "CARGO VC": "green", "CARGO TC": "violet", "UNKNOWN": "gray"}
CONFIDENCE_COLORS = {"High": "green", "Medium": "orange", "Low": "red"}
SAMPLES = {
    "Vessel position": "MV SEA HAWK 58,000 DWT\nOPEN TIANJIN 10-12 DEC\nGEARED 4X30T\nPLS OFFER SUITABLE CARGO",
    "Cargo order": "Pls offer firm for;\nMundra / Chittagong\n12,000 mt bagged sugar\n5-10 Dec\n2000x / 1500x\n2.5% ttl",
    "Time charter": "Period enquiry\nDel: Haldia\nRedel: Far East\nPeriod: 11-13 months\nKamsarmax required",
    "Tricky case": (
        "Hi John, we have a vessel available for a crude oil shipment from Houston to Rotterdam. "
        "The vessel is the MV Ocean Star, 150,000 DWT. The laycan is 15-20 October. Freight USD 20/MT."
    ),
    "Normal email": "Hi Sarah,\n\nCould we move the budget review to Thursday afternoon?\n\nThanks,\nDaniel",
}


def format_value(name, value):
    return f"{int(value):,} DWT" if name == "Vessel Size" else value


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
        "On 42 real broker circulars not used during development: **95%** sorted correctly, "
        "**75%** of details extracted correctly. On 300 normal emails, 1 was wrongly flagged.\n\n"
        "Rule-based, so every decision can be explained. Details only come from the first "
        "vessel or cargo in an email."
    )

st.title("Chartering Email Segregation")
st.caption("IME Innovation Challenge – sort broker emails and extract vessel and cargo details.")

single_tab, batch_tab = st.tabs(["Single email", "Batch upload"])

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
            view = view[["Source", "Category", "Confidence", "Needs Review", "Key Details", "Why"]]
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

        st.download_button(
            "Download results CSV",
            data=table.to_csv(index=False).encode("utf-8-sig"),
            file_name="email_segregation_results.csv",
            mime="text/csv",
        )
