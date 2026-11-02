"""Geração do PDF da **Capa de Tratamento** (Ficha de Tratamento, modelo Clinica).

Duas páginas A4 retrato, medidas do relatório institucional da clínica:

* Página 1 — identificação, curso/intenção/CID, as prescrições aprovadas,
  alertas de enfermagem e as assinaturas do primeiro dia.
* Página 2 — fotos de posicionamento, acessórios, preparo (bexiga/reto/braços)
  e a devolução de exames.

As coordenadas são as do modelo, em pontos, com **origem no canto superior
esquerdo** — é assim que se lê um formulário, e foi assim que elas foram
extraídas do PDF de referência. Os helpers convertem para o sistema do
ReportLab. Números soltos no código são posições medidas, não escolhas: mexer
neles desalinha a capa em relação à que a clínica já usa.
"""
from __future__ import annotations

import contextlib
import io
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from isocentro import raiz
from isocentro.banco import capa_dados
from isocentro.dominio import constantes
from isocentro.papel import rodape

_LOG = logging.getLogger(__name__)

# Empacotado, os logos ficam em ``_internal/assets`` — um nível ABAIXO do
# executável. Por isso ``pasta_assets`` e não ``pasta_do_app``: errar aqui é a
# capa sair sem logo, impressa, sem nenhum aviso na tela.
_ASSETS = str(raiz.pasta_assets())
LOGO_CLINICA = os.path.join(_ASSETS, "logo_clinica.png")
LOGO_REDE = os.path.join(_ASSETS, "logo_rede.png")

# ── Paleta do modelo ─────────────────────────────────────────────────────────
AZUL_TITULO = HexColor("#0078AE")   # "Ficha de Tratamento" e a faixa masculina
VERMELHO = HexColor("#C00000")      # a mesma faixa, quando a paciente é mulher
# Sexo que o relatório não trouxe (ou trouxe ilegível): a faixa sai NEUTRA em vez
# de escolher uma das duas cores no chute. Quem confere a capa vê que falta, e a
# tela avisa (ver ``capa.PainelCapa._avisos_proprios``).
CINZA_SEM_SEXO = HexColor("#8C8C8C")
TEAL = HexColor("#1DBCB8")          # DDN/ID, máquina, curso e descrição
CINZA = HexColor("#D3D3D3")         # cabeçalhos de tabela
# A faixa de fotos tinha um cinza só dela (#C0C0C0). Passou a usar o CINZA dos
# demais títulos: na contracapa são cinco blocos empilhados, e dois tons de
# cinza de título faziam um parecer mais importante que os outros sem motivo.
AMBAR = HexColor("#FEC422")         # preparo que exige ação (bexiga cheia etc.)

FONTE = "Helvetica"
FONTE_B = "Helvetica-Bold"

# Espessura das réguas do formulário, como no modelo.
_LW = 0.75

# Raio dos cantos das tabelas. O modelo institucional é todo em canto reto; o
# arredondamento é escolha desta versão. Num formulário tão denso, mais que uns
# 5 pt começa a comer a primeira letra das células de canto.
_RAIO = 5.0

# Alertas de enfermagem — a coluna fixa da capa, sempre os sete, sempre nesta
# ordem. São impressos mesmo em branco: a capa é onde a enfermagem anota, e uma
# linha ausente é uma pergunta que ninguém faz.
ALERTAS = (
    "ALERGIA",
    "QT CONCOMITANTE",
    "CARDIOPATA",
    "QUEDA",
    "PRECAUÇÃO DE CONTATO",
    "USO PSICOTRÓPICO",
    "RADIODERMITE/MUCOSITE",
)

# Preparo e posicionamento (página 2). As três primeiras são as que mudam o que
# o técnico faz antes de deitar o paciente, e por isso ganham fundo âmbar quando
# têm valor — ver ``_destacar``.
COLUNAS_PREPARO = ("BEXIGA", "RETO", "PARA O GANTRY", "DECÚBITO", "BRAÇOS", "JEJUM")
PREPARO_DESTACADO = ("BEXIGA", "RETO", "BRAÇOS")

VAZIO = capa_dados.VAZIO_PREPARO

# Altura do quadro da foto 3×4, IGUAL nas duas folhas. É a altura que o bloco
# de identificação da capa tem (83,2 pt); a contracapa, cujo bloco é 38 pt mais
# curto, deixa a moldura passar por baixo dele em vez de encolher a foto.
# A largura do slot é 93,4 pt — a proporção que sai daqui é a que mais se
# aproxima de um 3×4 sem invadir a margem da folha.
_ALT_FOTO_3X4 = 83.2

# Quantos setups de posicionamento cabem na folha 2 (ver ``ARRANJO_FOTOS``).
# O que passa sai avisado, não escondido.
#
# DOIS, e não três. Com três, a faixa virava colunas: cada montagem ficava com
# um terço da largura e as fotos encolhiam até o ponto em que não se confere
# mais a montagem — que é a única razão de a foto estar impressa. Além disso o
# quadro de preparo ganhava uma coluna de valores por setup e empurrava o
# carimbo para fora da folha. Dois é o que o papel comporta sem deformar, e é
# o caso real: um paciente tratado de dois sítios tem dois jeitos de ser
# deitado; um terceiro é raro e cabe numa segunda contracapa.
MAX_SETUPS = 2

# Os valores que o relatório institucional oferece em cada coluna, na grafia
# dele — é assim que a capa da clínica está escrita há anos, e uma capa que diga
# "Ao longo do corpo" onde as outras dizem "Ao lado corpo" faz o conferente
# parar para pensar se é a mesma coisa. Texto livre continua valendo: o serviço
# inventa instrução nova antes de o app ser atualizado.
OPCOES_PREPARO: dict[str, tuple[str, ...]] = {
    "BEXIGA": (VAZIO, "Cheia", "Vazia"),
    "RETO": (VAZIO, "Vazio", "Cheio"),
    "PARA O GANTRY": ("Cabeça", "Pé"),
    "DECÚBITO": ("Dorsal", "Ventral", "Lateral Dir", "Lateral Esq"),
    "BRAÇOS": (VAZIO, "Sobre Tórax", "Ao lado corpo", "Afastados corpo",
               "Esquerdo elevado", "Direito elevado", "Ambos elevados"),
    "JEJUM": (VAZIO, "4h", "6h"),
}


@dataclass
class Bloco:
    """Uma prescrição como ela sai impressa na capa."""
    titulo: str = ""
    aprovado_por: str = ""
    volumes: list[str] = field(default_factory=list)
    frequencia: str = ""
    notas: str = ""          # estadiamento/observação livre, à direita


@dataclass
class Capa:
    """Tudo que a capa imprime — o que veio do relatório já com as edições da tela.

    Um dataclass único, e não o ``Resultado`` do :mod:`capa_dados`, porque a
    partir do momento em que a tela deixa editar não existe mais "o dado do
    relatório": existe o que vai ser impresso e assinado.
    """
    # Identificação
    nome: str = ""
    registro: str = ""
    nascimento: str = ""
    sexo: str = ""
    convenio: str = ""
    contato: str = ""
    medico: str = ""
    maquina: str = ""
    foto: Optional[bytes] = None
    # O paciente foi achado no relatório de CADASTRO? Não é firula: separa
    # "o relatório diz que não há contato" de "não sabemos se há" — a primeira
    # se imprime, a segunda não (ver ``_contato_impresso``).
    cadastro_achado: bool = False

    # Curso
    curso: str = ""
    intencao: str = ""
    data_aprovacao: str = ""
    descricao: str = ""
    cid: str = ""

    # Corpo
    blocos: list[Bloco] = field(default_factory=list)

    # Enfermagem
    alertas: dict[str, str] = field(default_factory=dict)      # rótulo → marca
    datas_alternadas: dict[str, str] = field(default_factory=dict)
    planos_cuidado: str = ""

    # Página 2 — um ou mais setups de posicionamento (ver ``capa_dados.Setup``).
    # O paciente tratado de fêmur E de tórax tem dois jeitos de ser deitado, com
    # acessórios e preparo diferentes; a folha 2 mostra os dois lado a lado.
    setups: list[capa_dados.Setup] = field(
        default_factory=lambda: [capa_dados.Setup()])

    # ── Atalhos para o setup único ───────────────────────────────────────
    # A maioria dos casos tem um setup só, e a tela, os testes e o código que
    # veio antes falam dele direto. Estas propriedades mantêm essa linguagem
    # sem duplicar o dado: quem escreve, escreve no primeiro setup.

    def _principal(self) -> capa_dados.Setup:
        if not self.setups:
            self.setups = [capa_dados.Setup()]
        return self.setups[0]

    @property
    def fotos_posicionamento(self) -> list:
        return self._principal().fotos

    @fotos_posicionamento.setter
    def fotos_posicionamento(self, valor) -> None:
        self._principal().fotos = list(valor or [])

    @property
    def acessorios(self) -> str:
        return self._principal().acessorios

    @acessorios.setter
    def acessorios(self, valor) -> None:
        self._principal().acessorios = str(valor or "")

    @property
    def preparo(self) -> dict:
        return self._principal().preparo

    @preparo.setter
    def preparo(self, valor) -> None:
        self._principal().preparo = dict(valor or {})

    def setups_impressos(self) -> list:
        """Os setups que cabem na folha 2 (ver ``MAX_SETUPS``)."""
        return [s for s in self.setups[:MAX_SETUPS]]

    def idade(self) -> str:
        return capa_dados.idade(self.nascimento)

    def ddn(self) -> str:
        """``"21/4/1947 (79)"`` — data e idade, como no modelo."""
        d = capa_dados.data_curta(self.nascimento)
        i = self.idade()
        return f"{d} ({i})" if d and i else d

    def feminino(self) -> bool:
        return str(self.sexo or "").strip().upper().startswith("F")

    def masculino(self) -> bool:
        return str(self.sexo or "").strip().upper().startswith("M")

    def sexo_definido(self) -> bool:
        """O sexo dá para reconhecer? É ele que escolhe a cor da faixa do nome.

        Nem sempre vem: paciente recém-cadastrado, relatório com o campo em
        branco ou escrito de um jeito que o app não conhece. Aí a faixa sai
        neutra e a tela reclama, em vez de a capa afirmar um sexo por sorteio.
        """
        return self.feminino() or self.masculino()

    def cor_da_faixa(self):
        """Cor de fundo da faixa do nome: vermelha (F), azul (M) ou neutra."""
        if self.feminino():
            return VERMELHO
        return AZUL_TITULO if self.masculino() else CINZA_SEM_SEXO


SEM_CONTATO = "Não cadastrado"


def _contato_impresso(capa: "Capa") -> str:
    """O telefone, ou o recado de que não há — nunca uma célula em branco.

    Célula vazia na sala de tratamento se lê como esquecimento: alguém vai
    procurar o telefone em outro sistema, ou anotar um número de memória. Dizer
    "Não cadastrado" encerra a busca.

    Só se diz isso quando o paciente FOI achado no cadastro e o campo veio
    vazio — aí é o relatório afirmando que não há contato (72% dos pacientes da
    última exportação). Sem linha de cadastro nenhuma, ninguém sabe se existe
    telefone, e afirmar que não há seria inventar dado no papel; nesse caso a
    célula fica vazia mesmo, e a tela avisa que o cadastro faltou.
    """
    if capa.contato.strip():
        return capa.contato
    return SEM_CONTATO if capa.cadastro_achado else ""


def de_resultado(res: capa_dados.Resultado, *, nome: str = "", registro: str = "",
                 nascimento: str = "", maquina: str = "",
                 medico: str = "") -> Capa:
    """Monta a capa a partir do que a busca nos relatórios achou.

    Os argumentos nomeados são o que a **ficha** já sabe do paciente e entram
    onde o relatório não trouxe nada. O relatório é a fonte preferida — é dele
    que saem convênio e curso —, mas um paciente recém-cadastrado pode ainda não
    estar na exportação, e aí a capa nasce com o que veio do DICOM em vez de em
    branco.
    """
    c = res.cadastro
    # Nome e médico em grafia canônica, não em CAIXA ALTA (25/08/2026): a capa
    # anda grampeada na ficha, e a mesma pessoa saía nas duas com grafias
    # diferentes. Formatado aqui mesmo com a fonte já formatando, porque um
    # espelho gravado ANTES desta mudança ainda guarda o nome cru do banco — e
    # por ``de_pessoa``, a forma completa, porque espelho mais antigo ainda
    # pode ter o nome como o banco o entrega: invertido.
    capa = Capa(
        nome=capa_dados.de_pessoa(c.nome or nome),
        registro=c.registro or registro,
        nascimento=c.nascimento or nascimento,
        sexo=c.sexo,
        convenio=c.convenio,
        contato=c.contato,
        medico=capa_dados.de_pessoa(medico_completo(c.medico or medico)),
        # Nome de EXIBIÇÃO: a máquina chega crua do banco (``cad.maquina``) e
        # já rotulada quando vem da bancada. ``rotulo_maquina`` é idempotente
        # — nome já trocado não casa de novo —, então rotular aqui cobre as
        # duas portas de uma vez, e a capa deixa de discordar da ficha que anda
        # grampeada nela.
        maquina=constantes.rotulo_maquina(c.maquina or maquina),
        foto=res.foto,
        cadastro_achado=bool(res.achou),
        curso=c.curso,
        intencao=c.intencao,
        descricao=c.descricao,
        cid=c.cid,
    )
    escolhidas = [o for o in opcoes_de(res) if o.marcada]
    capa.blocos = [o.bloco for o in escolhidas]
    # A data de aprovação do cabeçalho é a da prescrição mais recente ENTRE AS
    # ESCOLHIDAS — é o carimbo de "esta capa vale a partir de quando", e uma
    # prescrição de outro curso, que nem entrou, não pode datá-la.
    datas = [o.data for o in escolhidas if o.data]
    if datas:
        capa.data_aprovacao = capa_dados.data_curta(max(datas, key=_ordem_data))
    capa.preparo = {col: VAZIO for col in COLUNAS_PREPARO}
    return capa


@dataclass
class Opcao:
    """Uma prescrição aprovada oferecida para entrar na capa.

    O relatório traz o histórico inteiro do paciente — o TC9 tem nove
    prescrições de quatro cursos, algumas de 2024. Só cabem três na folha, e
    escolher as três primeiras por ordem de arquivo colocaria na capa um
    tratamento que acabou há dois anos. Quem escolhe é a pessoa; o programa
    ordena por data e marca de saída as do curso que está correndo.
    """
    bloco: Bloco
    curso: str = ""
    data: str = ""
    do_curso_atual: bool = False
    marcada: bool = False

    def rotulo(self) -> str:
        """``"13/5/2026 · C1_MAIO_2026 · Palato duro: …"`` — a data primeiro."""
        partes = [p for p in (capa_dados.data_curta(self.data), self.curso,
                              self.bloco.titulo) if p]
        return "  ·  ".join(partes)


def opcoes_de(res: capa_dados.Resultado) -> list[Opcao]:
    """As prescrições do paciente, da mais recente para a mais antiga.

    Vêm marcadas as do **curso atual** — o que o cadastro aponta como o curso em
    tratamento e, sem cadastro, o curso da prescrição mais recente. Se a marcação
    passar do que cabe na folha, as extras entram desmarcadas: melhor a capa
    pedir uma escolha do que sair com um bloco cortado.
    """
    ordenadas = sorted(res.prescricoes, key=lambda p: _ordem_data(p.data_aprovacao),
                       reverse=True)
    atual = (res.cadastro.curso or "").strip()
    if not atual and ordenadas:
        atual = (ordenadas[0].curso or "").strip()
    alvo = capa_dados.normalizar_nome(atual)

    out: list[Opcao] = []
    marcadas = 0
    for p in ordenadas:
        do_atual = bool(alvo) and capa_dados.normalizar_nome(p.curso) == alvo
        marcar = do_atual and marcadas < MAX_BLOCOS
        marcadas += 1 if marcar else 0
        out.append(Opcao(
            bloco=Bloco(titulo=p.titulo(), aprovado_por=p.aprovador,
                        volumes=[v.linha() for v in p.volumes],
                        frequencia=p.linha_frequencia(),
                        notas=p.notas),
            curso=p.curso, data=p.data_aprovacao,
            do_curso_atual=do_atual, marcada=marcar))
    # Nenhuma marcada (curso do cadastro não bate com nenhuma prescrição): entra
    # a mais recente, para a capa não sair vazia sem ninguém ter decidido isso.
    if out and not any(o.marcada for o in out):
        out[0].marcada = True
    return out


def _ordem_data(texto: str):
    d = capa_dados.ler_data(texto)
    return d or date.min


def medico_completo(nome: str) -> str:
    """Expande o nome do médico para a grafia canônica da equipe.

    O relatório exporta um apelido curto ("Barbara Peixoto", "Thais
    Sartori") enquanto a capa institucional imprime o nome inteiro. A lista
    canônica do serviço já resolve isso para a ficha; aqui é a mesma
    reconciliação, com o mesmo critério estrito de ``dicom_rt.mesma_pessoa`` —
    nome que não casa com ninguém sai como veio, porque um médico novo é mais
    provável que um erro de digitação.
    """
    n = str(nome or "").strip()
    if not n:
        return ""
    try:
        from isocentro.dados.equipe import MEDICOS
        from isocentro.dicom import dicom_rt

        return dicom_rt.mesma_pessoa(n, MEDICOS) or n
    except Exception:  # noqa: BLE001 — nome curto ainda identifica o médico
        _LOG.exception("Capa: falha ao expandir o nome do médico %r", n)
        return n


# ── Imagens ──────────────────────────────────────────────────────────────────
# As fotos de posicionamento saem do celular do técnico: 4 a 5 MB, uns 4000 ×
# 3000 px. O quadro que as recebe na folha 2 tem 276 × 198 pt — cerca de 3,8 ×
# 2,8 polegadas. Embutir o bitmap inteiro faz o ReportLab gravá-lo SEM
# compressão: a capa de um paciente com três fotos passou de 120 MB e levou 40
# segundos para fechar, o que na prática é uma capa que não imprime.
#
# Então a foto é reduzida ao tamanho em que vai ser impressa, a uma resolução
# de impressão honesta, e recomprimida em JPEG.
_DPI_IMPRESSAO = 200

# Abaixo disto não vale mexer: o custo do recorte supera o que se economiza, e
# a foto 3×4 que vem do relatório já é pequena.
_MIN_PIXELS_PARA_REDUZIR = 1_200 * 900


def _reamostrar(dados, largura_pt: float, altura_pt: float):
    """Reduz a imagem ao tamanho impresso, em JPEG. Devolve ``dados`` se não der.

    Falha aqui nunca é fatal: pior caso, a capa sai grande — que é o
    comportamento de antes — em vez de não sair.
    """
    if not isinstance(dados, (bytes, bytearray)):
        return dados                      # caminho de arquivo (os logos)
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(dados))
        if img.width * img.height <= _MIN_PIXELS_PARA_REDUZIR:
            return dados
        alvo_w = max(int(largura_pt / 72 * _DPI_IMPRESSAO), 1)
        alvo_h = max(int(altura_pt / 72 * _DPI_IMPRESSAO), 1)
        escala = min(alvo_w / img.width, alvo_h / img.height, 1.0)
        if escala >= 1.0:
            return dados
        img = img.convert("RGB").resize(
            (max(int(img.width * escala), 1), max(int(img.height * escala), 1)),
            Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        _LOG.exception("Falha ao reamostrar imagem da capa — usando a original")
        return dados


# ── Helpers de desenho ───────────────────────────────────────────────────────

class _Folha:
    """Canvas A4 com origem no topo-esquerda e as primitivas do formulário."""

    def __init__(self, c: canvas.Canvas):
        self.c = c
        self.W, self.H = A4

    def y(self, topo: float) -> float:
        return self.H - topo

    def caixa(self, x0, y0, x1, y1, cor) -> None:
        """Retângulo preenchido, sem borda (as réguas vêm depois, por cima)."""
        self.c.setFillColor(cor)
        self.c.rect(x0, self.y(y1), x1 - x0, y1 - y0, stroke=0, fill=1)

    def linha(self, x0, y0, x1, y1) -> None:
        self.c.setStrokeColor(black)
        self.c.setLineWidth(_LW)
        self.c.line(x0, self.y(y0), x1, self.y(y1))

    @contextlib.contextmanager
    def bloco(self, x0, y0, x1, y1, raio: float = None):
        """Arredonda os cantos de uma tabela inteira.

        Tudo desenhado dentro do ``with`` — faixas de cor, réguas internas,
        imagens — é **aparado** por um retângulo de cantos redondos, e o
        contorno é traçado por cima no fim. Sem o recorte, o quadradinho da
        grade vazaria por fora do arco, que é o defeito que faz um canto
        arredondado parecer um erro de impressão.
        """
        c = self.c
        r = _RAIO if raio is None else raio
        c.saveState()
        p = c.beginPath()
        p.roundRect(x0, self.y(y1), x1 - x0, y1 - y0, r)
        c.clipPath(p, stroke=0, fill=0)
        try:
            yield
        finally:
            c.restoreState()
        c.setStrokeColor(black)
        c.setLineWidth(_LW)
        c.roundRect(x0, self.y(y1), x1 - x0, y1 - y0, r, stroke=1, fill=0)

    def grade(self, x0, y0, x1, y1, verticais=(), horizontais=()) -> None:
        """Moldura de uma tabela mais as divisórias internas informadas."""
        self.linha(x0, y0, x1, y0)
        self.linha(x0, y1, x1, y1)
        for x in (x0, x1, *verticais):
            self.linha(x, y0, x, y1)
        for y in horizontais:
            self.linha(x0, y, x1, y)

    def txt(self, x, topo, texto, fonte=FONTE, tam=9.0, cor=black) -> float:
        """Texto com o TOPO em ``topo`` (não a linha de base). Devolve a largura.

        O modelo foi medido pelo topo dos glifos; converter aqui uma vez evita
        repetir o mesmo ajuste em cada uma das dezenas de chamadas.
        """
        if texto in (None, ""):
            return 0.0
        s = str(texto)
        self.c.setFont(fonte, tam)
        self.c.setFillColor(cor)
        self.c.drawString(x, self.y(topo + tam * 0.86), s)
        return self.c.stringWidth(s, fonte, tam)

    def txt_centro(self, x0, x1, topo, texto, fonte=FONTE, tam=9.0, cor=black,
                   minimo=6.0) -> None:
        """Centrado entre x0 e x1, encolhendo o que não caberia entre eles.

        Nome de paciente com quatro sobrenomes é rotina, e o slot do modelo tem
        largura fixa — sem o encolhimento o nome invadiria a caixa do DDN.
        """
        if texto in (None, ""):
            return
        s = str(texto)
        # Folga de 6 pt de cada lado: sem ela, um nome de quatro sobrenomes
        # encolhe até caber e encosta nas bordas da faixa colorida, o que fica
        # pior de ler do que um ponto de fonte a menos.
        disp = x1 - x0 - 12
        larg = self.c.stringWidth(s, fonte, tam)
        if larg > disp > 0:
            tam = max(tam * disp / larg, minimo)
        self.c.setFont(fonte, tam)
        self.c.setFillColor(cor)
        self.c.drawCentredString((x0 + x1) / 2, self.y(topo + tam * 0.86), s)

    def txt_direita(self, x, topo, texto, fonte=FONTE, tam=9.0, cor=black) -> None:
        if texto in (None, ""):
            return
        self.c.setFont(fonte, tam)
        self.c.setFillColor(cor)
        self.c.drawRightString(x, self.y(topo + tam * 0.86), str(texto))

    def txt_ajustado(self, x, topo, texto, largura, fonte=FONTE, tam=9.0,
                     cor=black, minimo=6.0) -> None:
        """Como :meth:`txt`, encolhendo SÓ o que não caberia em ``largura``.

        Nome comprido e descrição longa de CID são a regra, não a exceção, e um
        texto que vaza para a célula vizinha é pior do que um ponto de fonte a
        menos.
        """
        if texto in (None, ""):
            return
        s = str(texto)
        if self.c.stringWidth(s, fonte, tam) > largura > 0:
            tam = max(tam * largura / self.c.stringWidth(s, fonte, tam), minimo)
        self.txt(x, topo, s, fonte, tam, cor)

    def imagem(self, dados, x0, y0, x1, y1, *, encaixar=True) -> None:
        """Desenha a imagem dentro do retângulo, preservando a proporção.

        ``dados`` pode ser bytes ou caminho. Imagem ilegível não derruba a capa:
        o quadro fica vazio, como ficaria se ninguém tivesse tirado a foto.
        """
        if not dados:
            return
        try:
            lw, lh = x1 - x0, y1 - y0
            dados = _reamostrar(dados, lw, lh)
            origem = io.BytesIO(dados) if isinstance(dados, (bytes, bytearray)) else dados
            img = ImageReader(origem)
            if encaixar:
                iw, ih = img.getSize()
                escala = min(lw / iw, lh / ih)
                w, h = iw * escala, ih * escala
                x, y = x0 + (lw - w) / 2, y0 + (lh - h) / 2
            else:
                x, y, w, h = x0, y0, lw, lh
            self.c.drawImage(img, x, self.y(y + h), w, h, mask="auto")
        except Exception:  # noqa: BLE001 — quadro vazio, capa inteira
            _LOG.exception("Falha ao desenhar imagem na capa")

    def logo(self, arquivo, x0, y0, x1, y1, ancora="esquerda") -> None:
        """Logo com a ALTURA do slot, encostado numa das margens.

        A proporção do arquivo em ``assets/`` não é exatamente a do slot medido
        no modelo; esticar deformaria a marca, e centrar deixaria uma folga
        contra a borda da folha. Preenche a altura e encosta no lado.
        """
        if not os.path.exists(arquivo):
            _LOG.warning("Logo não encontrado em %s — a capa sai sem ele", arquivo)
            return
        try:
            img = ImageReader(arquivo)
            iw, ih = img.getSize()
            h = y1 - y0
            w = min(iw * h / ih, x1 - x0)
            x = x0 if ancora == "esquerda" else x1 - w
            self.c.drawImage(img, x, self.y(y0 + h), w, h, mask="auto")
        except Exception:  # noqa: BLE001
            _LOG.exception("Falha ao desenhar o logo %s", arquivo)


def _cabecalho(f: _Folha, capa: Capa, topo: float,
               completo: bool = True) -> float:
    """Logos, título e o bloco de identificação. Devolve o y do fim do bloco.

    ``topo`` é o y da primeira régua: a página 2 sobe o bloco 4,4 pt em relação
    à 1 para caber a faixa de fotos, exatamente como o modelo.

    ``completo=False`` (contracapa): saem as linhas de CONVÊNIO/sexo/CONTATO e a
    faixa da MÁQUINA. As duas folhas andam grampeadas e essas três informações
    já estão na capa — repeti-las custava 38 pt de altura que as fotos de
    posicionamento usam melhor. Ficam o nome, o DDN/RGH e o médico, que é o que
    identifica a folha se ela se soltar do maço.
    """
    # Cada logo encosta na sua margem — centrá-las no slot deixaria uma folga
    # assimétrica em relação à borda da folha, que é onde o olho compara.
    f.logo(LOGO_CLINICA, 15.6, 21.6, 105.9, 48.5, ancora="esquerda")
    f.logo(LOGO_REDE, 429.1, 14.1, 578.0, 51.5, ancora="direita")
    f.txt_centro(184.5, 380.0, 25.4, "Ficha de Tratamento", FONTE_B, 20.0, AZUL_TITULO)

    # Réguas: o bloco vai de x=16,2 a 479,7; a foto ocupa a coluna da direita.
    x0, xf, x1 = 16.2, 479.7, 579.6
    y_nome = topo + 25.6            # faixa do nome/DDN/ID
    y_medico = topo + 45.0          # linha do médico assistente
    y_conv = topo + 64.5            # convênio / sexo / contato
    y_maq = topo + 83.2             # faixa da máquina
    y_fim = y_maq if completo else y_medico

    with f.bloco(x0, topo, xf, y_fim):
        # A cor da faixa É a informação do sexo: vermelha, azul ou neutra
        # quando não se sabe (ver ``Capa.cor_da_faixa``).
        f.caixa(x0, topo, 275.6, y_nome, capa.cor_da_faixa())
        f.caixa(275.6, topo, xf, y_nome, TEAL)

        f.txt_centro(x0, 275.6, topo + 6.2, capa.nome, FONTE_B, 12.0, white)
        f.txt(284.5, topo + 7.3, "DDN", FONTE_B, 10.0, white)
        f.txt(316.1, topo + 7.3, capa.ddn(), FONTE_B, 10.0, white)
        f.txt_centro(397.6, xf, topo + 7.3, capa.registro, FONTE_B, 10.0, white)

        f.txt_centro(x0, xf, y_nome + 4.1, capa.medico, FONTE_B, 10.0, black)

        horizontais = [y_nome]
        if completo:
            f.caixa(x0, y_conv, xf, y_maq, TEAL)
            f.txt(17.2, y_medico + 4.7, "CONVÊNIO", FONTE_B, 9.0)
            f.txt_ajustado(72.9, y_medico + 4.2, capa.convenio, 160.0, FONTE, 10.0)
            f.txt_centro(237.0, 330.3, y_medico + 4.7, capa.sexo, FONTE, 9.0)
            f.txt(331.3, y_medico + 4.7, "CONTATO", FONTE_B, 9.0)
            f.txt(398.6, y_medico + 4.7, _contato_impresso(capa), FONTE, 9.0)
            f.txt_centro(x0, xf, y_conv + 3.3, capa.maquina, FONTE_B, 11.0, white)
            horizontais += [y_medico, y_conv]

        f.grade(x0, topo, xf, y_fim, horizontais=horizontais)
        f.linha(275.6, topo, 275.6, y_nome)
        f.linha(397.6, topo, 397.6, y_nome)
        if completo:
            f.linha(237.0, y_medico, 237.0, y_conv)
            f.linha(330.3, y_medico, 330.3, y_conv)

    # Foto 3×4 à direita, num quadro próprio — o retrato preenche o slot e são
    # os cantos dele que aparam a imagem.
    #
    # O quadro tem a MESMA ALTURA nas duas folhas, e não a do bloco ao lado. Na
    # contracapa o bloco é curto (saem convênio, sexo e máquina), e acompanhá-lo
    # deixava a moldura com quase o dobro da largura da altura: a mesma foto
    # saía recortada de um jeito na capa e de outro na contracapa — duas caras
    # para o mesmo paciente, no documento cuja função é dizer quem ele é.
    y_foto = topo + _ALT_FOTO_3X4
    with f.bloco(485.9, topo, x1 - 0.3, y_foto):
        f.imagem(capa.foto, 485.9, topo, x1 - 0.3, y_foto, encaixar=False)
    # Quem manda no que vem abaixo é o mais baixo dos dois: na contracapa a
    # foto passa do bloco de identificação e é ela que fecha o cabeçalho.
    return max(y_fim, y_foto)


# ── Página 1 ─────────────────────────────────────────────────────────────────

_TOPO_P1 = 56.7

# Faixa CURSO/DESCRIÇÃO e o corpo das prescrições.
_Y_CURSO = 143.7
_Y_DESCRICAO = 156.4
_Y_CORPO = 174.4
_Y_ALERTAS = 497.9          # fim do corpo / início do bloco de enfermagem

# Um bloco de prescrição por 86,2 pt — as posições internas são relativas a ele.
_PASSO_BLOCO = 86.2

# Quantos blocos cabem no corpo da folha 1. É o teto que a tela usa para decidir
# quantas prescrições marcar sozinha (ver ``opcoes_de``).
MAX_BLOCOS = int((_Y_ALERTAS - _Y_CORPO) // _PASSO_BLOCO)
_ALTURA_LINHA = 11.2

# A faixa em que as linhas de volume podem viver dentro do bloco: abaixo do
# título da prescrição e acima do rótulo FREQUÊNCIA.
#
# Elas ficam CENTRADAS no rótulo VOLUME (+37,6), e isso cabia até quatro. Uma
# mama bilateral tem CINCO (PTV mama E, boost E, FSC E, mama D, boost D) e as
# linhas invadiam o título em cima e a FREQUÊNCIA embaixo — texto sobre texto,
# ilegível, numa folha que vai grampeada na ficha. Visto impresso.
#
# Não dá para empurrar a FREQUÊNCIA para baixo: o passo do bloco é fixo e o
# próximo começaria em cima dela. Então o que cede é o espaçamento, até um piso
# em que ainda se lê; passando disso, o excedente é ANUNCIADO em vez de sumir.
_VOL_TOPO = 18.0            # logo abaixo do título
_VOL_BASE = 63.0            # logo acima da FREQUÊNCIA

# A faixa da NOTA, na coluna direita do bloco: começa logo abaixo da caixa
# "Aprovado por" (que vai até +21,8) e termina antes do bloco seguinte (+86,2).
#
# A nota saía numa só altura, +65,6, ao lado da FREQUÊNCIA — herança de quando
# ela era um campo digitado na tela, sempre curto ou vazio. Vinda do ARIA
# (``DimPrescription.Notes``, desde 23/09/2026) ela é o texto que o
# radioterapeuta escreveu: das nove notas do banco na primeira leitura, SEIS
# tinham de três a sete linhas — e a partir da terceira o texto passava por
# baixo da caixa "Aprovado por" do bloco seguinte, ilegível. Medido no PDF.
#
# O espaço entre a caixa e o fim do bloco estava vazio e é onde a nota cabe.
_NOTA_TOPO = 24.0
_NOTA_BASE = 82.0
_MAX_LINHAS_NOTA = int((_NOTA_BASE - _NOTA_TOPO) // _ALTURA_LINHA)
_VOL_ALTURA_MIN = 8.4
_FONTE_VOLUME = 10.0
_FONTE_VOLUME_MIN = 8.0


def _pagina1(f: _Folha, capa: Capa) -> None:
    _cabecalho(f, capa, _TOPO_P1)

    x0, x1 = 16.2, 579.4
    # Curso / intenção / data de aprovação / descrição / CID
    with f.bloco(x0, _Y_CURSO, x1, _Y_CORPO):
        f.caixa(x0, _Y_CURSO, x1, _Y_CORPO, TEAL)
        f.txt(17.2, _Y_CURSO + 1.3, "CURSO", FONTE_B, 9.0, white)
        f.txt_ajustado(63.0, _Y_CURSO + 1.3, capa.curso, 148.0, FONTE, 9.0, white)
        f.txt(217.7, _Y_CURSO + 1.3, "INTENÇÃO", FONTE_B, 9.0, white)
        f.txt_ajustado(274.1, _Y_CURSO + 1.3, capa.intencao, 142.0, FONTE, 9.0, white)
        f.txt(422.3, _Y_CURSO + 1.3, "DATA APROV.", FONTE_B, 9.0, white)
        f.txt(503.5, _Y_CURSO + 1.3, capa.data_aprovacao, FONTE, 9.0, white)
        f.txt(17.2, _Y_DESCRICAO + 4.0, "DESCRIÇÃO", FONTE_B, 9.0, white)
        f.txt_ajustado(85.4, _Y_DESCRICAO + 4.0, capa.descricao, 396.0,
                       FONTE, 9.0, white)
        f.txt(485.9, _Y_DESCRICAO + 4.0, "CID", FONTE_B, 9.0, white)
        f.txt_ajustado(511.5, _Y_DESCRICAO + 4.0, capa.cid, 64.0, FONTE, 9.0, white)

        f.grade(x0, _Y_CURSO, x1, _Y_CORPO, horizontais=(_Y_DESCRICAO,))
        f.linha(216.7, _Y_CURSO, 216.7, _Y_DESCRICAO)
        f.linha(421.3, _Y_CURSO, 421.3, _Y_DESCRICAO)
        f.linha(484.9, _Y_DESCRICAO, 484.9, _Y_CORPO)

    # O corpo é uma moldura só, com as prescrições desenhadas dentro dela.
    with f.bloco(x0, _Y_CORPO, x1, _Y_ALERTAS):
        _prescricoes(f, capa)

    _enfermagem(f, capa)
    _assinaturas(f)


def _prescricoes(f: _Folha, capa: Capa) -> None:
    """Os blocos de prescrição, um a cada 86,2 pt, até o corpo encher.

    O modelo reserva a folha inteira e nunca precisou de mais de três; se vierem
    mais, o excedente é anunciado no rodapé do corpo em vez de sumir — capa que
    esconde uma prescrição aprovada é pior do que capa apertada.
    """
    cabem = MAX_BLOCOS
    for i, b in enumerate(capa.blocos[:cabem]):
        d = i * _PASSO_BLOCO
        # Caixa "Aprovado por", à direita, na altura do título.
        with f.bloco(315.0, _Y_CORPO + d, 576.4, _Y_CORPO + 21.8 + d, raio=4.0):
            f.caixa(315.0, _Y_CORPO + d, 576.4, _Y_CORPO + 21.8 + d, CINZA)
        larg = f.txt(331.7, _Y_CORPO + 1.1 + d, "Aprovado por", FONTE_B, 10.0)
        f.txt_ajustado(331.7 + larg + 4, _Y_CORPO + 1.1 + d,
                       _com_dominio(b.aprovado_por), 240.0 - larg, FONTE, 10.0)

        f.txt_ajustado(17.2, _Y_CORPO + 5.4 + d, b.titulo, 290.0, FONTE, 10.0)
        f.txt(17.2, _Y_CORPO + 37.6 + d, "VOLUME", FONTE_B, 10.0)
        # As linhas de volume ficam centradas na altura do rótulo VOLUME, e
        # comprimem-se para não invadir o título nem a FREQUÊNCIA.
        linhas, alt_linha, corpo = _volumes_que_cabem(b.volumes)
        y_vol = _Y_CORPO + 37.6 + d - (len(linhas) - 1) * alt_linha / 2
        for j, v in enumerate(linhas):
            f.txt_ajustado(95.9, y_vol + j * alt_linha, v, 200.0, FONTE, corpo)
        f.txt(17.2, _Y_CORPO + 65.6 + d, "FREQUÊNCIA", FONTE_B, 10.0)
        f.txt_ajustado(95.9, _Y_CORPO + 65.6 + d, b.frequencia, 200.0, FONTE, 10.0)
        for j, nota in enumerate(_notas_que_cabem(b.notas)):
            f.txt_ajustado(300.7, _Y_CORPO + _NOTA_TOPO + d + j * _ALTURA_LINHA,
                           nota, 270.0, FONTE, 10.0)

    sobra = len(capa.blocos) - cabem
    if sobra > 0:
        f.txt(17.2, _Y_ALERTAS - 13.0,
              f"⚠ Mais {sobra} prescrição(ões) aprovada(s) não couberam nesta "
              "folha — confira no sistema.", FONTE_B, 9.0)


def _volumes_que_cabem(volumes: list) -> tuple:
    """``(linhas, altura_da_linha, corpo_da_fonte)`` para caber na faixa.

    Devolve o que desenhar, não o que existe: quando nem comprimido cabe, a
    última linha vira "+ N volume(s)". Esconder um alvo prescrito seria pior que
    apertar a folha — quem confere na sala precisa saber que há mais.
    """
    n = len(volumes)
    if n <= 1:
        return list(volumes), _ALTURA_LINHA, _FONTE_VOLUME
    # Centradas em +37,6: o espaço útil é o dobro da menor das duas folgas.
    espaco = 2 * min(37.6 - _VOL_TOPO, _VOL_BASE - 37.6)
    altura = min(_ALTURA_LINHA, espaco / (n - 1))
    if altura >= _VOL_ALTURA_MIN:
        # A fonte só encolhe quando o espaçamento encolheu, e acompanha-o: fonte
        # de corpo 10 em linha de 9,8 pt encosta uma linha na outra.
        fonte = (_FONTE_VOLUME if altura >= _ALTURA_LINHA
                 else max(_FONTE_VOLUME_MIN, altura - 1.4))
        return list(volumes), altura, fonte
    cabem = int(espaco / _VOL_ALTURA_MIN) + 1
    resto = n - (cabem - 1)
    linhas = list(volumes[:cabem - 1])
    linhas.append(f"+ {resto} volume(s) — confira no sistema")
    return linhas, _VOL_ALTURA_MIN, _FONTE_VOLUME_MIN


def _notas_que_cabem(texto: str) -> list[str]:
    """As linhas da nota que cabem na coluna direita do bloco.

    Mesma regra dos volumes (:func:`_volumes_que_cabem`): o que não couber é
    ANUNCIADO, não sumido. Nota cortada em silêncio é pior do que nota
    incompleta — quem confere na sala não tem como saber que o médico escreveu
    mais três linhas, e é ali que mora "após QT" ou o que condiciona o
    tratamento.

    Aqui o corte é por número de linhas e não por espaçamento: a nota é texto
    livre, e espremer o entrelinhas até caber sete linhas deixaria as sete
    ilegíveis em vez de cinco legíveis.
    """
    linhas = _linhas(texto)
    if len(linhas) <= _MAX_LINHAS_NOTA:
        return linhas
    resto = len(linhas) - (_MAX_LINHAS_NOTA - 1)
    return linhas[:_MAX_LINHAS_NOTA - 1] + [
        f"+ {resto} linha(s) — confira no sistema"]


def _com_dominio(login: str) -> str:
    """``"barbara.teles"`` → ``"clinica\\barbara.teles"``.

    O relatório exporta só o login; a capa imprime com o domínio, que é como a
    assinatura eletrônica aparece no relatório. Login que já vem qualificado passa
    intacto.
    """
    s = str(login or "").strip()
    return s if not s or "\\" in s else f"clinica\\{s}"


def _linhas(texto: str) -> list[str]:
    return [l for l in str(texto or "").splitlines() if l.strip()]


def _enfermagem(f: _Folha, capa: Capa) -> None:
    """Alertas, dias alternados e planos de cuidado — a faixa da enfermagem."""
    y0, y_cab, y1 = 501.7, 518.9, 608.4
    colunas = ((16.2, 190.6, "ALERTAS"), (194.5, 298.9, "DIAS ALTERNADOS"),
               (303.2, 579.4, "PLANOS DE CUIDADO"))
    for xa, xb, titulo in colunas:
        with f.bloco(xa, y0, xb, y1):
            f.caixa(xa, y0, xb, y_cab, CINZA)
            f.txt(xa + 1.0, y0 + 3.6, titulo, FONTE_B, 9.0)
            f.grade(xa, y0, xb, y1, horizontais=(y_cab,))

    passo = (y1 - y_cab) / len(ALERTAS)
    for i, rotulo in enumerate(ALERTAS):
        y = y_cab + i * passo
        f.txt_ajustado(17.2, y + 1.4, rotulo, 130.0, FONTE, 9.0)
        f.txt_centro(152.7, 190.6, y + 1.4, capa.alertas.get(rotulo, ""), FONTE, 9.0)
        larg = f.txt(195.5, y + 1.4, "DATA:", FONTE, 9.0)
        f.txt(195.5 + larg + 4, y + 1.4,
              capa.datas_alternadas.get(rotulo, ""), FONTE, 9.0)
        if i:
            f.linha(16.2, y, 190.6, y)
            f.linha(194.5, y, 298.9, y)
    f.linha(152.7, y_cab, 152.7, y1)     # coluna da marcação dos alertas

    for i, linha in enumerate(_linhas(capa.planos_cuidado)):
        f.txt_ajustado(305.0, y_cab + 2.0 + i * 11.2, linha, 270.0, FONTE, 9.0)


def _assinaturas(f: _Folha) -> None:
    """As seis caixas de assinatura do primeiro dia. Sempre em branco."""
    x0, x1 = 16.2, 579.4
    y0, y_cab, y_meio, y1 = 624.9, 639.2, 703.6, 768.1
    with f.bloco(x0, y0, x1, y1):
        f.caixa(x0, y0, x1, y_cab, CINZA)
        f.txt(17.2, y0 + 2.1, "PRIMEIRO DIA DE TRATAMENTO", FONTE_B, 9.0)
        f.txt(397.3, y0 + 2.1, "APROVAÇÃO TRATAMENTO", FONTE_B, 9.0)
        f.grade(x0, y0, x1, y1, verticais=(211.4, 396.3),
                horizontais=(y_cab, y_meio))
        f.linha(396.3, y0, 396.3, y_cab)
    for x, sup, inf in ((17.2, "MÉDICO", "FÍSICO MÉDICO"),
                        (212.4, "TÉCNICO(A) 1", "TÉCNICO(A) 2"),
                        (397.3, "FÍSICO MÉDICO", "DUPLO CHECK")):
        f.txt(x, y_cab + 0.9, sup, FONTE, 9.0)
        f.txt(x, y_meio + 1.0, inf, FONTE, 9.0)


# ── Página 2 ─────────────────────────────────────────────────────────────────

_TOPO_P2 = 52.3


_X_MEIO_P2 = 297.7          # divisória entre os dois setups

# ── Geometria da folha 2 ─────────────────────────────────────────────────────
# A faixa de fotos começa abaixo do CABEÇALHO — que na contracapa termina na
# foto 3×4, não no bloco de identificação: a foto tem a mesma altura das duas
# folhas e passa por baixo do bloco, que ali é curto. Quem devolve esse y é o
# ``_cabecalho``; nada aqui pode assumir a altura dele.
#
# A faixa tem ALTURA VARIÁVEL: ocupa o que o arranjo de fotos pede e devolve o
# resto para os blocos de baixo, em vez de reservar sempre o mesmo retângulo e
# deixar meia folha em branco quando o caso tem um posicionamento só.
_GAP_CABECALHO_P2 = 3.0
# O carimbo da equipe: altura FIXA e pé da folha.
#
# ``_ALT_CARIMBO`` é a faixa de título (18 pt) mais o espaço do carimbo em si.
# Um carimbo de clínica tem uns 20 mm (57 pt) e a assinatura vai POR CIMA dele —
# 74 pt davam 56 pt úteis, exatamente o carimbo e nada para a assinatura, que
# saía espremida ou por cima do texto. São 92 pt: 74 úteis, o carimbo e a
# assinatura sem disputar o mesmo espaço.
#
# O que cede é o quadro de acessórios, que já se ajusta ao que sobra da folha
# (ver ``_linhas_que_cabem``) — não o pé da página, que é fixo.
_ALT_CARIMBO = 92.0
_ALT_MIN_CARIMBO = 60.0
# Onde a folha acaba para efeito de conteúdo (abaixo fica o rodapé "Impresso
# em…"). O carimbo nunca passa daqui.
_Y_PE_FOLHA = 786.3
# Altura do bloco de devolução de exames (faixa de título + a linha a preencher).
_ALT_EXAMES = 32.2
# Teto da faixa de fotos: o que sobra é dos blocos de baixo.
#
# Era 324 pt até 04/09/2026, e a troca foi pedida pelo uso: com DOIS
# posicionamentos o quadro de acessórios ficava com CINCO linhas, e as notas do
# serviço passam disso com frequência. Medido, o corte de 34 pt dá:
#
#   1 setup  →  foto 190 pt, 15 linhas   (NÃO MUDA: ali quem limita é o teto
#                                         _ALT_CELA_MAX, não a faixa)
#   2 setups →  foto 125 → 108 pt, 5 → 8 linhas
#
# Oito linhas contra cinco, ao preço de 17 pt em cada foto. Vale porque a foto
# de 108 pt continua legível para conferir a montagem — e acessório que não
# coube não é lido de lugar nenhum: ele simplesmente não vai para a sala.
_ALT_MAX_FOTOS = 290.0
_GAP_P2 = 3.0               # respiro entre os blocos empilhados
_ALT_CAB_P2 = 18.0          # faixa cinza de título de um bloco

# O DECÚBITO sai da contracapa: a pág. 2 da Ficha Técnica já traz a coluna
# "Posicionamento" (decúbito + para onde vai a cabeça), lida do DICOM, e as duas
# folhas andam grampeadas. Repetir só cria duas versões da mesma verdade.
# Fora da contracapa: a pág. 2 da Ficha Técnica já traz DECÚBITO e a posição em
# relação ao gantry ("Cabeça para o gantry"). Repetir aqui gasta duas das poucas
# linhas do quadro com o que quem confere já leu na folha anterior.
_JA_NA_FICHA_TECNICA = ("DECÚBITO", "PARA O GANTRY")
PREPARO_NA_CONTRACAPA = tuple(c for c in COLUNAS_PREPARO
                              if c not in _JA_NA_FICHA_TECNICA)

# Sem preparo nenhum o quadro INTEIRO não entra — ver ``_acessorios_e_preparo``.
# Já se tentou mantê-lo com a linha "Sem preparo específico" dentro, pelo medo de
# um quadro vazio se ler como falha de impressão. No papel ficou pior: a moldura,
# a divisória e a coluna de valores vazia continuavam lá, e o caso SEM preparo é
# a maioria. Quadro que não existe não se lê como falha; quadro vazio, sim.


def preparo_que_se_aplica(setups: list) -> tuple:
    """As linhas de preparo com valor em ALGUM setup.

    A contracapa imprimia as cinco sempre, e as que não se aplicam saíam "N/A":
    cinco linhas para dizer, em geral, uma coisa. Quem monta o paciente lê o que
    tem de fazer, e "N/A" não é instrução — é ruído entre as que são.

    Basta valer para UM dos posicionamentos: com dois setups lado a lado, sumir
    com a linha porque um deles não usa deixaria o outro sem a instrução dele.
    """
    return tuple(
        col for col in PREPARO_NA_CONTRACAPA
        if any(str((s.preparo or {}).get(col) or "").strip() not in ("", VAZIO)
               for s in setups))

# ── Checklist Pré-Tratamento ─────────────────────────────────────────────────
# Morava na pág. 2 da Ficha Técnica. Mudou-se INTEIRO para cá — itens, colunas de
# marcação e legenda —, junto com a conferência a que ele pertence: quem confere
# a montagem tem a contracapa na mão, e o carimbo da equipe já é desta folha.
CHECKLIST_ITENS = (
    "Nome, D.N, RGH, Foto",
    "Prescrição Médica (capa x ficha)",
    "Contra-Capa Completa",
    "Exames Complementares",
    "Acessórios Presentes",
    "Lateralidade e Anatomia",
)
CHECKLIST_COLUNAS = ("C", "N/C", "N/A", "Cor.")
CHECKLIST_LEGENDA = ("C: conforme    N/C: não conforme    "
                     "N/A: não se aplica    Cor.: corrigido")
_LARG_COL_CHK = 34.0
_ALT_LINHA_CHK = 13.5


def _pagina2(f: _Folha, capa: Capa) -> None:
    """Folha de posicionamento: até três montagens, cada uma com as suas fotos.

    Não dá para fundir duas montagens numa linha só: no TC7 o setup de fêmur põe
    os braços sobre o tórax e o de tórax não, e uma capa que diga só um dos dois
    manda montar errado metade das sessões. Cada bloco (fotos, acessórios,
    preparo) se reparte por posicionamento — ver ``ARRANJO_FOTOS``.
    """
    y_cabecalho = _cabecalho(f, capa, _TOPO_P2, completo=False)

    x0, x1 = 16.2, 579.3
    setups = capa.setups_impressos() or [capa_dados.Setup()]

    # De cima para baixo: o que se monta (fotos, acessórios, preparo), o que se
    # confere (checklist) e o que se assina (exames, carimbo). Cada bloco diz
    # onde termina, e o seguinte começa daí — a faixa de fotos tem altura
    # variável, então nada abaixo dela pode estar em posição fixa.
    y = _fotos_p2(f, setups, x0, x1, y_cabecalho + _GAP_CABECALHO_P2)
    y = _acessorios_e_preparo(f, setups, x0, x1, y + _GAP_P2)
    y = _checklist_p2(f, x0, x1, y + _GAP_P2)
    y = _exames(f, y + _GAP_P2)
    _carimbo(f, y + _GAP_P2)


# Arranjo da faixa de fotos por nº de posicionamentos:
#   nº de setups → (lado a lado?, colunas de foto por setup, linhas por setup)
#
# Um posicionamento pede uma tira de três (frente, lado, detalhe do acessório —
# ver ``posicionamento.MAX_FOTOS``). Dois pedem uma tira dessas para cada, uma
# sobre a outra, porque o que se compara é setup contra setup — e empilhados,
# não em colunas: a foto mantém a largura de ~186 pt nos dois casos, que é o
# mínimo em que a montagem ainda se confere.
ARRANJO_FOTOS: dict[int, tuple[bool, int, int]] = {
    1: (False, 3, 1),
    2: (False, 3, 1),
}
# Teto da altura de um quadro: sem ele, um posicionamento só esticaria a foto
# até o pé da folha e empurraria o resto para fora. Generoso de propósito — uma
# foto em pé (o paciente de corpo inteiro) fica minúscula num quadro deitado.
_ALT_CELA_MAX = 190.0
_ALT_ROTULO_SETUP = 14.0    # tarja com o nome do posicionamento
_ALT_LEGENDA_FOTO = 12.0    # tarja de legenda no pé de cada quadro
_GAP_CELA = 2.0


def arranjo_fotos(n_setups: int) -> tuple[bool, int, int]:
    """O arranjo de ``ARRANJO_FOTOS`` para ``n_setups``, aparado ao que cabe."""
    return ARRANJO_FOTOS[min(max(int(n_setups or 1), 1), MAX_SETUPS)]


def fotos_impressas(n_setups: int) -> int:
    """Quadros de foto que a folha 2 tem para CADA posicionamento.

    A tela pergunta para poder avisar quando uma foto não vai sair impressa —
    descobrir isso depois de a folha estar na sala custa a viagem de volta.
    """
    _lado, colunas, linhas = arranjo_fotos(n_setups)
    return colunas * linhas


def _quadro_de_foto(f: _Folha, img, x0: float, y0: float, x1: float, y1: float,
                    n: int) -> None:
    """Uma foto de posicionamento com a sua legenda no pé.

    A tarja traz o número do quadro e deixa o resto da linha em branco: as fotos
    não vêm com descrição nenhuma (são arquivos soltos da pasta do paciente), e
    quem monta precisa poder escrever o que é cada uma — "isocentro", "tatuagem
    lateral D", "altura do braço". Numerar sozinho já resolve metade: dá para
    dizer "confira a 3" sem apontar para o papel.
    """
    y_leg = y1 - _ALT_LEGENDA_FOTO
    with f.bloco(x0, y0, x1, y1, raio=3.0):
        f.imagem(img, x0 + 1, y0 + 1, x1 - 1, y_leg - 1)
        f.caixa(x0, y_leg, x1, y1, CINZA)
        f.linha(x0, y_leg, x1, y_leg)
    f.txt(x0 + 3.5, y_leg + 2.6, f"FOTO {n}", FONTE_B, 7.0)


def _grade_de_fotos(f: _Folha, setup, x0: float, y0: float, x1: float,
                    colunas: int, linhas: int, alt_cela: float) -> None:
    """Os quadros de UM posicionamento, numa grade ``colunas`` × ``linhas``."""
    larg = (x1 - x0) / colunas
    fotos = list(getattr(setup, "fotos", []) or [])
    cabem = colunas * linhas
    # Só os quadros que TÊM foto, e CENTRADOS na faixa (pedido do usuário em
    # 25/08/2026). A grade fixa de três desenhava dois retângulos vazios ao
    # lado da única foto do paciente, e quadro vazio no papel é uma pergunta:
    # quem confere na sala procura a foto que falta, ou anota nele achando que
    # devia haver algo. Nada ali é a resposta certa — não havia foto nenhuma.
    #
    # A LARGURA do quadro não muda: é ela que mantém a foto do mesmo tamanho
    # em todos os posicionamentos, e é comparando setup contra setup que a
    # montagem se confere. Esticar uma foto só até a margem daria um retrato
    # gigante ao lado de uma tira de três na montagem vizinha.
    #
    # SEM foto nenhuma a tira de três CONTINUA inteira, e não é exceção
    # esquecida: a capa em branco é impressa de propósito para ser preenchida à
    # mão (ver ``test_capa_vazia_nao_quebra``), e aí os três quadros são o
    # espaço reservado para as fotos que ainda vão ser coladas. Colapsá-la para
    # um quadro tiraria esse espaço de quem imprime antes de ter as fotos.
    n = cabem if not fotos else min(len(fotos), cabem)
    for i in range(n):
        lin, col = divmod(i, colunas)
        # Quantos quadros esta LINHA tem: a última pode ficar incompleta, e
        # centrá-la pela contagem total a jogaria para fora do meio.
        nesta_linha = min(colunas, n - lin * colunas)
        recuo = (larg * (colunas - nesta_linha)) / 2
        cx = x0 + recuo + col * larg
        cy = y0 + lin * (alt_cela + _ALT_LEGENDA_FOTO + _GAP_CELA)
        _quadro_de_foto(f, fotos[i] if i < len(fotos) else None,
                        cx + _GAP_CELA / 2, cy,
                        cx + larg - _GAP_CELA / 2,
                        cy + alt_cela + _ALT_LEGENDA_FOTO, i + 1)


def _rotulo_de_setup(f: _Folha, setup, i: int, x0: float, y0: float,
                     x1: float) -> None:
    f.caixa(x0, y0, x1, y0 + _ALT_ROTULO_SETUP, CINZA)
    f.linha(x0, y0, x1, y0)
    f.txt_centro(x0, x1, y0 + 2.6,
                 (getattr(setup, "nome", "") or f"Setup {i + 1}").upper(),
                 FONTE_B, 8.5)


def _fotos_p2(f: _Folha, setups: list, x0: float, x1: float,
              y0: float) -> float:
    """Faixa de fotos de posicionamento. Devolve o y do fim dela.

    A altura sai do arranjo (ver ``ARRANJO_FOTOS``) e nunca passa de
    ``_ALT_MAX_FOTOS``; com um posicionamento só, a faixa fica bem mais curta e
    devolve a folha para os blocos de baixo.
    """
    n = len(setups)
    lado_a_lado, colunas, linhas = arranjo_fotos(n)
    h_rot = _ALT_ROTULO_SETUP if n > 1 else 0.0
    y_cab = y0 + _ALT_CAB_P2

    # Altura de um quadro, a partir do que a faixa pode gastar.
    util = _ALT_MAX_FOTOS - _ALT_CAB_P2
    bloco = (util - h_rot) / linhas if lado_a_lado else (util / n - h_rot) / linhas
    alt_cela = min(bloco - _ALT_LEGENDA_FOTO - _GAP_CELA, _ALT_CELA_MAX)
    alt_grade = linhas * (alt_cela + _ALT_LEGENDA_FOTO + _GAP_CELA)
    y1 = y_cab + (h_rot + alt_grade if lado_a_lado
                  else n * (h_rot + alt_grade))

    with f.bloco(x0, y0, x1, y1):
        f.caixa(x0, y0, x1, y_cab, CINZA)
        f.txt(x0 + 1.0, y0 + 3.5, "FOTOS DE POSICIONAMENTO", FONTE_B, 10.0)
        f.linha(x0, y_cab, x1, y_cab)
        for i, s in enumerate(setups):
            if lado_a_lado:
                larg = (x1 - x0) / n
                sx0, sx1, sy = x0 + i * larg, x0 + (i + 1) * larg, y_cab
                if i:
                    f.linha(sx0, y_cab, sx0, y1)
            else:
                sx0, sx1 = x0, x1
                sy = y_cab + i * (h_rot + alt_grade)
            if n > 1:
                _rotulo_de_setup(f, s, i, sx0, sy, sx1)
            _grade_de_fotos(f, s, sx0, sy + h_rot, sx1, colunas, linhas,
                            alt_cela)
        f.grade(x0, y0, x1, y1)
    return y1


# Largura do quadro de Preparo por nº de posicionamentos; o de Acessórios fica
# com o resto da faixa. O preparo cresce porque ganha uma coluna de valores a
# cada montagem, e "Acima da Cabeça" precisa caber sem virar letra de bula. Os
# acessórios é que cedem: são texto corrido, que o ``txt_ajustado`` acomoda.
_LARG_PREPARO = {1: 245.0, 2: 268.0, 3: 276.0}
_GAP_MONTAGEM = 4.0


def _linhas_que_cabem(y_itens: float) -> int:
    """Quantas linhas o quadro da montagem pode ter sem empurrar o carimbo.

    Conta de trás para frente, do pé da folha: carimbo, exames e checklist têm
    altura conhecida; o que sobrar acima deles é do quadro.
    """
    alt_checklist = _ALT_CAB_P2 + (len(CHECKLIST_ITENS) + 1) * _ALT_LINHA_CHK
    fim = (_Y_PE_FOLHA - _ALT_CARIMBO - _GAP_P2 - _ALT_EXAMES - _GAP_P2
           - alt_checklist - _GAP_P2)
    return max(int((fim - y_itens - 4.0) // _ALTURA_LINHA), 1)


def _acessorios_e_preparo(f: _Folha, setups: list, x0: float, x1: float,
                          y0: float) -> float:
    """Os dois quadros da montagem, lado a lado. Devolve o y do fim.

    Eram duas faixas empilhadas de folha inteira — o preparo como uma tabela de
    seis colunas atravessando a página. Lado a lado economizam a altura que o
    Checklist veio ocupar, e cada um passa a ser lido como um quadro só: "o que
    vai na mesa" à esquerda, "como o paciente chega" à direita.
    """
    y_cab = y0 + _ALT_CAB_P2
    # Com dois setups, uma linha a mais nomeia cada coluna nos DOIS quadros — sem
    # ela, "Cheia | Vazia" não diz de qual montagem é cada uma.
    y_itens = y_cab + (_ALTURA_LINHA if len(setups) > 1 else 0.0)
    # A altura é a do quadro mais alto: o preparo tem nº fixo de linhas; os
    # acessórios, os que o dosimetrista escreveu.
    n_acess = max((len(_linhas(s.acessorios)) for s in setups), default=0)
    # O preparo deixou de ter nº FIXO de linhas: só entram as que se aplicam
    # (ver ``preparo_que_se_aplica``). Contar as cinco aqui reservaria altura
    # para linhas que não vão ser desenhadas, e o quadro sairia com um vão.
    colunas = preparo_que_se_aplica(setups)
    linhas_max = max(len(colunas), n_acess, 1)
    # TETO, calculado a partir do que sobra na folha — não um número fixo.
    # Sem teto o quadro crescia com o texto até empurrar o carimbo para fora do
    # papel, e o carimbo termina num y FIXO: "fora da folha" virava um retângulo
    # de altura negativa por cima do rodapé.
    #
    # O que sobra depende do número de posicionamentos (a faixa de fotos come o
    # dobro com dois), então um número fixo ou desperdiçava página com um setup
    # ou estourava com dois. A lista de acessórios é o único bloco de tamanho
    # livre daqui para baixo, então é ela que se ajusta — e o que não couber sai
    # CONTADO no pé do quadro (ver ``_acessorios_p2``), nunca calado.
    linhas_max = min(linhas_max, _linhas_que_cabem(y_itens))
    y1 = y_itens + 4.0 + linhas_max * _ALTURA_LINHA
    # Sem NENHUMA linha de preparo o quadro não entra, e os Acessórios ocupam a
    # faixa inteira. Antes ele saía com a divisória no lugar, a coluna de
    # valores vazia e um "Sem preparo específico" preso no canto — meia folha
    # de moldura para dizer que não há o que dizer. Preparo é exceção: a maioria
    # dos casos não tem nenhum, e era essa maioria que ganhava o quadro feio.
    if not colunas:
        _acessorios_p2(f, setups, x0, x1, y0, y_cab, y_itens, y1, linhas_max)
        return y1
    meio = x1 - _LARG_PREPARO[min(max(len(setups), 1), MAX_SETUPS)]
    _acessorios_p2(f, setups, x0, meio - _GAP_MONTAGEM, y0, y_cab, y_itens, y1,
                   linhas_max)
    _preparo_p2(f, setups, meio, x1, y0, y_cab, y_itens, y1)
    return y1


def _acessorios_p2(f: _Folha, setups: list, x0: float, x1: float,
                   y0: float, y_cab: float, y_itens: float, y1: float,
                   cabem: int) -> None:
    """Só o que o dosimetrista escreveu no campo Acessórios, um por linha.

    Com dois setups, uma coluna para cada — o de fêmur e o de tórax não usam os
    mesmos apoios, e uma lista fundida manda montar errado metade das sessões.
    """
    n = len(setups)
    col = (x1 - x0) / n
    with f.bloco(x0, y0, x1, y1):
        f.caixa(x0, y0, x1, y_cab, CINZA)
        f.txt(x0 + 1.0, y0 + 3.5, "ACESSÓRIOS", FONTE_B, 10.0)
        f.grade(x0, y0, x1, y1, horizontais=(y_cab,))
        # As divisórias começam ABAIXO do título: ele é uma célula só,
        # atravessando o quadro.
        for i in range(1, n):
            f.linha(x0 + i * col, y_cab, x0 + i * col, y1)
        for i, s in enumerate(setups):
            xa = x0 + i * col + 2.0
            larg = col - 5.0
            if n > 1:
                f.txt_ajustado(xa, y_cab + 2.5,
                               (s.nome or f"Setup {i + 1}").upper(), larg,
                               FONTE_B, 7.5)
            # ``cabem`` vem de quem dimensionou o quadro — derivar de ``y1``
            # com margem fixa errava por uma linha e cortava acessório que
            # cabia.
            linhas = _linhas(s.acessorios)
            vagas = cabem
            sobra = len(linhas) - vagas
            if sobra > 0:
                # Uma linha é gasta com o aviso, para o "+N" não empurrar o
                # último acessório para fora sem dizer nada.
                vagas -= 1
                sobra += 1
            for j, linha in enumerate(linhas[:vagas]):
                y = y_itens + 3.0 + j * _ALTURA_LINHA
                # Mesma fonte e corpo dos valores do quadro de Preparo, ao lado:
                # os dois se leem juntos, e dois pesos diferentes faziam a lista
                # de acessórios parecer mais importante do que o preparo.
                f.txt_ajustado(xa, y, linha, larg, FONTE, 8.5)
            if sobra > 0:
                f.txt_ajustado(xa, y_itens + 3.0 + vagas * _ALTURA_LINHA,
                               f"⚠ mais {sobra} acessório(s) — veja no sistema",
                               larg, FONTE_B, 8.0)


def _preparo_p2(f: _Folha, setups: list, x0: float, x1: float,
                y0: float, y_cab: float, y_itens: float, y1: float) -> float:
    """Bexiga / reto / gantry / braços / jejum como QUADRO: um item por linha.

    Vale mais como lista do que como tabela larga: são cinco instruções curtas,
    e quem monta lê uma de cada vez. Sem o DECÚBITO, que a Ficha Técnica já traz
    (ver ``PREPARO_NA_CONTRACAPA``). O âmbar continua marcando só o preparo que
    exige alguém fazer alguma coisa antes de deitar o paciente.
    """
    x_val = x0 + 96.0                     # onde começa a coluna de valores
    largs = [x1 - x_val] if len(setups) == 1 else \
        [(x1 - x_val) / len(setups)] * len(setups)
    with f.bloco(x0, y0, x1, y1):
        f.caixa(x0, y0, x1, y_cab, CINZA)
        f.txt(x0 + 1.0, y0 + 3.5, "PREPARO", FONTE_B, 10.0)
        f.grade(x0, y0, x1, y1, horizontais=(y_cab,))
        if len(setups) > 1:
            xa = x_val
            for i, (s, larg) in enumerate(zip(setups, largs)):
                f.txt_centro(xa, xa + larg, y_cab + 2.5,
                             (s.nome or f"Setup {i + 1}").upper(), FONTE_B, 7.5)
                xa += larg
        colunas = preparo_que_se_aplica(setups)
        for i, col in enumerate(colunas):
            ya = y_itens + 4.0 + i * _ALTURA_LINHA
            f.txt(x0 + 3.0, ya + 1.0, col, FONTE_B, 8.0)
            xa = x_val
            for s, larg in zip(setups, largs):
                valor = s.preparo.get(col) or VAZIO
                if _destacar(col, valor):
                    # Tarja recuada da borda: encostada nela, lia-se como se a
                    # célula tivesse vazado para fora do quadro.
                    f.caixa(xa, ya - 0.5, min(xa + larg, x1 - 2.0),
                            ya + _ALTURA_LINHA - 1.5, AMBAR)
                f.txt_centro(xa, xa + larg, ya + 1.0, valor, FONTE, 8.5)
                xa += larg
        f.linha(x_val - 3.0, y_cab, x_val - 3.0, y1)
    return y1


def _checklist_p2(f: _Folha, x0: float, x1: float, y0: float) -> float:
    """Checklist Pré-Tratamento — o que era a tabela da pág. 2 da Ficha Técnica.

    A tabela ocupa a esquerda e a legenda das colunas fica à direita, no vão que
    sobra: são quatro colunas estreitas de marcação, e esticá-las até a margem
    só deixaria um retângulo vazio grande demais para marcar um X dentro.
    """
    y_cab = y0 + _ALT_CAB_P2
    y1 = y_cab + (len(CHECKLIST_ITENS) + 1) * _ALT_LINHA_CHK
    x_marca = x1 - len(CHECKLIST_COLUNAS) * _LARG_COL_CHK
    with f.bloco(x0, y0, x1, y1):
        f.caixa(x0, y0, x1, y_cab, CINZA)
        f.txt(x0 + 1.0, y0 + 3.5, "CHECKLIST PRÉ-TRATAMENTO", FONTE_B, 10.0)
        f.txt_direita(x1 - 4.0, y0 + 5.0, CHECKLIST_LEGENDA, FONTE, 7.0)
        # Cabeçalho das colunas de marcação.
        for j, cab in enumerate(CHECKLIST_COLUNAS):
            xa = x_marca + j * _LARG_COL_CHK
            f.caixa(xa, y_cab, xa + _LARG_COL_CHK, y_cab + _ALT_LINHA_CHK, TEAL)
            f.txt_centro(xa, xa + _LARG_COL_CHK, y_cab + 2.6, cab, FONTE_B,
                         8.5, white)
        for i, item in enumerate(CHECKLIST_ITENS):
            ya = y_cab + (i + 1) * _ALT_LINHA_CHK
            f.txt(x0 + 4.0, ya + 2.8, item, FONTE, 8.5)
        f.grade(x0, y0, x1, y1,
                horizontais=[y_cab + k * _ALT_LINHA_CHK
                             for k in range(len(CHECKLIST_ITENS) + 1)])
        # As réguas das colunas de marcação começam ABAIXO do título: subindo
        # até lá, elas riscavam a legenda no meio das palavras.
        for j in range(len(CHECKLIST_COLUNAS)):
            f.linha(x_marca + j * _LARG_COL_CHK, y_cab,
                    x_marca + j * _LARG_COL_CHK, y1)
    return y1


def _destacar(coluna: str, valor: str) -> bool:
    """A célula vai de âmbar? Só o preparo que muda o que se faz com o paciente.

    Bexiga cheia, reto vazio e braço elevado são instruções que alguém tem de
    executar antes de deitar o paciente — daí o destaque. Decúbito, gantry e
    jejum descrevem o setup e ficam brancos mesmo preenchidos, como no modelo.
    """
    v = str(valor or "").strip()
    return coluna in PREPARO_DESTACADO and v != "" and v.upper() != VAZIO


def _exames(f: _Folha, y0: float = 662.6) -> float:
    """Devolução de exames complementares. Impressa em branco, para preencher.

    ``y0`` varia porque o preparo cresce com o número de setups.
    """
    bordas = (16.2, 149.9, 258.5, 366.9, 470.8, 579.3)
    y_cab, y1 = y0 + 18.0, y0 + _ALT_EXAMES
    rotulos = (("EXAMES COMPLEMENTARES?", 8.0), ("QUANTIDADE", 10.0),
               ("DEVOLVIDO POR", 10.0), ("DATA", 10.0),
               ("ASSINATURA PACIENTE", 8.0))
    with f.bloco(16.2, y0, 579.3, y1):
        f.caixa(16.2, y0, 579.3, y_cab, CINZA)
        for i, (rotulo, tam) in enumerate(rotulos):
            f.txt_centro(bordas[i], bordas[i + 1],
                         y0 + 4.5 + (10.0 - tam) * 0.55, rotulo, FONTE_B, tam)
        f.grade(16.2, y0, 579.3, y1, verticais=bordas[1:-1],
                horizontais=(y_cab,))
    return y1


def _carimbo(f: _Folha, y0: float = 697.8) -> None:
    """Caixa do carimbo da equipe técnica.

    O carimbo é o que cede espaço quando o preparo cresce: ele sempre termina no
    pé da folha, e o que muda é a altura.

    A linha "Ficha confeccionada em … por …" que vinha logo abaixo saiu: a data
    virou o rodapé "Impresso em …", miúdo e nas DUAS folhas (ver ``rodape``).
    """
    # Altura FIXA, e não "o que sobrar até o pé da folha". Absorvendo a sobra,
    # a caixa saía com 190 pt num caso de um posicionamento — um vazio que era
    # o maior elemento da contracapa. O que ela precisa é do carimbo e de uma
    # assinatura; o resto do papel rende mais nos acessórios, que é texto que
    # alguém escreveu.
    # Encostado no PÉ DA FOLHA, sempre: uma caixa de assinatura flutuando no
    # meio da página, com branco embaixo, lê-se como erro de impressão.
    y0 = max(y0, _Y_PE_FOLHA - _ALT_CARIMBO)
    y1 = _Y_PE_FOLHA
    # Piso de segurança: se algum dia um bloco de cima crescer além do previsto,
    # o carimbo sai apertado em vez de sair INVERTIDO — este bloco desenha de
    # y0 até y1, e y0 > y1 vira um retângulo de altura negativa sobre o rodapé.
    y0 = min(y0, y1 - _ALT_MIN_CARIMBO)
    y_cab = y0 + 18.0
    with f.bloco(16.2, y0, 579.3, y1):
        f.caixa(16.2, y0, 579.3, y_cab, CINZA)
        f.txt(17.2, y0 + 0.9, "CARIMBO E ASSINATURA DA EQUIPE TÉCNICA",
              FONTE_B, 9.0)
        f.grade(16.2, y0, 579.3, y1, horizontais=(y_cab,))


# ── API ──────────────────────────────────────────────────────────────────────

def gerar(capa: Capa) -> bytes:
    """PDF de duas páginas da capa, pronto para visualizar ou imprimir."""
    buf = io.BytesIO()
    c = rodape.em_todas(canvas.Canvas(buf, pagesize=A4))
    c.setTitle(f"Capa de Tratamento — {capa.nome}".strip(" —"))
    f = _Folha(c)
    _pagina1(f, capa)
    c.showPage()
    _pagina2(f, capa)
    c.showPage()
    c.save()
    return buf.getvalue()
