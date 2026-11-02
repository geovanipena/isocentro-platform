"""Radioterapia comum: geometria e números sobre objetos de RT, sem veredito.

Regra da camada (AD-38 da espinha, `docs/planejamento/sistema-global/
architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md`): funções puras sobre
dado já lido por quem chama. Sem Qt, banco, rede, arquivo, PIL nem matplotlib,
e sem importar nada do pacote fora de `rt/` — é o código que todo módulo vai
importar, e o que entra aqui revisa a suíte inteira. Tolerância, aprovado e
reprovado são do módulo dono: aqui se MEDE, e quem decide é a pessoa.
"""
