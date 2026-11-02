"""Uma grafia só para o nome de uma pessoa, valha ela de onde valer.

O mesmo paciente chega ao app por três portas — o DICOM do TPS, o data warehouse
e os relatórios exportados — e cada uma grafa do seu jeito: "SANDRA CABRAL DA
LUZ", "Luz, Sandra Cabral da", "Sandra Cabral Da Luz". Antes deste módulo, a
grafia que aparecia na tela era a da porta por onde o nome entrou, e numa lista
de dez linhas conviviam as três. Isso não é feiúra: caixa alta ao lado de caixa
mista é lida como dado de origens diferentes — e é justamente a origem que não
deve transparecer para quem confere a ficha.

Daqui em diante o nome é formatado **na entrada** (para nascer canônico) e **na
leitura do que já está gravado** (para as fichas antigas não destoarem). O que
sai na tela é o que sai no papel.

Módulo sem dependência nenhuma, de propósito: ``dicom_rt`` precisa da regra e
não pode passar a depender de ``capa_dados``, que lê CSV e importa o DICOM de
volta.

Isto vale para nome de GENTE. Login de estação e nome de setor ("RPA103",
"Clinica Física") copiam a grafia como está — ver a tabela de radioterapeutas em
``tratamento_db``.
"""
from __future__ import annotations


def desinverter(nome: str) -> str:
    """``"Souza, Antonio Carlos de"`` → ``"Antonio Carlos de Souza"``.

    O relatório exporta sobrenome primeiro; a capa imprime o nome como se fala.
    Sem vírgula, devolve como veio.
    """
    s = str(nome or "").strip()
    if "," not in s:
        return s
    fam, resto = s.split(",", 1)
    return f"{resto.strip()} {fam.strip()}".strip()


# Palavras que ficam MINÚSCULAS no meio de um nome próprio. É a regra do
# português, e ignorá-la produz "Neuza Tavares De Abreu" — que ninguém escreve.
# ``e`` entra por "Maria e Silva"; ``y`` e ``van`` por nomes estrangeiros que o
# cadastro tem.
_CONECTIVOS = {"de", "da", "do", "das", "dos", "e", "di", "du", "del",
               "della", "van", "von", "y", "dello", "la", "le"}


def como_nome_proprio(texto: str) -> str:
    """``"NEUZA TAVARES DE ABREU"`` → ``"Neuza Tavares de Abreu"``.

    O cadastro do serviço tem nome em caixa alta, em caixa baixa e misturado —
    o mesmo relatório traz "CARMEN CRISTINA NACIFE DE SA" ao lado de "Francisco
    Job do Nascimento". Numa lista, essa mistura é lida como se fossem dados de
    origens diferentes, e caixa alta ainda ocupa mais largura para dizer o
    mesmo.

    O conectivo só é rebaixado no MEIO: "Da Silva Júnior" começando o nome
    continua "Da". E a partícula colada por hífen ou apóstrofo é capitalizada
    dos dois lados ("D'Almeida", "Silva-Neto"), porque ali ela não é conectivo.
    """
    partes = str(texto or "").split()
    fora = []
    for i, palavra in enumerate(partes):
        baixa = palavra.lower()
        if i and baixa in _CONECTIVOS:
            fora.append(baixa)
            continue
        fora.append(_capitalizar_pedacos(baixa))
    return " ".join(fora)


def _capitalizar_pedacos(palavra: str) -> str:
    """Capitaliza também depois de hífen e apóstrofo. ``str.title`` não serve:
    ele quebra em qualquer não-letra e devolve "D'Almeida" como "D'Almeida" mas
    "Joao'S" para outros casos, além de estragar iniciais."""
    fora = palavra
    for sep in ("-", "'", "’"):
        fora = sep.join(p[:1].upper() + p[1:] for p in fora.split(sep))
    return fora[:1].upper() + fora[1:]


def de_pessoa(nome: str) -> str:
    """A forma canônica: desinverte (se vier "Família, Nome") e grafa próprio.

    É esta que as FONTES chamam — o banco e os relatórios exportam invertido, o
    DICOM não. Chamar as duas em ordem em cada fonte funcionava, mas era o tipo
    de par que se esquece de repetir na fonte seguinte.
    """
    return como_nome_proprio(desinverter(nome))
