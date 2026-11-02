"""A borda do app: quem fala com o que está fora dele (arquivo, rede DICOM, banco).

Adaptador devolve o dado cru — ``pydicom.Dataset``, linha de banco — e não
importa ``rt``: quem chama entrega o dado a quem modela (AD-38 da espinha,
``docs/planejamento/sistema-global/architecture-isocentro-2026-10-19/``).
Nasceu na R-58 (22/10/2026), com o que era a parte de I/O de ``dicom/``.
"""
