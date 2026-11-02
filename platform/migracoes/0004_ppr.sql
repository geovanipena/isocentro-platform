-- 0004 — as partes do PPR vivo, guardadas por cada módulo dono (R-85).
--
-- Fonte: AD-3 (dono único), AD-5 (nada se edita), AD-27 (tabela → dono) e
-- AD-41 (PPR vivo) da espinha; CAP-10 e CAP-11 da spec Documentação; mapa em
-- `docs/planejamento/sistema-global/ppr-vivo-mapa-2026-10-28.md`.
--
-- O PPR não é uma tabela da Documentação: cada módulo guarda o que conhece,
-- e a Documentação só lê e monta. Por isso as MESMAS duas tabelas nascem em
-- cada esquema de módulo — com uma tabela só, o dono de cada linha seria uma
-- coluna, e o gatilho do log (que confere o dono pela TABELA) deixaria a GQ
-- gravar o texto da Segurança.
--
-- `ppr_parte`: o texto corrido de um capítulo, subseção ou anexo, com os
-- documentos de origem (PDFs embutidos) e a fonte de onde veio. `chave` é a
-- de `dominio/ppr.py` (`anexo/<chave>` para anexo): número e letra mudam de
-- clínica para clínica, a chave não.
--
-- `ppr_dado`: as tabelas do PPR (equipe, equipamentos, testes…) como dado do
-- dono. PROVISÓRIA: quando o módulo tiver a tabela de verdade (GQ: o
-- inventário da R-84), o dado muda de casa por corte de entidade (AD-37).
--
-- Vigente é o registro que nenhum outro substitui no log (AD-5): corrigir o
-- texto é gravar um registro novo apontando o anterior em `substitui`.

CREATE SCHEMA qualidade;
CREATE SCHEMA plano;
CREATE SCHEMA seguranca;
CREATE SCHEMA documentacao;
GRANT USAGE ON SCHEMA qualidade, plano, seguranca, documentacao
    TO isocentro_app, isocentro_concentradora;

-- Um laço em vez de dez CREATE TABLE copiados: as dez tabelas têm de ser
-- iguais, e a cópia é onde uma delas ficaria sem a restrição da clínica.
-- A Fundação é o núcleo e grava em `nucleo.*`.
DO $$
DECLARE
    m text;
BEGIN
    FOREACH m IN ARRAY ARRAY['nucleo', 'qualidade', 'plano', 'seguranca',
                             'documentacao'] LOOP
        EXECUTE format($t$
            CREATE TABLE %1$I.ppr_parte (
                id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                -- Os códigos do `atividades_db.UNIDADES` (ANA é a CTRA).
                clinica     text NOT NULL CHECK (clinica IN ('ANA', 'BNO', 'CBR')),
                chave       text NOT NULL
                    CHECK (chave ~ '^(anexo/)?[a-z][a-z0-9_]*$'),
                -- Vazio é legítimo: capítulo que é só "Vide anexo X" não tem
                -- corpo, e o "Vide" é do gerador, que calcula a letra.
                texto       text NOT NULL,
                documentos  jsonb NOT NULL DEFAULT '[]'
                    CHECK (jsonb_typeof(documentos) = 'array'),
                fonte       text NOT NULL CHECK (fonte ~ '\S'),
                quando      timestamptz NOT NULL DEFAULT clock_timestamp()
            );
            CREATE INDEX ppr_parte_clinica ON %1$I.ppr_parte (clinica, chave);
            CREATE TABLE %1$I.ppr_dado (
                id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                clinica     text NOT NULL CHECK (clinica IN ('ANA', 'BNO', 'CBR')),
                chave       text NOT NULL CHECK (chave ~ '^[a-z][a-z0-9_]*$'),
                conteudo    jsonb NOT NULL,
                fonte       text NOT NULL CHECK (fonte ~ '\S'),
                quando      timestamptz NOT NULL DEFAULT clock_timestamp()
            );
            CREATE INDEX ppr_dado_clinica ON %1$I.ppr_dado (clinica, chave);
            INSERT INTO nucleo.dono_tabela VALUES
                (%2$L, %1$L), (%3$L, %1$L);
        $t$, m, m || '.ppr_parte', m || '.ppr_dado');
    END LOOP;
END
$$;
