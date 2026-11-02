# PPR Streamlit — Project Guidelines

## Coding Behavior (Karpathy Guidelines)

### 1. Think Before Coding
- State assumptions explicitly before implementing. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so.
- If something is unclear, stop and name what's confusing.

### 2. Simplicity First
- Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No error handling for impossible scenarios.
- Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes
- Touch only what must change. Don't improve adjacent code.
- Don't refactor things that aren't broken.
- Match existing style.
- Remove only imports/variables made unused by YOUR changes.
- Every changed line must trace directly to the user's request.

### 4. Goal-Driven Execution
- Transform tasks into verifiable goals before starting.
- For multi-step tasks, state a brief plan with a verify step for each.
- Strong success criteria: loop independently. Weak criteria: ask first.

## UI & Design (Frontend Design Guidelines)

When building or modifying any UI element in this Streamlit app:

- **Distinctive, not generic** — avoid default Streamlit aesthetics; use custom CSS (`st.markdown(..., unsafe_allow_html=True)`) to produce polished, production-grade visuals.
- **Consistent design system** — Inter font, dark-blue sidebar gradient, card layouts with subtle shadows, and the existing color tokens (`#1E3A5F`, `#22C55E`, `#F59E0B`, `#EF4444`) already in `app.py`.
- **No AI-aesthetic clichés** — no cookie-cutter gradients, no generic hero sections, no lorem ipsum placeholders.
- **Hierarchy through spacing** — use whitespace, dividers, and `sec()` helper for visual grouping instead of heavy borders.
- **Feedback at every action** — loaders (`st.status`), success/warning/error banners, and metric cards keep the user informed.
- **Mobile-aware** — `st.columns` ratios and font sizes should degrade gracefully on narrow viewports.

## Workflow Skills

- **`verify`** — after any UI change, run the app and confirm the feature works before reporting done. Especially important for Streamlit rerun/session-state bugs that only appear at runtime.
- **`security-review`** — before any commit that touches auth, secrets, file upload, or data export: check for exposed `ANTHROPIC_API_KEY`, unsanitized uploads, sensitive data leaking into logs or session state.

## Project Context

- **Stack:** Python / Streamlit, pandas, reportlab, pypdf, anthropic SDK
- **Main file:** `app.py` — single-file Streamlit app
- **PDF generation:** `ppr_pdf_web.py` → `ppr_pdf.py`
- **Deployment:** Streamlit Cloud, branch `main`
- **API secrets:** `ANTHROPIC_API_KEY` in Streamlit Cloud secrets (`st.secrets`)
- **Session state:** project data lives in `st.session_state.dados` (aliased as `d`)
