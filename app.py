import streamlit as st
import json
from classifier import classify_email
from extractor import extract_data

st.title("IME Innovation Challenge – Email Segregation")

email = st.text_area("Paste Email Content", height=300)

if st.button("Process Email"):
    if email.strip():
        category = classify_email(email)
        data = extract_data(email, category)

        output = {
            "Category": category,
            "Extracted Data": data
        }

        st.success(f"Detected Category: {category}")
        st.json(output)

        st.download_button(
            "Download JSON",
            data=json.dumps(output, indent=4),
            file_name="output.json"
        )
    else:
        st.warning("Paste email text first.")
