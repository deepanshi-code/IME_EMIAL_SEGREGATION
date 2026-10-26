import json

import streamlit as st

from pipeline import (
    TEXT_COLUMN_HINTS, decode_text, guess_column, parse_eml, process_email, read_csv, results_table,
)

CATEGORIES = ["TONNAGE", "CARGO VC", "CARGO TC", "UNKNOWN"]

st.set_page_config(page_title="Email Segregation", layout="wide")
st.title("IME Innovation Challenge – Email Segregation")
st.caption(
    "Sorts chartering emails into TONNAGE, CARGO VC, CARGO TC or UNKNOWN and extracts key fields. "
    "Confidence is Low when the top two category scores are within 1 point or the score is at the threshold."
)

single_tab, batch_tab = st.tabs(["Single email", "Batch upload"])

with single_tab:
    with st.form("single-email"):
        email_text = st.text_area("Paste Email Content", height=300)
        submitted = st.form_submit_button("Process Email")

    if submitted:
        if email_text.strip():
            result = process_email(email_text)
            found = {name: value for name, value in result["fields"].items() if value}
            output = {
                "Category": result["category"],
                "Confidence": result["confidence"],
                "Scores": result["scores"],
                "Extracted Data": found,
            }

            message = f"Detected Category: {result['category']} (confidence: {result['confidence']})"
            if result["needs_review"]:
                st.warning(message + " – needs manual review")
            else:
                st.success(message)
            st.json(output)

            st.download_button(
                "Download JSON",
                data=json.dumps(output, indent=4),
                file_name="output.json",
            )
        else:
            st.warning("Paste email text first.")

with batch_tab:
    uploads = st.file_uploader(
        "Upload .txt or .eml files (one email each), or a .csv with one email per row",
        type=["txt", "eml", "csv"],
        accept_multiple_files=True,
    )

    sources, texts = [], []
    for upload in uploads or []:
        raw = upload.getvalue()
        name = upload.name.lower()
        if name.endswith(".eml"):
            sources.append(upload.name)
            texts.append(parse_eml(raw))
        elif name.endswith(".txt"):
            sources.append(upload.name)
            texts.append(decode_text(raw))
        else:
            try:
                frame = read_csv(raw)
            except Exception as error:
                st.error(f"Could not read {upload.name}: {error}")
                continue
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
            subject_guess = guess_column(columns, ["subject"]) if any("subject" in c.lower() for c in columns) else "(none)"
            subject_column = right.selectbox(
                f"Subject column in {upload.name} (optional)", subject_options,
                index=subject_options.index(subject_guess),
                key=f"subject-{upload.name}",
            )
            for i, row in frame.iterrows():
                text = row[text_column]
                if subject_column != "(none)":
                    text = f"Subject: {row[subject_column]}\n\n{text}"
                sources.append(f"{upload.name} row {i + 2}")
                texts.append(text)

    pairs = [(source, text) for source, text in zip(sources, texts) if text and text.strip()]
    if uploads and not pairs:
        st.info("No email text found in the uploaded files.")

    if pairs:
        sources = [source for source, _ in pairs]
        texts = [text for _, text in pairs]
        table = results_table(sources, [process_email(text) for text in texts])

        counts = table["Category"].value_counts()
        metrics = st.columns(len(CATEGORIES) + 2)
        metrics[0].metric("Emails", len(table))
        for column, category in zip(metrics[1:], CATEGORIES):
            column.metric(category, int(counts.get(category, 0)))
        metrics[-1].metric("Needs review", int(table["Needs Review"].sum()))

        left, right = st.columns(2)
        chosen = left.multiselect("Show categories", CATEGORIES, default=CATEGORIES)
        review_only = right.checkbox("Only emails that need review")
        view = table[table["Category"].isin(chosen)]
        if review_only:
            view = view[view["Needs Review"]]
        view = view.dropna(axis=1, how="all").fillna("")

        if view.empty:
            st.info("No emails match these filters.")
        else:
            st.dataframe(view, use_container_width=True, hide_index=True)

        with st.expander("Read an email from this batch"):
            picked = st.selectbox("Email", sources)
            st.text(texts[sources.index(picked)])

        st.download_button(
            "Download results CSV",
            data=table.to_csv(index=False).encode("utf-8-sig"),
            file_name="email_segregation_results.csv",
            mime="text/csv",
        )
