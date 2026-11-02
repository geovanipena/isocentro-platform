# Parallel MU Check (web)

Flask app, the first web version of the **independent monitor-unit verification** that later moved into
the ISOCENTRO platform ([`platform/isocentro/dominio/paralelo.py`](../../platform/isocentro/dominio/paralelo.py),
following AAPM TG-219).

- Upload an RT Plan DICOM and review beams, control points and prescription in the browser.
- Recomputes MU per field from consultative beam tables (TMR/Scp) uploaded as `.xlsx`/`.csv`.
- Generates a PDF report of the comparison.

Beam data is machine-specific commissioning data and is **not** included.

```bash
pip install -r requirements.txt
python app.py
```
