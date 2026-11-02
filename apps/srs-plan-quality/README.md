# SRS Plan Quality

Streamlit app that evaluates **stereotactic radiosurgery** plans straight from DICOM (RT Dose,
RT Structure Set, RT Plan) and keeps a history of the department's plans.

- Checks that the three DICOM objects belong to the same patient before computing anything.
- Target and brain metrics: TV, PIV, V12 Gy of brain, D98/D2/D50.
- Conformity and dose-gradient indices: **CI (RTOG)**, **Paddick CI**, **GI**, **HI (RTOG)**,
  **HI (ICRU 83)**, Q, CVI, DGI.
- Interactive DVH (Plotly), case history in CSV and PDF report.

```bash
pip install -r requirements.txt
streamlit run app.py
```

`data/historico.csv` ships with the header only: no plan data is included.
