-- 0001 — núcleo: versão do esquema, registro tabela → dono e o log encadeado.
--
-- Aplicado pelo `isocentro_dono` (AD-19), nunca pelo app: é ele o dono de
-- tudo o que nasce aqui, e é com os direitos dele que o gatilho do log roda.
-- Os três papéis (`isocentro_dono`, `isocentro_app`,
-- `isocentro_concentradora`) são do cluster e já existem antes deste arquivo
-- (`tools/migrar_banco.py --papeis`).
--
-- Fonte: AD-4 (dado e log na mesma transação, log único), AD-5 (nada se
-- apaga nem se edita), AD-6 (corrente global por gatilho SECURITY DEFINER,
-- papéis), AD-19 (versão do esquema), AD-27 (schema por módulo, registro
-- tabela → dono) e AD-32 (verificador) da espinha; CAP-1, CAP-4 e CAP-5 da
-- spec Fundação.

CREATE SCHEMA nucleo;
GRANT USAGE ON SCHEMA nucleo TO isocentro_app, isocentro_concentradora;

-- AD-19: o app compara a maior versão daqui com a que ele conhece e, se não
-- bater, abre somente leitura. A linha é gravada pelo `migrar_banco.py`, na
-- mesma transação do arquivo aplicado: arquivo pela metade não deixa versão.
CREATE TABLE nucleo.versao_esquema (
    versao      integer PRIMARY KEY CHECK (versao > 0),
    arquivo     text NOT NULL,
    aplicada_em timestamptz NOT NULL DEFAULT clock_timestamp()
);
GRANT SELECT ON nucleo.versao_esquema TO isocentro_app, isocentro_concentradora;

-- AD-27: quem grava cada tabela. O schema da tabela é o nome do módulo dono;
-- a restrição prende os dois, para que um registro errado não deixe o módulo
-- `plano` gravar em `qualidade.*` com aparência de ordem.
CREATE TABLE nucleo.dono_tabela (
    tabela text PRIMARY KEY
        CHECK (tabela ~ '^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$'),
    modulo text NOT NULL CHECK (modulo ~ '^[a-z][a-z0-9_]*$'),
    CHECK (split_part(tabela, '.', 1) = modulo)
);
GRANT SELECT ON nucleo.dono_tabela TO isocentro_app, isocentro_concentradora;

-- A ponta da corrente: uma linha só, travada pelo gatilho a cada INSERT no
-- log. A trava é o que serializa as três clínicas numa corrente só (AD-6):
-- com duas estações gravando juntas e cada uma lendo o "último hash" sem
-- trava, as duas encadeariam no mesmo anterior e a corrente se bifurcaria.
-- Ela também dá a posição SEM BURACO, que um `bigserial` não dá (transação
-- desfeita queima o número) — e é o buraco que denuncia a linha apagada.
CREATE TABLE nucleo.ponta (
    id      smallint PRIMARY KEY CHECK (id = 1),
    posicao bigint NOT NULL,
    hash    bytea NOT NULL
);
INSERT INTO nucleo.ponta VALUES (1, 0, decode(repeat('00', 32), 'hex'));

-- O log único (AD-4). Só referência, nunca texto livre (AD-33): `registro` é
-- o id da linha gravada, e `substitui` o id da que ela corrige (AD-5).
-- `posicao`, `quando`, `hash_anterior` e `hash` são do gatilho: o app nem tem
-- permissão de escrevê-los (GRANT por coluna, abaixo).
CREATE TABLE nucleo.log (
    posicao       bigint PRIMARY KEY,
    quando        timestamptz NOT NULL,
    quem          text NOT NULL CHECK (quem <> ''),
    modulo        text NOT NULL,
    tabela        text NOT NULL REFERENCES nucleo.dono_tabela (tabela),
    registro      text NOT NULL CHECK (registro <> ''),
    substitui     text CHECK (substitui <> ''),
    versao_origem text CHECK (versao_origem <> ''),
    hash_anterior bytea NOT NULL,
    hash          bytea NOT NULL
);
GRANT SELECT ON nucleo.log TO isocentro_app, isocentro_concentradora;
GRANT INSERT (quem, modulo, tabela, registro, substitui, versao_origem)
    ON nucleo.log TO isocentro_app, isocentro_concentradora;

-- Cada campo vira `comprimento:valor`, e o nulo vira `-`. Separador simples
-- (`|`) deixaria `a|b` + `c` e `a` + `b|c` com o mesmo texto, e portanto o
-- mesmo hash; com o comprimento na frente, nenhum valor imita a fronteira.
-- O verificador (`isocentro/nucleo/integridade.py`) refaz a MESMA conta em
-- Python: é ele, e não esta função, que se confia no dia da auditoria, porque
-- quem tem DDL pode trocar a função.
CREATE FUNCTION nucleo.campo(valor text) RETURNS text
    LANGUAGE sql IMMUTABLE
    SET search_path = pg_catalog
AS $$
    SELECT CASE WHEN valor IS NULL THEN '-'
                ELSE length(valor)::text || ':' || valor END
$$;

-- `quando` entra como microssegundos desde 1970 (inteiro exato), não como
-- texto: o texto de um timestamptz depende do DateStyle e do TimeZone da
-- sessão, e o mesmo instante teria dois hashes conforme a estação.
CREATE FUNCTION nucleo.hash_da_linha(l nucleo.log) RETURNS bytea
    LANGUAGE sql IMMUTABLE
    SET search_path = pg_catalog, nucleo
AS $$
    SELECT sha256(l.hash_anterior || convert_to(
        nucleo.campo(l.posicao::text)
        || nucleo.campo((extract(epoch FROM l.quando) * 1000000)::bigint::text)
        || nucleo.campo(l.quem)
        || nucleo.campo(l.modulo)
        || nucleo.campo(l.tabela)
        || nucleo.campo(l.registro)
        || nucleo.campo(l.substitui)
        || nucleo.campo(l.versao_origem),
        'UTF8'))
$$;

-- SECURITY DEFINER (AD-6): roda com os direitos do dono, para ler e mover a
-- ponta que o app não enxerga. O `search_path` fixo é o que torna isso
-- seguro — sem ele, quem chama poderia pôr na frente um schema seu com um
-- `sha256` de mentira.
CREATE FUNCTION nucleo.encadear() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, nucleo
AS $$
DECLARE
    dono  text;
    ponta nucleo.ponta%ROWTYPE;
    ja    bigint;
BEGIN
    SELECT modulo INTO dono FROM nucleo.dono_tabela WHERE tabela = NEW.tabela;
    IF dono IS DISTINCT FROM NEW.modulo THEN
        RAISE EXCEPTION 'a tabela % é do módulo %, não de %',
            NEW.tabela, coalesce(dono, '(nenhum)'), NEW.modulo
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    -- A trava vem ANTES de conferir a correção: é ela que impede duas
    -- estações de corrigir o mesmo registro ao mesmo tempo, cada uma vendo
    -- que ninguém o tinha corrigido ainda.
    SELECT * INTO ponta FROM nucleo.ponta WHERE id = 1 FOR UPDATE;

    IF NEW.substitui IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM nucleo.log
                        WHERE tabela = NEW.tabela
                          AND registro = NEW.substitui) THEN
            RAISE EXCEPTION 'a correção aponta % em %, que não foi gravado',
                NEW.substitui, NEW.tabela
                USING ERRCODE = 'foreign_key_violation';
        END IF;
        -- Duas correções do mesmo registro bifurcariam o histórico, e o
        -- "vigente" deixaria de ser um só (AD-5).
        SELECT posicao INTO ja FROM nucleo.log
         WHERE tabela = NEW.tabela AND substitui = NEW.substitui;
        IF FOUND THEN
            RAISE EXCEPTION '% em % já foi corrigido (posição %): corrija o vigente',
                NEW.substitui, NEW.tabela, ja
                USING ERRCODE = 'unique_violation';
        END IF;
    END IF;

    NEW.posicao := ponta.posicao + 1;
    -- `clock_timestamp()` e não `now()`: o `now()` é a hora em que a
    -- transação COMEÇOU, e quem esperou a trava ficaria com hora anterior à
    -- da linha de antes.
    NEW.quando := clock_timestamp();
    NEW.hash_anterior := ponta.hash;
    NEW.hash := nucleo.hash_da_linha(NEW);
    UPDATE nucleo.ponta SET posicao = NEW.posicao, hash = NEW.hash WHERE id = 1;
    RETURN NEW;
END
$$;

CREATE TRIGGER log_encadear BEFORE INSERT ON nucleo.log
    FOR EACH ROW EXECUTE FUNCTION nucleo.encadear();

-- O app e a concentradora já não têm UPDATE, DELETE nem TRUNCATE (só os
-- GRANTs acima). O gatilho segura também o dono, por engano; contra o dono
-- de propósito (que pode desligar o gatilho), quem responde é o verificador
-- com as âncoras (AD-32).
CREATE FUNCTION nucleo.recusar_alteracao() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'o log só aceita INSERT: nada se apaga nem se edita (AD-5)'
        USING ERRCODE = 'insufficient_privilege';
END
$$;

CREATE TRIGGER log_imutavel BEFORE UPDATE OR DELETE ON nucleo.log
    FOR EACH ROW EXECUTE FUNCTION nucleo.recusar_alteracao();
CREATE TRIGGER log_sem_truncate BEFORE TRUNCATE ON nucleo.log
    FOR EACH STATEMENT EXECUTE FUNCTION nucleo.recusar_alteracao();
CREATE TRIGGER ponta_sem_truncate BEFORE TRUNCATE ON nucleo.ponta
    FOR EACH STATEMENT EXECUTE FUNCTION nucleo.recusar_alteracao();

-- Toda tabela que o dono criar daqui em diante (as dos módulos) nasce com
-- SELECT e INSERT para o app e a concentradora, e nada mais (AD-5). Vem no
-- FIM do arquivo de propósito: antes, valeria também para a `ponta` e a
-- `versao_esquema`, que o app não grava.
ALTER DEFAULT PRIVILEGES FOR ROLE isocentro_dono
    GRANT SELECT, INSERT ON TABLES TO isocentro_app, isocentro_concentradora;
ALTER DEFAULT PRIVILEGES FOR ROLE isocentro_dono
    GRANT USAGE ON SEQUENCES TO isocentro_app, isocentro_concentradora;
