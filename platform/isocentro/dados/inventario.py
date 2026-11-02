"""Inventário dos **imobilizadores** — máscaras, VacLok e afins.

Dois tipos de acessório aparecem na simulação, e eles se controlam de maneiras
diferentes:

**Padrão, compartilhado** — rampa de mama, rampa de tórax, base B, apoio de
joelho, travesseiro. Fica na sala, serve para qualquer paciente e não precisa de
inventário: basta dizer na nota que foi usado.

**Individual, rastreado** — máscara termoplástica e VacLok têm etiqueta, dono e
histórico, e é isso que este módulo guarda. Só a **máscara** conta utilizações:
é ela que se reaproveita, e é do material dela que se quer saber quantas vezes
já passou pelo forno. O VacLok é vinculado ao paciente e devolvido, sem
contador.

O que se quer saber, e que hoje ninguém sabe sem ir olhar a prateleira: qual
imobilizador está com qual paciente, quantas utilizações a máscara já teve, e o
que está livre para a simulação de agora.

O arquivo é um JSON único (mesmo padrão de ``cadastro_sus.json``), com escrita
atômica. **O conteúdo atual é fictício**, semeado na primeira execução para a
tela poder ser usada e provada — o inventário real entra no lugar dele sem
mudança de código, bastando substituir o arquivo.
"""
from __future__ import annotations

import json
import logging
import os
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from typing import Optional
from isocentro import raiz
from isocentro.dados import ambiente

_LOG = logging.getLogger(__name__)


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s or ""))
                   if unicodedata.category(c) != "Mn")

PASTA_ENV = "ISOCENTRO_INVENTARIO_DIR"
ARQUIVO = "inventario_imobilizadores.json"

# Tipos que o serviço usa. O primeiro campo é o que sai impresso na nota.
TIPOS = (
    "Máscara Curta",
    "Máscara Longa",
    "Máscara de Radiocirurgia",
    "VacLok Corpo",
    "VacLok Membro",
    "Molde de Bolus",
)

# Estados possíveis de um item.
DISPONIVEL = "Disponível"
EM_USO = "Em uso"
DESCARTADO = "Descartado"
ESTADOS = (DISPONIVEL, EM_USO, DESCARTADO)

# Quantas utilizações uma máscara acumula antes de a equipe conferir o material.
# Não é limite rígido — é o ponto em que o app deixa de ficar calado. Vale só
# para máscara (ver ``Item.conta_uso``).
LIMITE_USOS = 20


@dataclass
class Item:
    """Um imobilizador etiquetado."""
    codigo: str = ""            # a etiqueta física, é por ela que se acha
    tipo: str = ""
    estado: str = DISPONIVEL
    paciente: str = ""          # de quem está, quando EM_USO
    registro: str = ""
    usos: int = 0
    adquirido_em: str = ""
    observacao: str = ""

    def __post_init__(self):
        # O inventário real vem de outro sistema, e "usos": "3" (string) é o que
        # um export de planilha produz. Sem a coerção, o ``+= 1`` estoura com
        # TypeError no meio do cadastro — depois de a pasta já ter sido gravada.
        try:
            self.usos = int(self.usos)
        except (TypeError, ValueError):
            self.usos = 0

    def disponivel(self) -> bool:
        return self.estado == DISPONIVEL

    def conta_uso(self) -> bool:
        """Só a máscara acumula utilizações — é o material que se reaproveita.

        O VacLok também é vinculado ao paciente, mas contar moldagens dele não
        diz nada sobre o estado do saco, então a coluna fica de fora em vez de
        mostrar um número que ninguém usa.

        Compara SEM acento: o inventário real vem de outro sistema e pode
        exportar "MASCARA LONGA". Exigir o acento desligaria a contagem e o
        aviso de limite em silêncio — contra a promessa de trocar o arquivo sem
        mudar o código.
        """
        return _sem_acento(self.tipo).lower().startswith("mascara")

    def gasto(self) -> bool:
        return self.conta_uso() and self.usos >= LIMITE_USOS

    def rotulo(self) -> str:
        """``"MSK-014 · Máscara Longa · Disponível (3 usos)"``."""
        partes = [self.codigo, self.tipo, self.estado]
        if self.conta_uso() and self.usos:
            partes[-1] += f" ({self.usos} uso{'s' if self.usos > 1 else ''})"
        if self.estado == EM_USO and self.paciente:
            partes.append(self.paciente)
        return "  ·  ".join(p for p in partes if p)


# ── Arquivo ──────────────────────────────────────────────────────────────────

def _app_dir() -> str:
    # A conta por ``__file__`` valia enquanto o módulo morava na raiz do
    # projeto — ver ``isocentro.raiz.pasta_do_app``.
    return str(raiz.pasta_do_app())


def caminho() -> str:
    base = ambiente.ler(PASTA_ENV) or _app_dir()
    return os.path.join(base, ARQUIVO)


def carregar() -> list[Item]:
    """Todos os itens. Sem arquivo, semeia o inventário fictício e devolve ele."""
    p = caminho()
    if not os.path.exists(p):
        itens = _ficticio()
        if not salvar(itens):
            _LOG.warning("Inventário não pôde ser gravado em %s — as mudanças "
                         "não vão persistir", p)
        return itens
    try:
        with open(p, encoding="utf-8") as fh:
            corpo = json.load(fh)
    except (OSError, ValueError):
        _LOG.exception("Inventário ilegível em %s — seguindo com lista vazia", p)
        return []
    return [Item(**{k: v for k, v in i.items() if k in Item.__annotations__})
            for i in (corpo.get("itens") or ())]


def salvar(itens: list[Item]) -> bool:
    """Grava o inventário. Devolve se conseguiu — escrita atômica.

    O retorno importa: com a pasta sem permissão de escrita, a gravação falhava
    calada e o ``carregar`` seguinte ressemeava a lista fictícia. O inventário
    parecia funcionar e nunca guardava nada.
    """
    p = caminho()
    corpo = {"versao": 1, "itens": [asdict(i) for i in itens]}
    try:
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(corpo, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        return True
    except OSError:
        _LOG.exception("Falha ao gravar o inventário em %s", p)
        return False


def disponiveis(tipo: str = "") -> list[Item]:
    """Itens livres, opcionalmente de um tipo só."""
    return [i for i in carregar()
            if i.disponivel() and (not tipo or i.tipo == tipo)]


def por_codigo(codigo: str) -> Optional[Item]:
    alvo = str(codigo or "").strip().upper()
    return next((i for i in carregar() if i.codigo.upper() == alvo), None)


def registrar_uso(codigos: list[str], paciente: str, registro: str = "",
                  quando: Optional[date] = None) -> list[str]:
    """Vincula os itens ao paciente e conta a utilização.

    Devolve os avisos que a tela deve mostrar — item já em uso por outro
    paciente, ou material que passou do limite de moldagens. Vincular mesmo
    assim é deliberado: a prateleira é a verdade, e o app não pode impedir um
    cadastro porque o inventário está atrasado. Ele avisa.
    """
    alvos = {str(c).strip().upper() for c in codigos if str(c).strip()}
    if not alvos:
        return []
    itens = carregar()
    avisos = []
    for i in itens:
        if i.codigo.upper() not in alvos:
            continue
        if i.estado == EM_USO and i.registro and i.registro != registro:
            avisos.append(f"{i.codigo} estava em uso por {i.paciente} — "
                          "confira antes de levar.")
        # Recadastrar o MESMO paciente no mesmo material nao e uma utilizacao
        # nova: a tela remarca de proposito o que ja e dele, e refazer o
        # cadastro do mes e fluxo normal. Contar de novo antecipa o aviso de
        # limite e faria descartar mascara boa.
        ja_e_dele = (i.estado == EM_USO and registro and i.registro == registro)
        i.estado = EM_USO
        i.paciente = paciente
        i.registro = registro
        if i.conta_uso() and not ja_e_dele:
            # Conta ANTES de avaliar: o aviso é sobre a utilização que está
            # acontecendo agora. Avaliando antes, a máscara de 19 usos passava
            # calada e só avisava na vez seguinte — com o material já na sala.
            i.usos += 1
            if i.gasto():
                avisos.append(f"{i.codigo} chega a {i.usos} utilizações "
                              f"(limite {LIMITE_USOS}) — confira o material.")
    salvar(itens)
    return avisos


def liberar(codigos: list[str], descartar: bool = False) -> None:
    """Devolve itens à prateleira ao fim do tratamento.

    ``descartar`` marca o item como fora de uso em vez de disponível — é a saída
    para o material que não volta. Quem decide é a pessoa que está com a peça na
    mão, não o programa.
    """
    alvos = {str(c).strip().upper() for c in codigos if str(c).strip()}
    itens = carregar()
    for i in itens:
        if i.codigo.upper() in alvos:
            i.estado = DESCARTADO if descartar else DISPONIVEL
            i.paciente = ""
            i.registro = ""
    salvar(itens)


def acrescentar(item: Item) -> None:
    itens = carregar()
    itens.append(item)
    salvar(itens)


# ── Inventário fictício ──────────────────────────────────────────────────────

def _ficticio() -> list[Item]:
    """Semente para a tela ter o que mostrar antes do inventário real chegar.

    Cobre os estados que a tela precisa saber desenhar: disponível, em uso,
    material perto do limite e item descartado.
    """
    hoje = date.today().strftime("%d/%m/%Y")
    return [
        Item("MSK-001", "Máscara Curta", DISPONIVEL, adquirido_em=hoje),
        Item("MSK-002", "Máscara Curta", DISPONIVEL, adquirido_em=hoje),
        Item("MSK-010", "Máscara Longa", DISPONIVEL, adquirido_em=hoje),
        Item("MSK-011", "Máscara Longa", EM_USO, paciente="PACIENTE EXEMPLO",
             registro="0000000XXX", usos=1, adquirido_em=hoje),
        Item("MSK-020", "Máscara de Radiocirurgia", DISPONIVEL,
             adquirido_em=hoje),
        Item("MSK-030", "Máscara Longa", DISPONIVEL, usos=19, adquirido_em=hoje,
             observacao="Perto do limite de utilizações"),
        Item("VAC-100", "VacLok Corpo", DISPONIVEL, adquirido_em=hoje),
        Item("VAC-101", "VacLok Corpo", DISPONIVEL, adquirido_em=hoje),
        Item("VAC-200", "VacLok Membro", DISPONIVEL, adquirido_em=hoje),
        Item("VAC-201", "VacLok Membro", DESCARTADO, adquirido_em=hoje,
             observacao="Saco furado, retirado de uso"),
    ]
