"""O que o usuário vê e opera — as telas e as peças compartilhadas entre elas.

``gui`` é a janela; ``ui`` e ``estilo`` são as peças e a paleta de que todas as
telas se servem, e é por eles que a tela nova começa, nunca pelo Qt cru
(``tests/test_padrao_visual.py`` reprova o Qt cru, inclusive o hexadecimal). O
resto é uma tela cada: Capa, Fichinha, Ficha Virtual, Qualidade, Simulação,
Administração, e os diálogos de busca, edição e agendamento.

``carregadores`` está aqui, e não em ``dominio/``, apesar de não desenhar nada:
ele existe para tirar as duas cargas pesadas (o caso e o corpo 3D) de cima da
interface, e só faz sentido ao lado de quem espera por elas.
"""
