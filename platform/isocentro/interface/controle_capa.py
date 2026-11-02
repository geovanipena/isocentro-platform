"""A aba Capa e o cadastro da simulação: buscar, montar, gravar e imprimir.

Saiu da ``JanelaPrincipal`` em 16/09/2026 (R-06, corte 5 do
``docs/PROPOSTA_GUI.md``). A capa não sai do DICOM: sai dos relatórios (e do
banco, pelo ``capa_dados``). A tela (``capa.PainelCapa``) só mostra e deixa
corrigir; quem sabe qual paciente está na bancada e vai buscá-lo é este
controle, com a janela ao lado.

**A capa vai para o papel**, grampeada na ficha. A mudança foi só de endereço:
os textos, a ordem das buscas e as travas contra misturar pacientes são os da
janela.

Lê o caso NA JANELA, na hora (``janela.form``, ``janela.caso.pasta_carregada``,
``janela.caso.dados``), pelo mesmo motivo do ``PortaoDaFicha``: a carga reatribui, e
uma cópia guardada aqui responderia pelo paciente anterior.

O que continua na janela, e por quê:

- ``_sincronizar_bancada``: é FLUXO — carrega a pasta na bancada, e a Ficha
  Virtual também a chama. O ``_sync_recusado`` que ela guarda é da janela
  (decidido no corte 3).
- ``_capa_mudou``: descarta a PRÉVIA da ficha e derruba ``_previa_ok``, que são
  da bancada. Daqui ela só chama ``descartar_pdf``.
- ``com_capa`` e ``capa_para_ficha``: são a montagem da ficha
  (``ControleFicha``, corte 6c), e
  consultam ``ja_montada``/``buscar`` daqui.

``pacientes_carregados`` é PÚBLICO: a aba Serviço das Configurações o derruba
quando o admin troca a pasta ou o servidor. Era ``janela._pacientes_carregados``
lido por ``hasattr`` — e com o atributo mudando de dono o ``hasattr`` daria
falso, e a lista velha ficaria na busca pelo resto do dia, sem erro nenhum.

Os endereços antigos (``gui.JanelaPrincipal._capa_buscar``…) **não** foram
mantidos, pela mesma razão dos cortes 3 e 4.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from isocentro.banco import capa_dados
from isocentro.dados import historico
from isocentro.dados import inventario
from isocentro.dominio import constantes
from isocentro.interface import capa as capa_tela
from isocentro.interface import simulacao
from isocentro.interface import ui
from isocentro.papel import capa_pdf

_LOG = logging.getLogger(__name__)

# Quanto a Capa espera, depois de a seleção parar num paciente, antes de ler os
# relatórios dele. Ler custa ~0,4 s; sem a espera, cada tecla de seta na lista
# montaria uma capa inteira. Curto o bastante para não parecer travamento.
_ESPERA_BUSCA_CAPA = 260   # ms


class ControleCapa:
    """Busca, montagem e saída da capa. A janela o constrói e liga os sinais."""

    def __init__(self, janela):
        # A janela é o PAI dos pop-ups e a dona do estado do caso (ver a
        # docstring do módulo para o porquê de não copiar nada dela aqui).
        self.janela = janela
        self.capa = janela.capa
        # Ler treze mil pacientes custa quase um segundo; só na 1ª abertura.
        self.pacientes_carregados = False
        self._refs_pacientes: list = []
        self._buscando = False   # guarda de reentrância (ver ``buscar``)
        # Pediram a capa de quem veio da tomografia (ver ``confeccionar``):
        # a tela não volta ao modo Simulação enquanto este paciente estiver nela.
        self._completa_pedida = False
        # Espera entre parar num paciente da lista e ler os relatórios dele.
        # Filho da JANELA, não deste objeto (que não é QObject): morre com ela.
        self._timer_busca = QTimer(janela)
        self._timer_busca.setSingleShot(True)
        self._timer_busca.timeout.connect(self.buscar_o_escolhido)
        # A raiz das simulações e a pasta dos relatórios NÃO são mais lidas do
        # QSettings: elas vêm da configuração do serviço, resolvidas dentro de
        # ``simulacao.raiz()`` e ``capa_dados.pasta_dados()``. Ler daqui era o
        # que fazia a escolha do admin valer só na máquina em que foi feita.

        # PDF da capa já elaborado e guardado em disco (ver ``pdf_atual``).
        self._caminho: Optional[str] = None

    def ao_abrir(self) -> None:
        # Sem caso na bancada, a Capa é a porta de quem chega da TOMOGRAFIA: a
        # busca de paciente aparece e o posicionamento é o que se preenche.
        if not self.janela._estado_fichinha_tem_ficha() and not self._completa_pedida:
            # Sem caso na bancada, quem está na tela veio da TOMOGRAFIA: curso
            # e prescrições não existem ainda e só atrapalhariam.
            #
            # ``_completa_pedida`` é a exceção: quem cadastrou a simulação
            # e pediu a capa não pode perdê-la ao ir à bancada conferir um campo
            # e voltar — curso e prescrições sumiriam da tela junto com o botão
            # de impressão, e o trabalho pareceria desfeito.
            self.capa.definir_modo(capa_tela.SIMULACAO)
            # ``mostrar_busca`` e separado do carregamento: a lista so e lida
            # uma vez por sessao, e sem isto voltar a Capa depois de limpar a
            # bancada deixava o fluxo da TC sem como escolher paciente.
            self.capa.mostrar_busca()
            if self.carregar_lista_pacientes():
                self.capa.mostrar_status(
                    "Escolha o paciente e arraste as fotos do posicionamento.")
            return
        self.capa.esconder_busca()
        self.capa.definir_modo(capa_tela.COMPLETA)
        return self.do_caso()

    def carregar_lista_pacientes(self) -> bool:
        """Lista para a busca da Capa — uma vez por sessao (13 mil nomes).

        Devolve se ha lista utilizavel; ``False`` deixa na tela o recado de
        como resolver, que nao pode ser sobrescrito pelo convite generico.
        """
        if self.pacientes_carregados:
            return True
        self.capa.mostrar_status("Lendo a lista de pacientes…")
        QApplication.processEvents()
        try:
            refs = capa_dados.pacientes()
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Capa: falha ao listar pacientes")
            refs = []
            self.capa.mostrar_status(
                f"Não consegui ler a lista de pacientes: {exc}", erro=True)
        self.capa.definir_pacientes(refs)
        # Guardada aqui, e não só dentro da Capa: a aba Ficha Virtual busca na
        # MESMA lista, e ir buscá-la no atributo privado de outra tela é o tipo
        # de acoplamento que quebra calado quando aquela tela muda.
        self._refs_pacientes = refs
        self.pacientes_carregados = bool(refs)
        if not refs:
            # O recado depende de quem está na frente: o botão "Relatórios" só
            # aparece para admin (ver ``permitir_escolher_pastas``). Mandar a
            # técnica apertá-lo era mandá-la procurar o que não está na tela.
            # O botão "Relatórios" desta tela não existe mais: os endereços
            # foram para Configurações → Serviço. Mandar apertar um botão que
            # não está lá é pior que não dizer nada.
            saida = ("Aponte em Configurações → Serviço."
                     if self.capa.pode_apontar_pastas()
                     else "Peça ao administrador para apontar o sistema em "
                          "Configurações → Serviço.")
            # O caminho procurado E a origem dele: "não encontrados" sem dizer
            # ONDE se procurou não dá a ninguém como resolver.
            self.capa.mostrar_status(
                f"Nenhum paciente na lista — os relatórios não estão em "
                f"{capa_dados.pasta_dados()} ({capa_dados.origem_da_pasta()}). "
                f"{saida}", erro=True)
        return bool(refs)

    def do_caso(self) -> None:
        """Entrada na tela Capa: busca o paciente na primeira vez que aparece.

        Nas vezes seguintes o que está na tela é preservado — quem já corrigiu
        o convênio à mão não quer perder a correção só por ter ido à bancada
        conferir um campo. Para buscar de novo existe o botão.
        """
        self.capa.definir_pasta(self.janela.caso.pasta_carregada or "")
        if self.ja_montada():
            self.capa.mostrar_status(
                f"Capa de {self.janela.form.pac_nome.text().strip()} — confira e siga "
                "para a Visualização.")
            return
        self.buscar()

    def ja_montada(self) -> bool:
        """A tela já tem a capa DESTE paciente?

        Compara pelo registro, e pelo nome quando não há registro: trocar de
        paciente sem refazer a busca deixaria a capa do anterior na tela, com o
        nome novo por cima — que é exatamente o erro que a capa existe para
        evitar.
        """
        atual = self.capa.coletar()
        if not (atual.nome or atual.registro):
            return False
        # Identificar o paciente não é montar a capa dele. A busca da TC
        # preenche nome/registro e nada mais; tratá-la como pronta faz a capa
        # ser impressa sem convênio, curso, CID, médico, máquina e sem uma
        # prescrição — e a tela ainda diz "confira e siga".
        if not self.capa.montada_dos_relatorios():
            return False
        reg = self.janela.form.pac_registro.text().strip()
        if reg or atual.registro:
            return capa_dados.normalizar_id(atual.registro) == \
                capa_dados.normalizar_id(reg)
        return capa_dados.normalizar_nome(atual.nome) == \
            capa_dados.normalizar_nome(self.janela.form.pac_nome.text())

    # ── Modo Simulação ───────────────────────────────────────────────────
    # O cadastro da simulação é o PRIMEIRO elo: o dosimetrista registra o que
    # fez na tomografia, e é essa pasta que a Capa vai encontrar depois. Não
    # depende de DICOM nem de paciente carregado — quem chega aqui vem da TC,
    # antes de existir plano.

    def cadastrar_simulacao(self) -> None:
        """Grava a pasta da simulação e vincula os imobilizadores."""
        sim = self.capa.simulacao()
        sim.cadastrada_por = (self.janela._usuario or {}).get("usuario", "")
        faltas = sim.valida()
        if faltas:
            self.capa.mostrar_status(" ".join(faltas), erro=True)
            return
        try:
            pasta = simulacao.cadastrar(sim)
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Falha ao cadastrar a simulação")
            ui.alertar(self.janela, "Erro ao cadastrar a simulação", str(exc))
            return

        # O inventário só é mexido DEPOIS de a pasta gravar: falhar aqui deixaria
        # uma máscara marcada como em uso numa simulação que não existe.
        avisos = []
        codigos = [m["codigo"] for m in sim.imobilizadores if m.get("codigo")]
        if codigos:
            avisos = inventario.registrar_uso(codigos, sim.nome, sim.registro)
        historico.registrar("simulacao_cadastrada", detalhes={
            "nome": sim.nome, "registro": sim.registro,
            "setups": len(sim.setups),
            "fotos": sum(len(s.fotos) for s in sim.setups)})

        n_fotos = sum(len(s.fotos) for s in sim.setups)
        msg = (f"Simulação de {sim.nome} cadastrada — {len(sim.setups)} "
               f"posicionamento(s), {n_fotos} foto(s).")
        self.capa.mostrar_status(msg + (" " + " ".join(avisos)
                                                if avisos else ""),
                                         erro=bool(avisos))
        # Está gravado em disco: sair da tela ou montar a capa por cima não
        # perde mais nada, e não precisa de pergunta.
        self.capa.marcar_posicionamento_arquivado()
        self.capa.posicionamento.recarregar_inventario()
        # Os avisos do inventário vão DENTRO do modal: são sobre material que a
        # pessoa está levando para a sala agora, e a linha de status é apagada
        # logo em seguida por "Próximo paciente" — bastaria um Enter para a
        # advertência sumir sem ter sido lida.
        self.perguntar_abrir_simulacao(pasta, sim.nome, avisos,
                                        registro=sim.registro,
                                        nascimento=sim.nascimento)

    def perguntar_abrir_simulacao(self, pasta: str, nome: str,
                                   avisos: Optional[list] = None,
                                   registro: str = "",
                                   nascimento: str = "") -> None:
        """Oferece o passo seguinte de quem acabou de cadastrar a simulação.

        Duas saídas, porque são dois trabalhos diferentes: **abrir a pasta**
        para conferir as fotos gravadas, ou **próximo paciente** — limpar aqui,
        e não no clique seguinte, é o que faz a tela servir para uma fila em vez
        de um paciente por sessão.

        Havia uma terceira, "Confeccionar a capa", e ela era até o padrão. SAIU:
        no instante do cadastro da simulação **ainda não existe prescrição**. A
        capa aberta ali nascia sem o que a define, e o atalho que parecia
        adiantar trabalho só empurrava para a frente uma folha incompleta —
        exatamente o contrário do que a capa existe para fazer. Quem cadastrou
        a simulação chega à capa pela busca, depois, com o curso já prescrito.
        """
        ABRIR = "📂  Abrir a pasta"
        PROXIMO = "➕  Próximo paciente"
        # Os avisos do inventário sobem para o DETALHE junto com a pasta: são
        # sobre material que a pessoa está levando para a sala agora.
        detalhe = pasta
        if avisos:
            detalhe = "\n".join(f"⚠  {a}" for a in avisos) + f"\n\n{pasta}"
        alvo = ui.escolher(
            self.janela, "Simulação cadastrada", f"Simulação de {nome} cadastrada.",
            [ABRIR, PROXIMO], detalhe=detalhe,
            icone=QMessageBox.Warning if avisos else None)
        if alvo == ABRIR:
            try:
                os.startfile(pasta)
            except OSError as exc:
                self.capa.mostrar_status(
                    f"Não consegui abrir a pasta: {exc}", erro=True)
        elif alvo == PROXIMO:
            # ``limpar`` preserva a lista de pacientes já lida: reprocessar os
            # treze mil a cada paciente travaria a tela por segundos.
            self._completa_pedida = False
            self.capa.definir_modo(capa_tela.SIMULACAO)
            self.capa.limpar()
            self.capa.mostrar_busca()
            self.capa.mostrar_status("Pronto para a próxima simulação.")

    def confeccionar(self, nome: str, registro: str,
                           pasta: str = "", nascimento: str = "") -> None:
        """Da simulação cadastrada para a capa do MESMO paciente.

        Sai do modo Simulação (que esconde curso, prescrições e a impressão
        porque na tomografia eles ainda não existem) e procura o cadastro nos
        relatórios. O posicionamento que acabou de ser gravado continua na tela:
        é dele que sai a folha 2, e refazê-lo exige o paciente de volta na sala.
        """
        self._completa_pedida = True
        self.capa.definir_modo(capa_tela.COMPLETA)
        # ``nascimento`` explícito: sem ele, ``buscar`` caía no campo da
        # BANCADA, que pode ser de outro paciente — e nascimento errado numa
        # capa é erro de identificação, o que ela existe para impedir.
        self.buscar(nome=nome, registro=registro, nascimento=nascimento,
                          preservar_posicionamento=True,
                          pasta=pasta or None)

    def da_pasta(self, pasta: str) -> None:
        """Apontaram uma pasta de paciente NA CAPA — monta a capa a partir dela.

        Este é o caminho de quem chega da tomografia: a pasta do paciente na
        mão e nenhum plano calculado. A bancada não é tocada — carregar o caso
        lá custa a leitura da TC inteira e traz dose e estruturas que esta tela
        não usa; aqui basta saber DE QUEM é a pasta para procurar o cadastro nos
        relatórios.
        """
        if not pasta or not os.path.isdir(pasta):
            self.capa.mostrar_status("Pasta não encontrada.", erro=True)
            return
        self.capa.definir_pasta(pasta)
        self.capa.mostrar_status(f"Lendo {os.path.basename(pasta)}…")
        QApplication.processEvents()

        quem = capa_dados.identidade_da_pasta(pasta)
        # O posicionamento entra sempre — é o que a pasta tem de mais certo, e
        # não depende de o paciente estar nos relatórios.
        importado = self.capa.carregar_da_pasta(
            pasta, nome=quem.get("nome", ""), registro=quem.get("registro", ""))

        if not (quem.get("nome") or quem.get("registro")):
            # Pasta sem DICOM, sem ficha anterior e sem cadastro de simulação:
            # dá para seguir preenchendo à mão, mas quem procura o cadastro
            # precisa saber por que ele não veio.
            self.capa.mostrar_status(
                "Não identifiquei o paciente nesta pasta (sem DICOM, ficha "
                "anterior ou cadastro de simulação). "
                + (f"Importado: {importado.resumo()}. " if importado.achou() else "")
                + "Use a busca para escolher o paciente.", erro=True)
            self.capa.mostrar_busca()
            self.carregar_lista_pacientes()
            return

        historico.registrar("capa_da_pasta", detalhes={
            "pasta": pasta, "paciente": quem.get("nome", ""),
            "registro": quem.get("registro", "")})
        # A busca nos relatórios preserva o posicionamento que acabou de entrar.
        self.buscar(nome=quem.get("nome", ""),
                          registro=quem.get("registro", ""),
                          nascimento=quem.get("nascimento", ""),
                          preservar_posicionamento=True, pasta=pasta)
        if importado.achou():
            self.capa.mostrar_status(
                f"{quem.get('nome') or quem.get('registro')} — importado: "
                + importado.resumo() + ".")

    def correcao_salva(self, registro: str, campos: dict) -> None:
        """Correção de cadastro é dado de paciente: fica no histórico de uso."""
        historico.registrar("capa_correcao", detalhes={
            "registro": registro, "campos": ", ".join(sorted(campos))})

    def esquecer_modo_completa(self) -> None:
        """Outro paciente entrou: o pedido de capa do ANTERIOR não vale para ele.

        ``_completa_pedida`` só era desfeito no botão "Próximo paciente".
        Trocando de paciente pela busca, o próximo — recém-vindo da tomografia —
        abria em modo Completa, com Curso e Prescrições vazios e a Impressão
        acesa sobre uma capa que ainda não existe.
        """
        self._completa_pedida = False

    def pasta_para_a_capa(self, pasta, da_bancada: bool, nome: str,
                          registro: str) -> str:
        """Qual pasta de paciente vale para a capa que está sendo montada.

        A pasta aberta (``_pasta_carregada``) é a do caso da BANCADA — é dela
        que ``carregar_da_pasta`` tira as notas e as fotos de posicionamento.
        Ela só serve quando a capa é desse mesmo paciente.

        Escolher outro na busca e continuar apontado para a pasta da bancada
        era o caminho que sobrava para a mistura que esta tela mais precisa
        evitar: capa de B com a nota e as fotos de A, dizendo "da pasta: nota
        SETUP_A.txt" — informação de outro paciente, com a cara de ter sido
        importada para este.
        """
        if pasta is not None:      # quem chamou apontou uma: ela manda
            return pasta
        aberta = self.janela.caso.pasta_carregada or ""
        if not aberta or da_bancada:
            return aberta
        reg_bancada = capa_dados.normalizar_id(self.janela.form.pac_registro.text())
        reg_alvo = capa_dados.normalizar_id(registro or "")
        if reg_bancada or reg_alvo:
            return aberta if reg_bancada == reg_alvo else ""
        # Sem registro dos dois lados (paciente da TC ainda sem cadastro), o
        # nome é a única chave que resta — a mesma regra de
        # ``capa.posicionamento_e_de``.
        return (aberta
                if (capa_dados.normalizar_nome(self.janela.form.pac_nome.text())
                    == capa_dados.normalizar_nome(nome or "")) else "")

    def paciente_escolhido(self) -> None:
        """Escolher o paciente na busca traz TUDO que os relatórios têm dele.

        A busca é a porta de quem chega da tomografia, e sem este passo a tela
        ficava com nome, registro e nascimento — sem a foto 3×4, sem convênio,
        sexo, contato, médico, máquina, curso, intenção, CID nem uma prescrição.
        Quem cadastrasse a simulação e imprimisse a capa dali levava uma folha
        em branco com o nome certo em cima, que é a pior versão deste documento.

        A busca é **adiada**: o gatilho é a mudança de seleção, e ela muda a
        cada tecla de seta na lista. Ler os relatórios custa quase meio segundo
        — percorrer dez nomes com o teclado seriam quatro segundos de tela
        travada, montando nove capas que ninguém pediu. Quem parou num nome
        espera; quem está passando não paga nada.
        """
        self.capa.mostrar_status("Carregando os dados do paciente…")
        self._timer_busca.start(_ESPERA_BUSCA_CAPA)

    def buscar_o_escolhido(self) -> None:
        """Dispara a busca do paciente que está na tela agora.

        Lê a identificação no momento do disparo, não no do agendamento: entre
        um e outro a seleção pode ter andado, e buscar o nome antigo encheria a
        tela com a capa de quem a pessoa já deixou para trás.
        """
        atual = self.capa.coletar()
        if not (atual.nome or atual.registro):
            return
        self.buscar(nome=atual.nome, registro=atual.registro,
                          nascimento=atual.nascimento,
                          preservar_posicionamento=True)

    def buscar(self, nome: Optional[str] = None,
                     registro: Optional[str] = None,
                     nascimento: Optional[str] = None,
                     preservar_posicionamento: bool = False,
                     pasta: Optional[str] = None) -> None:
        """Procura o paciente nos relatórios e joga o resultado na tela.

        Sem argumentos, procura quem está na bancada — é o botão "Procurar" e a
        primeira abertura da Capa com um caso carregado. Com eles, procura quem
        acabou de ser escolhido na busca de paciente (ver
        ``paciente_escolhido``), que é o caminho de quem vem da TC.
        """
        da_bancada = nome is None and registro is None
        nome = (nome if nome is not None
                else self.janela.form.pac_nome.text()).strip()
        registro = (registro if registro is not None
                    else self.janela.form.pac_registro.text()).strip()
        nascimento = (nascimento if nascimento is not None
                      else self.janela.form.pac_nascimento.text()).strip()
        if not nome and not registro:
            self.capa.mostrar_status(
                "Sem nome nem registro do paciente — não há como procurar no "
                "relatórios.", erro=True)
            return
        # Montar a capa zera os quadros de posicionamento. Fotos que ainda não
        # viraram cadastro de simulação só existem aqui: apagá-las caladas perde
        # o trabalho da tomografia, que não se refaz sem o paciente na sala.
        guardado = []
        # Preservar SÓ o que é deste paciente. Sem a conferência de dono, o
        # caminho da lista e o do botão "Da pasta" repunham as fotos de quem
        # estava na tela antes: paciente A com fotos, capa de B pedida, e as
        # fotos de A saíam impressas na capa de B. Ver
        # ``capa.posicionamento_e_de``.
        if (preservar_posicionamento
                and self.capa.posicionamento_e_de(registro, nome)):
            guardado = self.capa.posicionamento_atual()
        elif (self.capa.posicionamento_pendente()
                and not self.capa.confirmar_descarte_do_posicionamento(
                    self.capa.coletar().nome, nome or registro)):
            self.capa.mostrar_status(
                "Posicionamento mantido — a capa não foi montada. Cadastre a "
                "simulação e procure de novo.", erro=True)
            return
        # ``processEvents`` abre a porta para outro clique na lista de pacientes
        # entrar aqui no meio — e a segunda busca terminaria por cima da
        # primeira, com a capa de um paciente e o posicionamento do outro.
        if self._buscando:
            return
        self._buscando = True
        self.capa.mostrar_status("Procurando nos relatórios…")
        QApplication.processEvents()
        try:
            res = capa_dados.buscar(registro, nome, nascimento)
        except Exception as exc:  # noqa: BLE001 — a tela continua editável
            _LOG.exception("Capa: falha ao ler os relatórios da capa")
            self.capa.mostrar_status(
                f"Não consegui ler os relatórios: {exc}", erro=True)
            return
        finally:
            self._buscando = False

        capa = capa_pdf.de_resultado(
            res, nome=nome, registro=registro, nascimento=nascimento,
            maquina=constantes.rotulo_maquina(self.maquina_do_caso()),
            medico=(self.janela.form.eq_medico.currentText() if da_bancada else ""))
        # A pasta vem de QUEM CHAMOU, nunca da tela. Quem apontou a pasta pelo
        # botão "Da pasta" (ver ``da_pasta``) não tem caso na bancada e
        # precisa que ela sobreviva a esta busca — mas herdar a que já estava na
        # tela seria pior que perdê-la: ao trocar de paciente, as fotos e notas
        # da pasta do ANTERIOR entrariam na capa do novo por ``carregar_da_pasta``.
        self.capa.definir_pasta(
            self.pasta_para_a_capa(pasta, da_bancada, nome, registro))
        self.capa.carregar(capa, capa_pdf.opcoes_de(res))
        if guardado:
            self.capa.repor_posicionamento(guardado)
        # Fotos e notas de posicionamento moram na pasta do paciente, junto com
        # o DICOM — só depois de ``carregar``, que zera os quadros.
        # A pasta é a que ACABOU de ser definida acima, não a da bancada. Com o
        # caso de A na bancada e a Capa apontada para a pasta de B, ler
        # ``_pasta_carregada`` aqui punha as fotos e a nota de A na capa de B —
        # a mesma mistura de pacientes que o dono do posicionamento evita, por
        # outra porta.
        importado = self.capa.carregar_da_pasta(
            self.capa.pasta_do_paciente(), nome=capa.nome,
            registro=capa.registro)
        avisos = res.avisos
        simulando = self.capa.modo() == capa_tela.SIMULACAO
        if simulando:
            # Na tomografia, não haver prescrição aprovada é o esperado, não uma
            # pendência: o caso ainda não foi calculado.
            avisos = [a for a in avisos if a != capa_dados.AVISO_SEM_PRESCRICAO]
        self.capa.mostrar_avisos(avisos)
        extra = f" — da pasta: {importado.resumo()}" if importado.achou() else ""
        # O recado diz o PRÓXIMO PASSO, e o próximo passo depende do que já está
        # feito. Pedir para arrastar fotos a quem acabou de arrastá-las (ao
        # apertar "Atualizar", por exemplo) faz a linha de status virar ruído
        # que ninguém lê — e é nela que os recados que importam aparecem.
        if simulando:
            if self.capa.posicionamento_tem_fotos():
                falta = "Confira e cadastre a simulação."
            else:
                falta = "Arraste as fotos do posicionamento e escolha a nota."
            achado = f"{capa.nome} carregado{extra}. {falta}"
        else:
            achado = f"Capa de {capa.nome} montada{extra}."
        if res.achou or res.prescricoes:
            self.capa.mostrar_status(achado)
        else:
            self.capa.mostrar_status(
                f"Paciente não encontrado nos relatórios{extra} — preencha os "
                "campos e siga.", erro=True)
        historico.registrar("capa_montada",
                            detalhes={"nome": capa.nome, "achou": res.achou})

    def maquina_do_caso(self) -> str:
        """Acelerador do plano ativo, para a capa que o relatório não conhece."""
        return str(((self.janela.caso.dados or {}).get("RP") or {}).get("maquina") or "")

    def pdf_atual(self) -> Optional[str]:
        """Gera o PDF do que está na tela e devolve o caminho do arquivo.

        Sempre regenera: os campos são editáveis e não há como saber se alguém
        mexeu num deles desde a última vez. Um PDF de capa custa milissegundos
        — reaproveitar arquivo aqui só compraria o risco de imprimir a versão
        anterior.
        """
        import tempfile
        capa = self.capa.coletar()
        if not capa.nome.strip():
            self.capa.mostrar_status("A capa precisa ao menos do nome do "
                                     "paciente.", erro=True)
            return None
        try:
            pdf = capa_pdf.gerar(capa)
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Capa: falha ao gerar o PDF")
            self.capa.mostrar_status(f"Não consegui gerar a capa: {exc}",
                                     erro=True)
            return None
        try:
            slug = re.sub(r"[^A-Za-z0-9]+", "_", capa.nome).strip("_")[:40]
            fd, caminho = tempfile.mkstemp(prefix=f"CAPA_{slug}_", suffix=".pdf")
            with os.fdopen(fd, "wb") as fh:
                fh.write(pdf)
        except OSError as exc:
            self.capa.mostrar_status(f"Não consegui gravar a capa: {exc}",
                                     erro=True)
            return None
        self.descartar_pdf(exceto=caminho)
        self._caminho = caminho
        return caminho

    def descartar_pdf(self, exceto: Optional[str] = None) -> None:
        """Apaga o PDF de capa anterior, para não deixar rastro no %TEMP%."""
        caminho = self._caminho
        self._caminho = None
        if not caminho or caminho == exceto:
            return
        try:
            os.remove(caminho)
        except OSError:
            pass   # aberto no leitor ou já removido

    def visualizar(self) -> None:
        caminho = self.pdf_atual()
        if not caminho:
            return
        try:
            os.startfile(caminho)
        except OSError as exc:
            self.capa.mostrar_status(f"Não consegui abrir a capa: {exc}",
                                     erro=True)
            return
        self.capa.mostrar_status("Capa aberta (arquivo temporário, não salvo).")

    def imprimir(self) -> None:
        caminho = self.pdf_atual()
        if not caminho:
            return
        try:
            os.startfile(caminho, "print")
        except OSError as exc:
            # Nem todo leitor de PDF registra o verbo "print"; abrir é o plano B
            # honesto — a pessoa imprime pelo próprio leitor.
            _LOG.info("Capa: impressão direta indisponível (%s) — abrindo", exc)
            self.visualizar()
            return
        self.capa.mostrar_status("Capa enviada para a impressora.")
        historico.registrar("capa_impressa",
                            detalhes={"nome": self.capa.coletar().nome})

    def salvar(self) -> None:
        """Grava a capa na pasta do paciente (ou onde escolherem)."""
        capa = self.capa.coletar()
        if not capa.nome.strip():
            self.capa.mostrar_status("A capa precisa ao menos do nome do "
                                     "paciente.", erro=True)
            return
        slug = re.sub(r"[^A-Za-z0-9]+", "_", capa.nome).strip("_")[:60]
        sugerido = os.path.join(self.janela.caso.pasta_carregada or "",
                                f"Capa_{slug}.pdf")
        caminho, _ = QFileDialog.getSaveFileName(
            self.janela, "Salvar a capa", sugerido, "PDF (*.pdf)")
        if not caminho:
            return
        try:
            with open(caminho, "wb") as fh:
                fh.write(capa_pdf.gerar(capa))
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("Capa: falha ao salvar")
            ui.alertar(self.janela, "Erro ao salvar a capa", str(exc))
            return
        self.capa.mostrar_status(f"Capa salva em {caminho}.")
        historico.registrar("capa_salva", detalhes={"caminho": caminho})
