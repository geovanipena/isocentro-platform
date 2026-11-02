# Radiation Protection Plan Generator

Streamlit app that assembles a radiotherapy department's **radiation protection plan** (PPR) as a PDF
and keeps track of every regulatory deadline behind it.

- Guided form for facility, equipment, sources, dosimetry and personnel sections.
- **Deadlines dashboard**: operating licence, radiometric survey, dosimetric audit, instrument
  calibration certificates, area monitors, occupational health certificates (ASO).
- **LLM-assisted extraction** (Claude API): uploaded PDFs are read with pypdf and the model returns
  structured JSON (e.g. each professional's last and next ASO date), which the user reviews before use.
- PDF generation with ReportLab, merging the attached certificates (pypdf).

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...           # or Streamlit secrets
streamlit run app.py
```
