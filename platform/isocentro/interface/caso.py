"""O paciente carregado: tudo o que a troca de paciente tem de esquecer.

Nasceu em 16/09/2026 (R-06, corte 6a do ``docs/PROPOSTA_GUI.md``). Estes 25
campos moravam soltos na ``JanelaPrincipal`` e eram zerados UM A UM, à mão, no
``_executar_limpeza`` — a lista existia em dois lugares (``__init__`` e
limpeza), e atributo novo do caso que entrasse só no primeiro sobrevivia à
troca de paciente. É a forma do defeito que chega ao papel: a ficha de B com um
resto de A.

Agora a limpeza é ``janela.caso = Caso()``. Campo novo entra AQUI, e a troca de
paciente o esquece sem ninguém precisar lembrar.

Provado pelo formato: ``_drrs_png_caso`` e ``_drrs_titulos_caso`` não estavam
no ``__init__`` — só nasciam na primeira limpeza, e quem os lia precisava de
``getattr`` com padrão.

**Quem lê, lê na hora** (``janela.caso.planos``), nunca guarda o ``Caso``: a
limpeza troca o OBJETO, e uma referência guardada responderia pelo paciente
anterior — o mesmo motivo de o ``PortaoDaFicha`` e o ``ControleCapa`` lerem a
janela em vez de copiar dela.

Não tem Qt de propósito, mas mora em ``interface/`` e não em ``dominio/``
(decisão do usuário, 16/09): guarda também o que é da TELA — cache de render
3D, PNGs, perguntas que a carga deixou para o fim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


def _sus_vazio() -> dict:
    return {"pac_sus": False, "numero_sus": ""}


@dataclass
class Caso:
    # ── O que veio do TPS ──────────────────────────────────────────────────
    ct: object = None              # ct_series.CTSerie
    rs: object = None
    rd: object = None
    # ``dados["RP"]``, ``rs`` e ``rd`` apontam para o plano ATIVO.
    dados: dict = field(default_factory=dict)
    # Múltiplos planos (até 5).
    planos: list = field(default_factory=list)
    plano_ativo: int = 0

    # ── Visualização SOMA ──────────────────────────────────────────────────
    # Ficha soma/personalizado: dose combinada + estruturas unificadas no
    # viewer, em vez do plano ativo. Vale só quando o plano ATIVO faz parte da
    # combinação (``indices_soma``) — um plano de fora, ex. em outra TC, mostra
    # a sua própria dose.
    modo_soma: bool = False
    dose_soma: object = None       # tupla de ct_series.tupla_dose (dose combinada)
    rs_soma: object = None         # RS usada para estruturas/3D na visão soma
    indices_soma: set = field(default_factory=set)  # planos na dose combinada

    # ── 3D e estruturas ───────────────────────────────────────────────────
    png_3d: Optional[bytes] = None
    # RS que ``png_3d`` REALMENTE representa (gravada no FIM do render, ao
    # contrário de ``rs_3d``, que muda no início do render assíncrono).
    png_3d_rs: object = None
    rs_3d: object = None           # RS a que o 3D exibido corresponde
    # Renders 3D já feitos, por (corpo, ângulo) → PNG. O render custa ~15 s e
    # não depende da aba: sem este cache, sair da aba antes de ele terminar
    # jogava fora o resultado e a volta recomeçava do zero. É do CASO: outro
    # paciente, outro corpo.
    cache_3d: dict = field(default_factory=dict)
    rs_estruturas: object = None   # RS a que a lista de estruturas corresponde
    drrs_png: list = field(default_factory=list)      # DRRs de setup do caso
    drrs_titulos: list = field(default_factory=list)  # títulos (nomes dos portais)

    # ── De onde o caso veio ────────────────────────────────────────────────
    pasta_carregada: Optional[str] = None
    # Caso aberto da pasta TEMPORÁRIA pelo ``● PRONTA`` da Fichinha: a
    # instância da Documentação e a pasta do curso. Com ela, a Impressão é a
    # LIBERAÇÃO — grava na pasta do paciente, não na carregada.
    origem_temporaria: Optional[dict] = None
    # Contexto de um tratamento aberto do JSON (sem DICOM): caminhos dos PNGs
    # de cortes/DVH salvos, para reusar na página 1 ao regerar.
    registro_carregado: Optional[dict] = None
    # Pasta temporária onde o zip do paciente reaberto foi extraído (os
    # imagens_paths/dvhs_paths apontam pra lá). A janela a APAGA antes de
    # trocar o caso — ver ``_executar_limpeza``.
    tmp_extraido: Optional[str] = None

    # ── O que a ficha decide sobre ele ─────────────────────────────────────
    # SUS (pré-preenche o popup): lembrado da última geração/reabertura, pois
    # pac_sus/numero_sus não são campos do formulário.
    sus: dict = field(default_factory=_sus_vazio)
    # Agendamento do tratamento multi-plano (config + sequência de frações).
    agendamento: Optional[dict] = None
    # A carga em curso trouxe ≥2 planos e o agendamento ainda tem de abrir?
    # Marcado em ``_plano_carregado``, consumido no FIM da carga — ver
    # ``_abrir_agendamento_pendente`` para o porquê da espera.
    agendamento_pendente: bool = False
    # As perguntas e avisos que a carga deixou para o FIM dela. Mesma razão do
    # agendamento: quem monta os planos é o slot de ``plano_pronto``, e de lá
    # nenhum modal pode subir — ver ``_perguntar_o_que_a_carga_deixou``.
    perguntas_pendentes: set = field(default_factory=set)
