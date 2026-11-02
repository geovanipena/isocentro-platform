"""O banco central do ISOCENTRO (PostgreSQL 18, ``psycopg`` 3.3; AD-10).

``porta``: a ``PortaDoBanco`` do ``nucleo.gravar`` — registro e linha de log
numa transação só (AD-4) — e a leitura do log para o verificador.
``esquema``: a versão do esquema que o app confere ao abrir (AD-19) e as
migrações numeradas de ``migracoes/``, que só o ``isocentro_dono`` aplica.

Nasceu na R-18 (27/10/2026). Login da pessoa, sessão e RLS são da R-19.
"""
