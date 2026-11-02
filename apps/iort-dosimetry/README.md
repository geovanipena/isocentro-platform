# IORT Dosimetry (ZEISS INTRABEAM)

Streamlit app supporting **intra-operative radiotherapy** of the breast with the ZEISS INTRABEAM
system: a case database for the clinical research cohort and a **computer-vision** reader for the
treatment report.

**Lesion-quadrant classifier** ([`iort_quadrant.py`](iort_quadrant.py)): reads page 2 of the INTRABEAM
treatment report and, from the "Application Type" diagram, detects

- the crossing of the red lines → lesion position;
- the concentric black circles → nipple (inner) and areola (outer);
- the yellow grid → calibration of the Cartesian plane (0–10);

then applies the team's rule: inside the areola → *areolar/periareolar*; on the nipple axes (± tolerance)
→ *junction of quadrants*; otherwise UOQ / UIQ / LOQ / LIQ, with lateral/medial resolved by laterality.
OpenCV and pdf2image are imported lazily, so the rest of the app starts fast.

```bash
pip install -r requirements.txt        # pdf2image needs poppler (see packages.txt)
streamlit run app.py
```
