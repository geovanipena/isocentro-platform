"""O PPR vivo: a estrutura do documento e de que módulo vem cada parte.

O PPR deixou de ser documento montado à mão (decisão de 28/10/2026, spec
Documentação CAP-10): cada módulo guarda as partes do que conhece — dado e
texto — e a Documentação só monta. Este módulo é a planta dessa montagem, sem
interface nenhuma; o porquê de cada dono está em
``docs/planejamento/sistema-global/ppr-vivo-mapa-2026-10-28.md``.

**A planta é a dos PPRs vigentes, não uma idealização.** Os três (CEL mai/2026,
BET jul/2026, DUO jan/2025) saíram do mesmo molde (``ppr-streamlit`` e o
projeto LaTeX dele): corpo com capítulos curtos — muitos são só "Vide anexo
X" — e anexos com as tabelas e os documentos de origem. Duas coisas que só se
viram lendo os três:

- **Rejeitos só existe com fonte radioativa.** A CEL (HDR) tem 23 capítulos e
  anexos até R; a DUO e a BET, 22 e até Q. Número de capítulo e letra de
  anexo são CALCULADOS: fixos, o "Vide anexo K" da DUO apontaria para o
  anexo errado.
- **Os anexos têm ordem própria.** O H (GQ) vem antes do I (monitores),
  embora o capítulo 11 venha antes do 12, e o C (Responsabilidades) não tem
  capítulo.

**Parte sem fachada é "sem dado", nunca vazio de mentira.** Enquanto o
módulo dono não existe, não há de onde ler; a tela diz isso e o botão de
emitir fica apagado. Um PPR emitido com capítulo em branco vai à CNEN dizendo
que a instalação não tem o que tem.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

# Nome do módulo como aparece na doca; a Fundação é o núcleo e não tem bloco.
MODULOS = {
    "fundacao": "Fundação",
    "qualidade": "Garantia da Qualidade",
    "plano": "Plano",
    "seguranca": "Segurança do paciente",
    "documentacao": "Documentação",
}

SEM_DADO = "sem dado"
COM_DADO = "com dado"

# Condição de presença. Só uma existe nos PPRs do serviço.
FONTE_RADIOATIVA = "fonte_radioativa"


@dataclass(frozen=True)
class Parte:
    """A unidade que um módulo guarda: um capítulo, uma subseção ou um anexo.

    ``chave`` é estável e é o que a fachada recebe — o número e a letra mudam
    de clínica para clínica, a chave não.
    """
    chave: str
    titulo: str
    modulo: str
    requer: str = ""

    @property
    def nome_do_modulo(self) -> str:
        return MODULOS[self.modulo]


@dataclass(frozen=True)
class Capitulo(Parte):
    anexo: str = ""                 # chave do anexo do "Vide anexo X"
    subsecoes: tuple = ()           # Partes; a 12.3 é da Segurança


@dataclass(frozen=True)
class Anexo(Parte):
    pass


def _p(chave, titulo, modulo):
    return Parte(chave, titulo, modulo)


# A ordem e os títulos são os do corpo dos três PPRs (``ppr_pdf._corpo``).
CAPITULOS = (
    Capitulo("identificacao", "Identificação da Instalação", "fundacao"),
    Capitulo("objetivo", "Objetivo da Instalação e Descrição das Práticas",
             "documentacao"),
    Capitulo("estrutura", "Estrutura Organizacional", "fundacao",
             anexo="estrutura"),
    Capitulo("ioes", "Descrição dos IOEs", "fundacao", anexo="ioes"),
    # Grupo e subgrupo da NN-6.02: dado de licenciamento da instalação, não o
    # perfil de risco do SEVRRA (o mapa de 28/10 dizia Segurança; a leitura
    # do corpo mostrou o texto).
    Capitulo("classificacao", "Classificação da Instalação", "fundacao"),
    Capitulo("areas", "Classificação e Descrição das Áreas", "documentacao",
             anexo="areas"),
    Capitulo("acesso", "Mecanismos e Sistemas de Controle de Acesso às Áreas "
             "da Instalação", "seguranca"),
    Capitulo("equipamentos", "Descrição dos Equipamentos e Fontes Emissoras "
             "de Radiação Ionizante", "qualidade", anexo="equipamentos"),
    Capitulo("fontes", "Descrição das Fontes de Referência", "qualidade",
             anexo="fontes"),
    Capitulo("instrumentos", "Descrição dos Instrumentos de Dosimetria",
             "qualidade", anexo="instrumentos"),
    Capitulo("monitores", "Descrição dos Monitores de Área", "qualidade",
             anexo="monitores"),
    Capitulo("gq", "Descrição do Programa de Garantia da Qualidade",
             "qualidade", anexo="gq", subsecoes=(
                 _p("gq_planilha", "Planilha de Controle e Resultados",
                    "qualidade"),
                 _p("gq_testes", "Testes Realizados, Periodicidade e "
                    "Tolerâncias", "qualidade"),
                 _p("gq_riscos", "Planejamento de Análise de Riscos",
                    "seguranca"),
             )),
    Capitulo("tps", "Sistemas de Planejamento", "plano", anexo="tps"),
    Capitulo("tecnicas", "Técnicas de Tratamento", "plano", anexo="tecnicas"),
    Capitulo("barreiras", "Cálculo de Barreiras e Estimativa de Dose",
             "documentacao", anexo="barreiras"),
    Capitulo("monitoracao_individual", "Monitoração Individual",
             "documentacao", anexo="monitoracao_individual"),
    Capitulo("monitoracao_areas", "Monitoração de Áreas", "documentacao"),
    Capitulo("rejeitos", "Gerência de Rejeitos Radioativos", "qualidade",
             requer=FONTE_RADIOATIVA, anexo="rejeitos"),
    Capitulo("aso", "Descrição do Controle Médico dos IOEs - ASO",
             "documentacao", anexo="aso"),
    Capitulo("treinamento", "Programa de Treinamento em Proteção Radiológica "
             "para os IOEs", "documentacao", anexo="treinamento"),
    Capitulo("educacao", "Programa de Educação Continuada para os IOEs",
             "documentacao", anexo="educacao"),
    Capitulo("niveis", "Níveis Operacionais e Restrições", "documentacao"),
    Capitulo("emergencia", "Procedimentos de Emergência", "seguranca",
             anexo="emergencia"),
)

# A ordem dos anexos é a de ``ppr_pdf.gerar`` (A…R), que não segue a dos
# capítulos. O H leva o SEVRRA dentro (seção "SEVRRA" da DUO, p. 53): a
# parte é da Segurança, e por isso o anexo da GQ tem uma subparte dela.
ANEXOS = (
    Anexo("estrutura", "Estrutura Organizacional", "fundacao"),
    Anexo("ioes", "Descrição dos IOEs", "fundacao"),
    Anexo("responsabilidades", "Descrição das Responsabilidades", "fundacao"),
    Anexo("areas", "Classificação e Descrição das Áreas da Instalação",
          "documentacao"),
    Anexo("equipamentos", "Descrição dos Equipamentos e Fontes Emissoras de "
          "Radiação Ionizante", "qualidade"),
    Anexo("fontes", "Descrição das Fontes de Referência", "qualidade"),
    Anexo("instrumentos", "Descrição dos Instrumentos de Dosimetria",
          "qualidade"),
    Anexo("gq", "Programa de Garantia da Qualidade", "qualidade"),
    Anexo("monitores", "Descrição dos Monitores de Área", "qualidade"),
    Anexo("rejeitos", "Gerência de Rejeitos Radioativos", "qualidade",
          requer=FONTE_RADIOATIVA),
    Anexo("tps", "Sistemas de Planejamento", "plano"),
    Anexo("tecnicas", "Técnicas de Tratamento", "plano"),
    Anexo("barreiras", "Cálculo de Barreiras e Estimativas de Dose",
          "documentacao"),
    Anexo("monitoracao_individual", "Monitoração Individual", "documentacao"),
    Anexo("aso", "Descrição do Controle Médico dos IOEs - ASO",
          "documentacao"),
    Anexo("treinamento", "Programa de Treinamento em Proteção Radiológica "
          "para os IOEs", "documentacao"),
    Anexo("educacao", "Programa de Educação Continuada para os IOEs",
          "documentacao"),
    Anexo("emergencia", "Procedimentos de Emergência", "seguranca"),
)

SEVRRA = _p("gq_sevrra", "SEVRRA", "seguranca")


def chave_gravada(parte: Parte) -> str:
    """A chave com que o módulo dono guarda a parte (a da semente e do banco).

    Capítulo e anexo dividem a chave (``estrutura`` é o capítulo 3 E o anexo
    A): guardados pela chave pura, o texto de um sobrescreveria o do outro. O
    SEVRRA mora dentro do anexo da GQ, e por isso também leva o prefixo.
    """
    if isinstance(parte, Anexo) or parte == SEVRRA:
        return f"anexo/{parte.chave}"
    return parte.chave


def partes_da_linha(linha_parte: Parte, p: "Planta") -> list:
    """Tudo o que uma linha da tabela junta: corpo, subseções, anexo e SEVRRA.

    É o mesmo conjunto que decide a situação da linha (``situacoes``), para
    que o texto mostrado seja exatamente o que a situação julgou.
    """
    if not isinstance(linha_parte, Capitulo):
        return [linha_parte]
    partes = [linha_parte, *linha_parte.subsecoes]
    if linha_parte.anexo:
        anexo = next((a for _l, a in p.anexos if a.chave == linha_parte.anexo),
                     None)
        if anexo:
            partes.append(anexo)
            if anexo.chave == "gq":
                partes.append(SEVRRA)
    return partes


@dataclass(frozen=True)
class Planta:
    """A estrutura de UM PPR: capítulos numerados e anexos com letra."""
    capitulos: tuple            # ((numero, Capitulo), ...)
    anexos: tuple               # ((letra, Anexo), ...)

    def letra(self, chave_do_anexo: str) -> str:
        return dict((a.chave, l) for l, a in self.anexos).get(chave_do_anexo, "")

    def partes(self) -> list:
        """Toda unidade que algum módulo precisa dar, na ordem do documento."""
        lista = []
        for _n, cap in self.capitulos:
            lista.append(cap)
            lista.extend(cap.subsecoes)
        for _l, anx in self.anexos:
            lista.append(anx)
            if anx.chave == "gq":
                lista.append(SEVRRA)
        return lista


def planta(condicoes: frozenset = frozenset({FONTE_RADIOATIVA})) -> Planta:
    """A planta do PPR de uma clínica, dadas as condições que ela cumpre.

    O padrão inclui o que é condicional: sem a resposta da GQ (inventário,
    R-84), tirar o capítulo de rejeitos seria afirmar que a clínica não tem
    fonte. Com ele presente e "sem dado", a falta aparece.
    """
    presentes = [c for c in CAPITULOS if not c.requer or c.requer in condicoes]
    capitulos = tuple((str(i), c) for i, c in enumerate(presentes, start=1))
    anexos_presentes = [a for a in ANEXOS
                        if not a.requer or a.requer in condicoes]
    anexos = tuple((chr(ord("A") + i), a)
                   for i, a in enumerate(anexos_presentes))
    return Planta(capitulos, anexos)


# A fachada de um módulo responde se ele TEM a parte (pela chave) para a
# clínica. Sem banco central configurado o dicionário é vazio: é o estado
# real, não um atalho.
Fachada = Callable[[str, Parte], bool]


def _tem(clinica: str, parte: Parte, fachadas: Mapping[str, Fachada]) -> bool:
    ler = fachadas.get(parte.modulo)
    return bool(ler and ler(clinica, parte))


def situacoes(clinica: str,
              fachadas: Optional[Mapping[str, Fachada]] = None,
              p: Optional[Planta] = None) -> list:
    """``[(rotulo, parte, situacao)]``: uma linha por capítulo, e uma pelo
    anexo sem capítulo (C).

    Capítulo "com dado" só quando TODAS as partes dele têm — corpo,
    subseções e o anexo (com o SEVRRA, no da GQ). Um capítulo com o corpo
    pronto e o anexo vazio sai no papel com "Vide anexo H" apontando para
    nada.
    """
    fachadas = fachadas or {}
    p = p or planta()
    linhas = []
    com_capitulo = set()
    for numero, cap in p.capitulos:
        if cap.anexo:
            com_capitulo.add(cap.anexo)
        partes = partes_da_linha(cap, p)
        tem = all(_tem(clinica, parte, fachadas) for parte in partes)
        linhas.append((numero, cap, COM_DADO if tem else SEM_DADO))
    for letra, anx in p.anexos:
        if anx.chave not in com_capitulo:
            tem = _tem(clinica, anx, fachadas)
            linhas.append((f"Anexo {letra}", anx, COM_DADO if tem else SEM_DADO))
    return linhas


@dataclass(frozen=True)
class Leitura:
    """O que a aba PPR precisa de uma clínica, lido de uma vez só.

    ``aviso`` não vazio é o motivo de não ter lido (ou de ter lido com
    ressalva) — a tela o mostra, para "sem dado" não parecer "não existe".
    """
    partes: dict
    condicoes: Optional[frozenset]
    fachadas: dict
    aviso: str = ""


_MENCAO = re.compile(r"\{anexo:([a-z_]+)\}")


def resolver_mencoes(texto: str, p: Planta) -> str:
    """``{anexo:gq}`` vira a letra DESTA planta (H na DUO, I na CEL).

    Anexo que a planta não tem fica como ``?``, e não some: a menção
    quebrada tem de aparecer para alguém corrigir o texto.
    """
    return _MENCAO.sub(lambda m: p.letra(m.group(1)) or "?", texto)


def motivo_para_nao_emitir(clinica: str, linhas: list) -> str:
    """Por que o PPR não pode sair agora, ou "" quando pode.

    O PPR é por clínica: com "Todas" não há instalação a descrever.
    """
    if not clinica:
        return "O PPR é emitido por clínica: escolha uma no Início."
    faltam = sum(1 for _r, _p, sit in linhas if sit != COM_DADO)
    if faltam:
        return (f"Faltam {faltam} parte(s) com dado. Cada uma vem do módulo "
                "dono, e nenhuma é preenchida à mão.")
    return ""
