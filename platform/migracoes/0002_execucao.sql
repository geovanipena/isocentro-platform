-- 0002 — a execução da verificação (R-20).
--
-- Fonte: AD-14 (contrato), AD-15 (ESAPI por JSON), AD-28 (execução vigente)
-- da espinha; CAP-8 e CAP-9 da spec Fundação; FR-39 (proveniência).
--
-- Grava só pelo `nucleo.gravar` (dono: o núcleo). Os valores fixos repetem os
-- do `isocentro/nucleo/verificacao.py`: o Python recusa antes, com motivo
-- legível; a restrição daqui é a garantia para quem pular o Python.

CREATE TABLE nucleo.execucao (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    verificacao_id     text NOT NULL
        CHECK (verificacao_id ~ '^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$'),
    verificacao_versao text NOT NULL CHECK (verificacao_versao <> ''),
    -- `podada` não executa (VerificacaoPodada), então não chega aqui.
    estado             text NOT NULL CHECK (estado IN ('sombra', 'ativa')),
    severidade         text NOT NULL
        CHECK (severidade IN ('alta', 'atencao', 'informativo')),
    origem             text NOT NULL CHECK (origem IN ('producao', 'semeado')),
    objeto             text NOT NULL CHECK (objeto <> ''),
    -- Pode ser vazia: sem versão o motor devolve `indeterminado`, e essa
    -- execução também tem de ficar registrada.
    objeto_versao      text NOT NULL,
    degrau             text NOT NULL
        CHECK (degrau IN ('variandw', 'espelho', 'csv', 'dicom', 'esapi_json')),
    data_origem        text CHECK (data_origem <> ''),
    arquivo            text CHECK (arquivo <> ''),
    checksum           text CHECK (checksum ~ '^[0-9a-f]{64}$'),
    resultado          text NOT NULL CHECK (resultado IN
        ('conforme', 'nao_conforme', 'nao_aplicavel', 'indeterminado', 'erro')),
    motivo             text NOT NULL,
    evidencia          jsonb NOT NULL CHECK (jsonb_typeof(evidencia) = 'object'),
    quando             timestamptz NOT NULL,

    CONSTRAINT execucao_motivo_obrigatorio
        CHECK (resultado NOT IN ('indeterminado', 'erro') OR motivo <> ''),
    -- FR-39: o nome sem hash não prova que o arquivo é o mesmo, e o hash sem
    -- nome não diz onde procurar o arquivo para conferir.
    CONSTRAINT execucao_arquivo_com_checksum
        CHECK ((arquivo IS NULL) = (checksum IS NULL)),
    CONSTRAINT execucao_degrau_de_arquivo_com_arquivo
        CHECK (degrau NOT IN ('dicom', 'esapi_json') OR arquivo IS NOT NULL),
    CONSTRAINT execucao_degrau_de_banco_com_data
        CHECK (degrau NOT IN ('variandw', 'espelho', 'csv')
               OR data_origem IS NOT NULL)
);

-- A busca da vigente (AD-28) é sempre por esta chave.
CREATE INDEX execucao_chave
    ON nucleo.execucao (verificacao_id, origem, objeto, objeto_versao);
-- E a "vigente" se calcula pelo log (quem substitui quem): sem este índice,
-- cada busca varreria o log inteiro.
CREATE INDEX log_substitui ON nucleo.log (tabela, substitui)
    WHERE substitui IS NOT NULL;

INSERT INTO nucleo.dono_tabela VALUES ('nucleo.execucao', 'nucleo');
