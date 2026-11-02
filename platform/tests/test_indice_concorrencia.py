"""O índice central de fichas não pode ser perdido nem corrompido.

``registro_fichas.json`` é o que a tela de Histórico lê. Ele é derivado (dá para
reconstruir a partir dos JSON dos pacientes), mas perdê-lo em silêncio é o pior
dos mundos: a busca abre vazia e ninguém percebe que faltou alguma coisa. Duas
garantias: a gravação é atômica (nunca fica um arquivo pela metade) e o ciclo
ler→alterar→gravar é exclusivo (dois físicos gerando ficha ao mesmo tempo não se
sobrescrevem).

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import indice  # noqa: E402


class _IndiceTemporario(unittest.TestCase):
    """Aponta o índice para uma pasta descartável — nunca o do serviço."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self._original = indice.REGISTRO_PATH
        indice.REGISTRO_PATH = self.dir / "registro_fichas.json"
        self.addCleanup(setattr, indice, "REGISTRO_PATH", self._original)

    def _ficha(self, registro: str) -> Path:
        p = self.dir / f"FICHA_{registro}.json"
        p.write_text(json.dumps({
            "paciente": {"registro": registro, "nome": f"Paciente {registro}"},
            "versoes": [{"versao": 1, "dados": {}, "plano_rp": {}}],
        }), encoding="utf-8")
        return p

    def _indexados(self) -> set:
        reg = json.loads(indice.REGISTRO_PATH.read_text(encoding="utf-8"))
        return {f["registro"] for f in reg["fichas"]}


class TestEscritaAtomica(_IndiceTemporario):

    def test_nao_deixa_temporario_para_tras(self):
        # O .lock FICA (é ele que o SO trava, e apagá-lo é justamente o que
        # quebrava no Windows); o temporário da escrita, não.
        indice.sincronizar_arquivo(self._ficha("R1"))
        self.assertEqual([p.name for p in self.dir.iterdir()
                          if p.name.endswith(".tmp")], [])

    def test_falha_no_meio_da_escrita_preserva_o_indice_anterior(self):
        # O arquivo final só é trocado pelo os.replace, no fim: uma falha antes
        # dele não pode encostar no que já estava indexado.
        indice.sincronizar_arquivo(self._ficha("R1"))
        original = indice.REGISTRO_PATH.read_text(encoding="utf-8")

        def explodir(*_a, **_k):
            raise OSError("disco cheio")

        real = indice.json.dump
        indice.json.dump = explodir
        try:
            with self.assertRaises(OSError):
                indice.sincronizar_arquivo(self._ficha("R2"))
        finally:
            indice.json.dump = real
        self.assertEqual(indice.REGISTRO_PATH.read_text(encoding="utf-8"), original)
        self.assertEqual(self._indexados(), {"R1"})

    def test_indice_truncado_nao_derruba_a_busca(self):
        # Continua valendo o fallback: arquivo ilegível vira índice vazio, sem
        # exceção — é o que a escrita atômica passa a tornar improvável.
        indice.REGISTRO_PATH.write_text('{"fichas": [', encoding="utf-8")
        self.assertEqual(indice.buscar(), [])


class TestEscritaConcorrente(_IndiceTemporario):

    def test_oito_gravadores_ao_mesmo_tempo_nao_perdem_ficha(self):
        # Sem exclusão mútua, cada um lê o índice ANTES da alteração do outro e
        # grava por cima: o último a gravar apaga as fichas dos demais. São 8
        # gravadores porque o modo de falha que escapou (o lock por
        # criar-e-apagar arquivo, que no Windows devolve PermissionError a quem
        # chega durante o *delete pending*) só aparece com disputa de verdade.
        fichas = [self._ficha(f"R{i}") for i in range(120)]
        erros: list = []

        def trabalhar(fatia):
            for p in fatia:
                try:
                    indice.sincronizar_arquivo(p)
                except Exception as e:  # noqa: BLE001
                    erros.append(repr(e))

        threads = [threading.Thread(target=trabalhar, args=(fichas[i::8],))
                   for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(erros, [])
        self.assertEqual(self._indexados(), {f"R{i}" for i in range(120)})

    def test_lock_de_execucao_anterior_nao_trava_o_servico(self):
        # O arquivo de lock nunca é apagado: encontrá-lo de pé (de uma sessão
        # anterior, ou de um processo que morreu) não pode barrar ninguém — quem
        # trava é o SO sobre o descritor, e ele solta sozinho.
        alvo = indice._lock_path()
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text("", encoding="utf-8")
        indice.sincronizar_arquivo(self._ficha("R1"))
        self.assertEqual(self._indexados(), {"R1"})

    def test_lock_tomado_por_outro_nao_impede_a_ficha_de_ser_salva(self):
        # Índice é derivado: se o lock não vier, grava-se assim mesmo — travar o
        # salvamento por causa dele seria pior que a disputa que ele evita.
        indice.sincronizar_arquivo(self._ficha("R1"))
        fd = os.open(str(indice._lock_path()), os.O_CREAT | os.O_RDWR)
        try:
            self.assertTrue(indice._travar_fd(fd))      # segura o lock
            espera = indice._LOCK_ESPERA_S
            indice._LOCK_ESPERA_S = 0.1                 # não esperar no teste
            try:
                indice.sincronizar_arquivo(self._ficha("R2"))
            finally:
                indice._LOCK_ESPERA_S = espera
            self.assertEqual(self._indexados(), {"R1", "R2"})
        finally:
            indice._destravar_fd(fd)
            os.close(fd)


class TestResumoPorRegistro(_IndiceTemporario):
    """Uma leitura só do índice para as dez linhas da lista da Fichinha."""

    def _com_versoes(self, registro: str, n: int) -> Path:
        p = self.dir / f"FICHA_{registro}.json"
        p.write_text(json.dumps({
            "paciente": {"registro": registro, "nome": f"Paciente {registro}"},
            "versoes": [{"versao": v, "dados": {}, "plano_rp": {},
                         "pdf": f"ficha_v{v}.pdf"} for v in range(1, n + 1)],
        }), encoding="utf-8")
        indice.sincronizar_arquivo(p)
        return p

    def test_conta_versoes_e_devolve_a_mais_recente(self):
        self._com_versoes("R1", 3)
        res = indice.resumo_por_registro()
        self.assertEqual(res["R1"]["versoes"], 3)
        self.assertEqual(res["R1"]["ultima"]["versao"], 3)
        self.assertTrue(res["R1"]["ultima"]["json_path"])

    def test_filtra_pelos_registros_pedidos(self):
        self._com_versoes("R1", 1)
        self._com_versoes("R2", 2)
        self.assertEqual(set(indice.resumo_por_registro({"R2"})), {"R2"})
        # Registro que não está no índice simplesmente não volta — quem
        # pergunta usa a ausência para apagar os botões daquela linha.
        self.assertEqual(indice.resumo_por_registro({"R9"}), {})

    def test_registro_vazio_ou_none_nao_quebra(self):
        self._com_versoes("R1", 1)
        self.assertEqual(indice.resumo_por_registro({None, ""}), {})
        self.assertEqual(set(indice.resumo_por_registro(set())), set())

    def test_indice_ausente(self):
        self.assertEqual(indice.resumo_por_registro({"R1"}), {})


if __name__ == "__main__":
    unittest.main()
