"""O núcleo: o que é de todos os módulos e não conhece nenhum deles.

Regra da camada (AD-2 e AD-22 da espinha, `docs/planejamento/sistema-global/
architecture-isocentro-2026-10-19/ARCHITECTURE-SPINE.md`): sem Qt, sem tela,
sem módulo e sem adaptador — o `tests/test_arquitetura.py` reprova o import.
O que precisa de banco, arquivo ou rede entra por uma PORTA (protocolo)
declarada aqui e implementada do lado de fora.
"""
