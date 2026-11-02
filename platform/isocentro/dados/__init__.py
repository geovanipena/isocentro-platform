"""O que o app grava e relê DELE MESMO — a memória local, não a clínica.

O dado do paciente vem do banco (``banco/``). Aqui está o que o programa produz
e precisa reencontrar depois: o registro versionado de cada ficha
(``registro_json``, ``indice``, ``diff_versoes``, ``backup``, ``empacotar``), os
cadastros do serviço (``auth``, ``equipe``, ``config_servico``, ``cadastro_sus``,
``inventario``, ``notas_setup``), as correções feitas à mão (``correcoes``), a
trilha de uso (``historico``), o rastro de erro e quem dele chega ao admin
(``log_app``, que as DUAS portas de entrada chamam — a interface e o
executável da varredura) e as duas peças que respondem "onde" e "como se
escreve": ``ambiente`` e ``nomes``.

Quase todo arquivo escrito por este pacote fica na **pasta do app**
(``isocentro.raiz.pasta_do_app``) e é migrado pelo ``migrar.ps1`` — que
NUNCA sobrescreve. Por isso nenhum deles pode viajar dentro do zip do pacote:
a migração pularia o arquivo real do serviço. A lista está em
``tools/gerar_executavel.NUNCA_NO_PACOTE``.
"""
