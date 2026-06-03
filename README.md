# IME – Shipping Email Segregation & Data Extraction System

A lightweight email intelligence platform developed for the **IME Innovation Challenge under TBI-GEU**.

The project automates shipping email processing by identifying email categories and extracting structured business information from unstructured email text.

The system converts raw shipping communication into machine-readable JSON output using local Python processing.

No external LLM APIs are used.

---

# Problem Statement

Shipping and chartering companies receive a large number of operational emails every day.

These emails contain information related to:

* Vessel availability
* Voyage charter cargo requests
* Time charter requirements

Manual processing requires reading each email individually and extracting details manually.

This project automates that workflow.

---

# Solution Overview

The system performs four core operations:

1. Receive shipping email content
2. Identify email category
3. Extract business information
4. Generate structured JSON output

---

# Project Structure

```plaintext
IME_EMAIL_SEGREGATION/

├── app.py
│
│   Main Streamlit application
│
│   Responsibilities:
│   • Receive email input
│   • Trigger processing
│   • Display extracted results
│   • Generate downloadable JSON
│
│
├── classifier.py
│
│   Email classification engine
│
│   Responsibilities:
│   • Read shipping email
│   • Detect email category
│
│   Categories:
│   → TONNAGE
│   → CARGO VC
│   → CARGO TC
│
│
├── extractor.py
│
│   Information extraction module
│
│   Responsibilities:
│   • Extract required fields
│   • Apply regex matching
│   • Generate structured output
│
│
├── requirements.txt
│
│   Project dependencies
│
│   Libraries:
│   • Streamlit
│   • Pandas
│   • Regex
│
│
└── README.md

    Project documentation
```

---

# System Workflow

```plaintext
Shipping Email
      ↓
Category Classification
      ↓
Information Extraction
      ↓
JSON Generation
      ↓
Output Display
```

---

# Supported Categories

## 1. TONNAGE

Purpose:

Identify vessel availability emails.

Typical Signals:

```plaintext
MV
OPEN
VESSEL
DWT
```

Extracted Fields:

* Vessel Name
* Open Port
* Vessel Size

Example:

Input:

```plaintext
MV SHENG AN HAI
OPEN XIAMEN
DWT 56564
```

Output:

```json
{
"Category":"TONNAGE",
"Extracted Data":{
"Vessel Name":"SHENG AN HAI",
"Open Port":"XIAMEN",
"Vessel Size":"56564"
}
}
```

---

## 2. CARGO VC

Purpose:

Identify voyage charter cargo requests.

Typical Signals:

```plaintext
LOAD PORT
DISCHARGE PORT
POL
POD
LAYCAN
```

Extracted Fields:

* Loading Port
* Discharge Port

Example:

```plaintext
LOAD PORT: THAILAND
DISCHARGE PORT: KANDLA
```

---

## 3. CARGO TC

Purpose:

Identify time charter cargo requests.

Typical Signals:

```plaintext
DELIVERY
REDELIVERY
DURATION
TCT
```

Extracted Fields:

* Delivery Port
* Redelivery Port
* Duration

Example:

```plaintext
DELIVERY VANCOUVER
REDELIVERY CHITTAGONG
DURATION 30 DAYS
```

---

# Technology Stack

Backend

* Python

Frontend

* Streamlit

Processing

* Regex
* Rule-Based Classification

Output

* JSON

---

# Installation

Clone repository:

```bash
git clone <repository-url>
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run application:

```bash
python -m streamlit run app.py
```

Application opens locally in browser.

---

# Features

✔ Automatic email categorization
✔ Structured data extraction
✔ JSON output generation
✔ Lightweight implementation
✔ Local processing

---

# Future Scope

* PDF and attachment processing
* Database integration
* Duplicate detection
* Cargo–vessel matching
* Dashboard analytics
* Advanced NLP pipeline

---

# Conclusion

This project demonstrates a practical approach to converting unstructured shipping communication into structured business information through automated email segregation and extraction.

The system reduces manual effort and provides a foundation for future intelligent shipping workflows.

---

# Author

Deepanshi Agarwal
B.Tech CSE (AI & ML)
Graphic Era Deemed University
