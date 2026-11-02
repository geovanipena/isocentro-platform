"""Diferenças entre versões do registro do paciente, para a tela de Histórico.

Funções puras (sem Qt): comparam os blocos ``dados``/``plano_rp``/``render`` de
versões consecutivas e produzem um HTML legível. Ficavam no gui.py; movidas para
cá para enxugar o módulo da UI e facilitar o teste isolado.
"""
from __future__ import annotations

import html


AUSENTE = object()   # sentinela: campo inexistente em uma das versões

# Rótulos amigáveis dos campos comparados (chave achatada → rótulo). Campos fora
# do mapa aparecem com o próprio nome (ex.: caminho aninhado do plano).
ROTULOS = {
    "pac_nome": "Nome", "pac_registro": "Registro", "pac_nascimento": "Nascimento",
    "rx_dose_total": "Dose total", "rx_dose_fracao": "Dose/fração",
    "rx_fracoes": "Nº frações", "fracionamento": "Fracionamento",
    "proto_imagem": "Imagem", "proto_frequencia": "Frequência",
    "proto_imagem_dias": "Dias de imagem",
    "gating": "Gating", "gating_modalidade": "Modalidade", "gating_fase": "Janela",
    "observacoes": "Observações",
    "eq_medico": "Médico", "eq_fisico": "Físico", "maquina": "Máquina",
    "idx_axial": "Corte axial", "idx_sagital": "Corte sagital",
    "idx_coronal": "Corte coronal", "mostrar_isodose": "Isodose",
    "isodose_range": "Faixa de isodose", "mostrar_estruturas": "Estruturas",
    "estruturas_dvh": "Estruturas do DVH", "estruturas_visiveis": "Estruturas visíveis",
}

BLOCOS = [("Dados da ficha", "dados"),
          ("Plano (RT Plan)", "plano_rp"),
          ("Visualização", "render")]


def achatar(obj, prefixo: str = "") -> dict:
    """Achata dict/list aninhados em ``chave.pontilhada -> valor`` folha.

    Listas de escalares são mantidas inteiras (comparadas como um todo), para
    não gerar ruído tipo ``faixa[0]``/``faixa[1]``.
    """
    saida: dict = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            chave = f"{prefixo}.{k}" if prefixo else str(k)
            saida.update(achatar(v, chave))
    elif isinstance(obj, list) and any(isinstance(x, (dict, list)) for x in obj):
        for i, v in enumerate(obj):
            saida.update(achatar(v, f"{prefixo}[{i}]"))
    else:
        saida[prefixo] = obj
    return saida


def rotulo(chave: str) -> str:
    base = chave.split(".")[-1].split("[")[0]
    return ROTULOS.get(base, chave)


def formatar(valor) -> str:
    if valor is AUSENTE or valor is None or valor == "":
        return "—"
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, list):
        return ", ".join(str(x) for x in valor) if valor else "—"
    return str(valor)


def diff_bloco(a: dict, b: dict) -> list[tuple]:
    """Campos que mudaram entre dois blocos: ``[(rótulo, antigo, novo)]``."""
    fa, fb = achatar(a or {}), achatar(b or {})
    mudancas = []
    for chave in sorted(set(fa) | set(fb)):
        va, vb = fa.get(chave, AUSENTE), fb.get(chave, AUSENTE)
        if va != vb:
            mudancas.append((rotulo(chave), va, vb))
    return mudancas


def html_diff(versoes: list) -> str:
    """HTML com as diferenças entre versões consecutivas (v1→v2, v2→v3, …)."""
    partes = ["<style>"
              "h3{color:#58c1dc;margin:14px 0 4px;} "
              "b.bloco{color:#e0a96b;} "
              "table{margin:2px 0 8px 12px;border-collapse:collapse;} "
              "td{padding:1px 10px 1px 0;vertical-align:top;} "
              ".antigo{color:#e0776b;} .novo{color:#7ec97e;} .campo{color:#cfd8dc;}"
              "</style>"]
    for ant, novo in zip(versoes, versoes[1:]):
        va, vn = ant.get("versao"), novo.get("versao")
        da, dn = ant.get("data", ""), novo.get("data", "")
        partes.append(f"<h3>v{va} → v{vn}"
                      + (f" &nbsp;({da} → {dn})" if da or dn else "") + "</h3>")
        houve = False
        for titulo, chave in BLOCOS:
            mudancas = diff_bloco(ant.get(chave, {}), novo.get(chave, {}))
            if not mudancas:
                continue
            houve = True
            partes.append(f'<b class="bloco">{html.escape(titulo)}</b><table>')
            for rot, antigo, atual in mudancas:
                partes.append(
                    f'<tr><td class="campo">{html.escape(rot)}</td>'
                    f'<td class="antigo">{html.escape(formatar(antigo))}</td>'
                    f'<td>→</td>'
                    f'<td class="novo">{html.escape(formatar(atual))}</td></tr>')
            partes.append("</table>")
        if not houve:
            partes.append("<i>(sem diferenças de conteúdo detectadas)</i>")
    return "".join(partes)
