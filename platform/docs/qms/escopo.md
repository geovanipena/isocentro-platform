# Escopo do sistema

> Decidido pelo físico responsável (Geovani Pena) em 13/10/2026, a partir de
> um levantamento feito no código dos três repositórios. Cada linha cita a
> fonte do levantamento. Os agentes do BMad tratam este arquivo como fato; o
> que está em "Em aberto" eles devem perguntar, não presumir.

## Regra de decisão

Fixada pelo físico responsável em 26/10/2026: **toda decisão do software se
apoia numa referência**; havendo duas ou mais que se aplicam, vale **a mais
restritiva**. O que não tem base bibliográfica não é decidido calado: vai
para a lista de discussão no serviço
(`docs/planejamento/sistema-global/decisoes-sem-base.md`) e, até lá, o
software segue a opção mais conservadora disponível e diz que ela é
provisória.

## O que o sistema faz

O ISOCENTRO é o núcleo do sistema global. O PPR e os scripts ESAPI
entram nele aos poucos, como módulos; até lá, continuam nos próprios
repositórios.

| Módulo | Faz | Origem do dado | Fonte do levantamento |
| --- | --- | --- | --- |
| ISOCENTRO | Ficha técnica, capa, mapa de frações, alta e página de imagens, em PDF | DICOM-RT (TC, RP, RS, RD), lido localmente | `README.md`, "Fluxo de uso" |
| ISOCENTRO | Capa de tratamento | Data warehouse `variandw`, somente leitura → espelho → relatórios exportados | `CLAUDE.md`, "Regras do domínio" |
| ISOCENTRO | Registro versionado por paciente (JSON + PNG) | Gravado na pasta do paciente | `README.md`, "Registro versionado" |
| ISOCENTRO | Cálculo paralelo e aba Qualidade | Tabelas de feixe da máquina do plano; sem elas, demonstração sem veredito | `DESTINO.md`, pilar 3 |
| PPR | Plano de Proteção Radiológica em PDF; aba Vencimentos | Formulário e PDFs enviados pelo usuário | `ppr-streamlit/app.py` |
| Scripts ESAPI | Constraints de DVH, índices de qualidade, checklist pré-tratamento | Plano aberto no Eclipse, somente leitura | `scriptsvarian/CLAUDE.md`, §11 |
| Scripts ESAPI | Estruturas de otimização e field-in-field | Plano aberto no Eclipse, **com escrita** (DLL gravável) | idem |
| ISOCENTRO (Radioteradados) | Indicadores do serviço (núcleo RDC 20/2006 e camada operacional), lista de origem e relatório mensal agregado | `variandw`, somente leitura; classificação de encerramento gravada pelo próprio app | PRD Radioteradados (`docs/planejamento/sistema-global/radioteradados/`), incluído em 13/10/2026 |

## O que o sistema NÃO faz

- Não escreve no ARIA nem no data warehouse. Nenhum módulo grava no sistema
  clínico de registro.
- Não escreve no Eclipse, **exceto** por script ESAPI gravável que passou por
  validação em ambiente não clínico (ver "Fronteiras").
- Não envia dado pessoal (de paciente ou de funcionário) a serviço de
  terceiros. Decidido em 13/10/2026: a extração de ASOs do PPR, que hoje manda
  o texto do PDF para a API da Anthropic, passa a ser local (frente R-15).

## Usuários

Decidido pelo físico responsável em 26/10/2026 (frente R-16). Sete perfis;
cada pessoa tem um, sem troca na sessão. **Admin** é permissão da pessoa
(dá acesso às Configurações e não amplia os módulos que ela vê); **físico
responsável** é atributo da pessoa (vê as três clínicas), não perfil.

A tabela perfil → capacidades **mora no banco e é configurável pelo admin**
numa tabela de seleção em Configurações: a visibilidade de cada módulo **e**
as ações dentro dele (assinar, cadastrar, registrar). Toda mudança na tabela
é gravação como outra qualquer, com autor no log encadeado. O valor inicial é
a matriz abaixo (a de `EXPERIENCE.md`, "Perfil × módulo visível", com as
suposições aceitas); o admin ajusta depois.

| Perfil | Usa para (valor inicial) |
| --- | --- |
| Médico radioterapeuta | Radioteraficha (Virtual, Agenda); Plano (ver se o plano passou pelas conferências); Tratamento; Segurança do paciente (registra); Conhecimento |
| Físico | Todos os módulos: Radioteraficha inteiro; Plano (Aprovação Física, Duplo Check, cadastros); Tratamento (contagem de frações); GQ (cadastra testes, ações, carta); Segurança (registra, revisão periódica); Documentação (vencimentos, aferição); Software e sistemas; Indicadores; Conhecimento |
| Dosimetrista | Radioteraficha (Capa-Up, Virtual, Agenda); Plano (2ª checagem, Lista de Planejamento); Segurança (registra); Conhecimento |
| Técnico | Radioteraficha (Capa-Up, Virtual, Agenda); Tratamento; GQ (registra execução); Segurança (registra); Conhecimento |
| Enfermeiro | Radioteraficha (Capa-Up, Virtual, Agenda); Tratamento; Segurança (registra); Conhecimento |
| Recepcionista | Radioteraficha (Capa-Up, Virtual, Agenda); Segurança (registra); Conhecimento |
| SPR/gestão | GQ (só leitura); Segurança (registra, acompanha); Documentação (cadastra e acompanha); Indicadores; Conhecimento |

**Travas que nenhuma configuração desliga** (ficam no código e no banco, fora
da tabela): só o físico assina a Aprovação Física e o Duplo Check; o físico
do Duplo Check nunca é o da Aprovação Física (FR-20); ninguém assina em nome
de outro (FR-8); cada clínica vê só os próprios dados (NFR-6).

## Fronteiras

- **Lê, somente leitura:** data warehouse `variandw` do ARIA; DICOM vindo do
  TPS (arquivo e rede); plano aberto no Eclipse via ESAPI.
- **Escreve:** só no Eclipse, só por script ESAPI gravável (estruturas de
  otimização, pesos de campo), e só depois de validado em ambiente não
  clínico. A validação de cada script é registrada antes do primeiro uso
  real.
- **Grava o que produz:** na pasta do paciente (PDF e registro versionado) e
  ao lado do app (configuração e índices).
- **Banco central** (decidido em 19/10/2026, espinha da arquitetura; registrado
  aqui em 26/10/2026, frentes R-16 e G6): o estado do sistema — usuários,
  sessões, verificações, assinaturas, registros dos módulos e o log encadeado
  — passa a ser gravado no PostgreSQL 18 do servidor da clínica
  (`clinica-python01`), dentro da rede. É banco **do ISOCENTRO**, não o
  sistema clínico: a regra de nunca escrever no ARIA nem no `variandw`
  continua. Os JSON ao lado do app migram para ele por entidade, sem gravação
  dupla (AD-37).

## Em aberto

- Pasta do serviço onde ficam fichas e registros na rede da clínica.
- Critério e registro da validação em ambiente não clínico dos scripts
  graváveis (o que é testado, por quem, onde fica a evidência).
