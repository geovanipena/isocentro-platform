-- 0003 — alerta com ciclo de vida e assinatura presa à versão (R-21).
--
-- Fonte: AD-5 (nada se edita), AD-28 (alerta só da execução vigente), AD-29
-- (alerta como eventos) e AD-30 (assinatura presa à versão) da espinha;
-- CAP-12, CAP-13 e CAP-14 da spec Fundação; FR-5, FR-8 e FR-41 do PRD.
--
-- Nenhuma das três tabelas tem coluna de pessoa: quem abriu, viu, resolveu ou
-- assinou é o `quem` da linha de log do registro, que só a sessão preenche.
-- Uma coluna "pessoa" seria o lugar exato por onde alguém assinaria em nome
-- de outro (FR-8) — com o log dizendo uma coisa e o registro, outra.

-- Um alerta nasce de UMA de duas coisas: uma execução (`nao_conforme`,
-- `indeterminado` ou `erro` de verificação ativa) ou um prazo que entrou no
-- aviso ou venceu (FR-41). A clínica e o perfil vêm de quem abre: a execução
-- não os guarda, e o alerta precisa deles para chegar à pessoa certa.
CREATE TABLE nucleo.alerta (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    origem       text NOT NULL CHECK (origem IN ('execucao', 'prazo')),
    -- UNIQUE: a concentradora e a estação podem reconhecer a mesma execução
    -- vigente; dois alertas do mesmo fato são o que o AD-28 veio impedir.
    execucao_id  bigint UNIQUE REFERENCES nucleo.execucao (id),
    prazo_chave  text CHECK (prazo_chave <> ''),
    objeto       text NOT NULL CHECK (objeto <> ''),
    -- Os códigos do `atividades_db.UNIDADES` (ANA é a CTRA).
    clinica      text NOT NULL CHECK (clinica IN ('ANA', 'BNO', 'CBR')),
    responsavel  text NOT NULL CHECK (responsavel <> ''),
    severidade   text NOT NULL
        CHECK (severidade IN ('alta', 'atencao', 'informativo')),
    motivo       text NOT NULL CHECK (motivo <> ''),
    vence_em     timestamptz,
    -- A hora do BANCO, e não a da estação: é ela que ordena os alertas das
    -- três clínicas, e uma estação com o relógio adiantado passaria na frente.
    quando       timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT alerta_uma_origem CHECK (
        (origem = 'execucao' AND execucao_id IS NOT NULL
                             AND prazo_chave IS NULL)
        OR (origem = 'prazo' AND prazo_chave IS NOT NULL
                             AND execucao_id IS NULL AND vence_em IS NOT NULL)),
    -- O aviso e o vencido do mesmo prazo são dois alertas (o segundo
    -- substitui o primeiro pelo log); o mesmo degrau duas vezes, não.
    CONSTRAINT alerta_prazo_unico UNIQUE (prazo_chave, severidade)
);

-- O ciclo de vida (AD-29): aberto é o alerta sem evento; cada mudança é uma
-- linha nova aqui, nunca UPDATE no alerta.
CREATE TABLE nucleo.alerta_evento (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alerta_id     bigint NOT NULL REFERENCES nucleo.alerta (id),
    evento        text NOT NULL CHECK (evento IN ('visto', 'resolvido')),
    justificativa text CHECK (justificativa ~ '\S'),
    quando        timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX alerta_evento_alerta ON nucleo.alerta_evento (alerta_id);

-- As duas regras do ciclo que o Python também confere (com motivo legível),
-- repetidas aqui para quem pular o Python. SECURITY DEFINER pela trava: o
-- app não tem UPDATE no alerta, e o `FOR UPDATE` pede esse direito.
CREATE FUNCTION nucleo.conferir_evento() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path = pg_catalog, nucleo
AS $$
DECLARE
    sev text;
BEGIN
    -- A trava serializa duas pessoas resolvendo o mesmo alerta ao mesmo
    -- tempo: sem ela, as duas veriam "ainda aberto" e o alerta teria duas
    -- resoluções, com duas justificativas diferentes.
    SELECT severidade INTO sev FROM nucleo.alerta
     WHERE id = NEW.alerta_id FOR UPDATE;
    IF EXISTS (SELECT 1 FROM nucleo.alerta_evento
                WHERE alerta_id = NEW.alerta_id AND evento = 'resolvido') THEN
        RAISE EXCEPTION 'o alerta % já foi resolvido', NEW.alerta_id
            USING ERRCODE = 'unique_violation';
    END IF;
    IF NEW.evento = 'resolvido' AND sev = 'alta'
       AND NEW.justificativa IS NULL THEN
        RAISE EXCEPTION 'resolver alerta alta pede justificativa (FR-5)'
            USING ERRCODE = 'check_violation';
    END IF;
    NEW.quando := clock_timestamp();
    RETURN NEW;
END
$$;

CREATE TRIGGER alerta_evento_conferir BEFORE INSERT ON nucleo.alerta_evento
    FOR EACH ROW EXECUTE FUNCTION nucleo.conferir_evento();

-- A assinatura liga objeto e versão (AD-30). A versão é texto montado pelo
-- núcleo (`nucleo/assinatura.versao_do_plano`), e nunca vazia: assinatura
-- sem versão valeria para qualquer versão, que é o que esta tabela proíbe.
CREATE TABLE nucleo.assinatura (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- O que se assina, com o módulo dono no prefixo (AD-31):
    -- `plano.aprovacao_fisica`, `plano.duplo_check`.
    tipo          text NOT NULL
        CHECK (tipo ~ '^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$'),
    objeto        text NOT NULL CHECK (objeto <> ''),
    objeto_versao text NOT NULL CHECK (objeto_versao ~ '\S'),
    perfil        text NOT NULL CHECK (perfil <> ''),
    quando        timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX assinatura_objeto ON nucleo.assinatura (tipo, objeto);

INSERT INTO nucleo.dono_tabela VALUES
    ('nucleo.alerta', 'nucleo'),
    ('nucleo.alerta_evento', 'nucleo'),
    ('nucleo.assinatura', 'nucleo');
