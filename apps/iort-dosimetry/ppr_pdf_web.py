"""
ppr_pdf_web.py – Adaptador do gerador de PDF para uso no Streamlit.

• Recebe o dict `dados` do session_state (com _pdfs_bytes e _logo_bytes).
• Escreve em BytesIO e retorna bytes — sem salvar em disco.
• PDFs uploadados são gravados em arquivos temporários durante a geração.
"""

import io, base64, tempfile, os, shutil
from copy import deepcopy

# Importa o gerador original — deve estar na mesma pasta
from ppr_pdf import gerar_pdf as _gerar_pdf_original


def gerar_pdf_bytes(dados: dict) -> bytes:
    """
    Gera o PPR em memória e retorna bytes do PDF.

    Parâmetros
    ----------
    dados : dict
        Estrutura completa dos dados do PPR (session_state.dados).
        Inclui opcionalmente:
          - _pdfs_bytes : {key: {"nome": str, "data": base64str, "chave_secao": str}}
          - _logo_bytes : base64str da imagem do logo
    """
    dados_work = deepcopy(dados)

    # Cria diretório temporário para gravar PDFs e imagens uploadados
    tmpdir = tempfile.mkdtemp(prefix="ppr_web_")

    try:
        pdfs_bytes_map: dict = dados_work.pop("_pdfs_bytes", {}) or {}
        logo_bytes_b64: str  = dados_work.pop("_logo_bytes", None)

        # ── Grava PDFs temporários e mapeia caminhos reais ─────────────────────
        # Estrutura: {chave_secao: [caminho_arquivo, ...]}
        caminhos_por_secao: dict = {}
        for k, info in pdfs_bytes_map.items():
            secao = info.get("chave_secao", "")
            nome  = info.get("nome", f"{k}.pdf")
            b64   = info.get("data", "")
            if not b64:
                continue
            try:
                conteudo = base64.b64decode(b64)
                caminho  = os.path.join(tmpdir, f"{secao}__{nome}")
                with open(caminho, "wb") as f:
                    f.write(conteudo)
                caminhos_por_secao.setdefault(secao, []).append(caminho)
            except Exception:
                pass

        # Popula dados["pdfs"] com os caminhos reais (substituindo listas vazias)
        if "pdfs" not in dados_work:
            dados_work["pdfs"] = {}
        for secao, caminhos in caminhos_por_secao.items():
            dados_work["pdfs"][secao] = caminhos

        # ── Logo ───────────────────────────────────────────────────────────────
        if logo_bytes_b64:
            try:
                logo_bytes = base64.b64decode(logo_bytes_b64)
                logo_path  = os.path.join(tmpdir, "logo.png")
                with open(logo_path, "wb") as f:
                    f.write(logo_bytes)
                dados_work["imagens"]["logo"] = logo_path
            except Exception:
                pass

        # ── Gera PDF para BytesIO ──────────────────────────────────────────────
        buf = io.BytesIO()

        # O ppr_pdf original aceita caminho de string.
        # Usamos um arquivo temporário de saída e depois lemos.
        caminho_saida = os.path.join(tmpdir, "PPR_output.pdf")
        _gerar_pdf_original(dados_work, caminho_saida)

        with open(caminho_saida, "rb") as f:
            pdf_bytes = f.read()

        return pdf_bytes

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
