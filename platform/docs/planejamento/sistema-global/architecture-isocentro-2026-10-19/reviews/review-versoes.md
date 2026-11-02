# Revisão de versões e tecnologias — ARCHITECTURE-SPINE (ISOCENTRO)

- **Data:** 19/10/2026
- **Alvo:** `../ARCHITECTURE-SPINE.md` (seção Stack, AD-10, AD-12, AD-20, AD-25) e `../.memlog.md` (entradas `version`)
- **Pergunta:** cada decisão com tecnologia foi conferida na web, no projeto ou no starter, ou foi afirmada de memória?
- **Projeto greenfield?** Não. É brownfield sem starter, então não há padrões de starter a conferir. Para o que já está em `requirements.txt` / `testes.yml`, estar no projeto basta como conferência.

## Veredito

As versões novas centrais (PostgreSQL 18.6, psycopg 3.3.4) foram conferidas na web e batem. As que já estão no código estão conferidas pelo próprio projeto. Faltam quatro coisas: a forma de instalar o psycopg no Windows (libpq), a biblioteca do cofre de credenciais do AD-25, o risco de fim de vida do PyQt5/Qt5, e o `windows-latest` sem fixar versão, que contradiz a convenção "versões fixadas exatas".

## Conferência por item

| Tecnologia | Na espinha | Conferido por | Situação em 19/10/2026 | Avaliação |
| --- | --- | --- | --- | --- |
| PostgreSQL | 18.x (18.6) | web (memlog `version`) | 18.6 saiu em 13/08/2026, com 28 correções de segurança. PG 19 em RC 1, GA prevista para **19/11/2026** (o memlog diz "out/2026, GA não confirmado") | OK. Atualizar a nota do memlog. A próxima versão menor sai em 12/11/2026 (18.7) |
| psycopg | 3.3 (3.3.4) | web (memlog) | 3.3.4 de 01/05/2026 é a mais recente; `requires_python >=3.10` | Versão OK. **Lacuna:** o pacote `psycopg` puro precisa da libpq do sistema (via ctypes). No Windows, o caminho prático é `psycopg[binary]` (`psycopg-binary`). A espinha não diz qual dos dois usar, nem como o PyInstaller empacota a libpq. Não achei listado o wheel `cp312-win_amd64` da 3.3.4 (só o da 3.3.3/cp314 apareceu) |
| RLS (AD-12) | PostgreSQL RLS | não conferido na web | recurso estável desde o 9.5; nada no 18 o remove | Baixo risco. Lembrete: o dono da tabela e quem tem BYPASSRLS ignoram as políticas. O `isocentro_dono` não pode ser o papel do app (o AD-6 já separa os papéis) |
| scram/TLS (AD-25) | scram + TLS obrigatório | não conferido na web | `scram-sha-256` é o padrão de `password_encryption` há várias versões; o PG 18 avisa quando se usa md5. O instalador Windows (EDB) tem SSL, mas o TLS tem que ser ligado na mão (certificado, `ssl=on`, `hostssl` no `pg_hba.conf`) | OK como decisão. Falta passo de operação (gerar e renovar o certificado, `sslmode=verify-full` ou `require` no cliente) |
| Cofre de credenciais do Windows (AD-25) | "cofre de credenciais do Windows" | **não conferido; tecnologia sem nome** | precisa de biblioteca: `keyring` (backend WinVault) ou `pywin32` (`win32cred`); nenhuma das duas está em `requirements.txt`, e o código não usa nenhuma | **Achado:** nomear a biblioteca, fixar a versão, pôr no SOUP e conferir que funciona empacotada no PyInstaller |
| Python | 3.12 | projeto (`requirements.txt`, `testes.yml`) | só correções de segurança desde 02/04/2025; fim de vida em **31/10/2028** | OK. Bom registrar a data na espinha |
| PyQt5 | 5.15.11 | projeto | 5.15.11 (19/07/2024) segue sendo a última versão do PyQt5, que é só de correções. O Qt 5.15 já passou do fim do suporte padrão (licenças legadas em 26/05/2023, assinantes em 26/05/2025); o 5.15.19 foi a última versão comercial. O código aberto só recebe as versões com ~1 ano de atraso | **Achado de risco:** base sem correções de segurança no futuro e sem garantia de wheels para Python ≥3.13. A espinha prende tudo ao PyQt5 (AD-2, AD-18) e não diz nada sobre o fim de vida. Sugestão: anotar em Deferred (migração para PyQt6/PySide6, ou aceitar o risco no SOUP) |
| pyodbc | 5.3.0 | projeto | 5.3.0 (17/10/2025) é a mais recente encontrada, com wheels cp312 win_amd64 | OK |
| pydicom | 3.0.2 | projeto | não achei na web versão mais nova que essa | OK (pelo projeto) |
| pynetdicom | 3.0.4 | projeto | a web só mostrou até a 3.0.3 (07/2025); o projeto fixa a 3.0.4 | OK (pelo projeto) |
| numpy / reportlab | 2.4.6 / 4.5.1 | projeto | não conferido na web | OK (pelo projeto) |
| ruff | 0.16.4 | projeto (`testes.yml:48`) | a web mostra a 0.16.3 como a mais recente indexada; a 0.16.4 está fixada no CI | OK (pelo projeto) |
| PyInstaller | "onedir, 3 specs", sem versão | projeto (3 `.spec`) | mais recente: 6.21.0 (13/06/2026), aceita Python 3.8 a 3.15 | **Achado:** `testes.yml:101` instala `pyinstaller` **sem versão**, o que contradiz a convenção "dependências fixadas exatas" (o executável clínico muda sem ninguém decidir). Fixar a versão, por exemplo `pyinstaller==6.21.0`, depois de conferir |
| CI `windows-latest` | GitHub Actions windows-latest | projeto | o `windows-latest` passou para Windows Server 2025 (set/2025); a imagem foi trocada para VS 2026 em 2026 | **Achado:** o rótulo flutua. Fixar `windows-2025`, pela mesma convenção |
| unittest | stdlib | projeto | — | OK |
| SQLite em SMB (AD-10, motivo) | locking não confiável | web, fontes secundárias (memlog) | a página oficial "Use Over Network" não foi conferida | Baixo risco (é só o motivo da recusa). Conferir na página oficial se for citado no SOUP |

## Achados principais

1. **psycopg no Windows:** a espinha diz "psycopg 3.3" mas não diz se é o pacote puro (precisa da libpq instalada) ou `psycopg[binary]`. Isso decide o empacotamento PyInstaller e o inventário SOUP (libpq/OpenSSL do wheel).
2. **AD-25 sem biblioteca:** a decisão depende de uma tecnologia que não tem nome (`keyring` ou `pywin32`), que não está no projeto e não foi conferida.
3. **PyQt5/Qt5 em fim de vida:** o Qt 5.15 está fora do suporte padrão desde 05/2025, e o PyQt5 não lança versão desde 07/2024. O risco não está registrado.
4. **PyInstaller e `windows-latest` sem versão fixa:** isso contradiz a convenção da própria espinha.
5. **Memlog desatualizado:** o PG 19 tem GA prevista para 19/11/2026 (RC 2 em 12/11), e não para out/2026.

## Fontes

- PostgreSQL 18.6 / 14 EOL: https://www.postgresql.org/ ; https://www.enterprisedb.com/docs/pge/latest/release_notes/rel_notes18.6.0/
- PostgreSQL 19 RC 1 (GA 19/11/2026): https://www.postgresql.org/about/news/postgresql-19-rc-1-released-3409/
- psycopg 3.3.4: https://pypistats.org/packages/psycopg ; https://www.psycopg.org/articles/2025/12/ ; https://pypi.appx.humansignal.com/root/pypi/psycopg/3.3.4
- psycopg-binary: https://www.pypi.org/project/psycopg-binary
- psycopg instalação (libpq, binary): https://www.psycopg.org/psycopg3/docs/basic/install.html ; https://github.com/psycopg/psycopg
- scram no PG 18: https://www.cybertec-postgresql.com/en/from-md5-to-scram-the-next-security-shift-in-postgresql/ ; https://docs.w3cub.com/postgresql~18/auth-password
- TLS no PostgreSQL no Windows (padrão hostssl): https://www.opswat.com/docs/mdcore/v5.22.1/configuration/ssl-connection-for-postgresql-communication
- Qt 5.15 fim de suporte: https://www.qt.io/blog/commercial-lts-qt-5.15.19-released ; https://www.phoronix.com/news/Qt-5.15-LTS-No-More-Standard
- PyQt5 5.15.11: https://riverbankcomputing.com/news/PyQt_v5.15.11_Released ; https://simple-repository.app.cern.ch/project/pyqt5
- Python 3.12 EOL: https://endoflife.date/python
- PyInstaller 6.21.0: https://simple-repository.app.cern.ch/project/pyinstaller
- pyodbc 5.3.0: https://simple-repository.app.cern.ch/project/pyodbc
- pynetdicom: https://www.piwheels.org/project/pynetdicom/
- ruff: https://newreleases.io/project/pypi/ruff/release/0.15.19
- windows-latest → Windows Server 2025: https://github.blog/changelog/2025-07-31-github-actions-new-apis-and-windows-latest-migration-notice/ ; https://depot.dev/changelog/2026-08-22-windows-runner-images.md
