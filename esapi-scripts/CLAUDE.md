# Scripts ESAPI — Clinica / Rede · Física Médica

Biblioteca de scripts **ESAPI (C#)** para **Varian Eclipse 15.6+**, ambiente **Citrix**, radioterapia.
Físico responsável: **Geovani Pena**. Código, relatórios e respostas em **pt-BR com UTF-8 acentuado real**
(acentos de verdade — nunca fallback ASCII nem entidades HTML).

> Este arquivo é o contrato de comportamento do projeto para o Claude Code. Leia-o inteiro antes da
> primeira tarefa da sessão. A skill de usuário `esapi` (armadilhas da API, doc oficial) complementa este manual.

---

## 0. Princípios de trabalho default (SEMPRE aplicar, sem pedido explícito)

Valem para **toda** tarefa pertinente. São princípios de comportamento do projeto (resumidos aqui e
detalhados nas §2/§5/§7). Se um dia forem formalizados como arquivos de skill, ficam em `.claude/skills/`
— **hoje essa pasta não existe no repo**; a orientação abaixo é o contrato:

- **`karpathy-guidelines`** — *como* escrever/alterar código: pensar antes de codar, mudança **cirúrgica**,
  mínimo necessário, explicitar suposições e trade-offs, definir critério de sucesso **verificável** antes
  de agir. É a lei de comportamento do projeto.
- **`web-design-guidelines`** — camada de decisão visual dos relatórios HTML: hierarquia, tipografia,
  grade 8px, contraste WCAG AA, cor semântica.
- **`ui-ux-pro-max`** — implementação de interfaces clínicas densas: tabelas densas, badges de status,
  cards, padrões de prazo, design system em `:root`. Skill **primária** dos relatórios.

Ordem prática ao produzir relatório: **karpathy** (como mexer) → **ui-ux-pro-max** (implementar) →
**web-design-guidelines** (revisar hierarquia/contraste). As skills orientam a *evolução* da identidade
visual; a `#region PADRÃO CLINICA` permanece idêntica entre arquivos até uma atualização deliberada e
replicada em todos.

---

## 1. Comportamento no repositório (economia de tokens)

- **Não reler arquivos inteiros.** Trabalhar a partir deste `CLAUDE.md` + `scripts/_template/Template_Clinica.cs`.
  Abrir apenas a região/método relevante quando faltar contexto (`grep`/leitura de trecho, não o arquivo todo).
- Aplicar mudança de forma **cirúrgica** por diff; não reprocessar o script inteiro.
- Respostas **objetivas**. Não reescrever blocos estáveis; alterar só o necessário.
- **Explicitar suposições** em vez de assumir em silêncio. Havendo duas leituras de um requisito, apresentar
  as duas — não escolher calado.

---

## 2. Fluxo de trabalho (karpathy)

Para toda tarefa não-trivial, declarar brevemente antes de agir:

```
1. [Passo] → verificar: [critério]
2. [Passo] → verificar: [critério]
```

- **"Adicionar constraint X"** → embutir tabela X + avaliador; verificar: métrica lida do plano bate com a
  publicação em um caso conhecido.
- **"Corrigir bug Y"** → reproduzir a condição; verificar: o caso que falhava agora passa.
- Critério fraco ("fazer funcionar") gera retrabalho. Critério forte permite iterar sozinho.

---

## 3. Arquitetura — dois modos de entrega, uma espinha dorsal

`Template_Clinica.cs` vale para os DOIS modos; muda-se só o *empacotamento*, nunca o template.

- **Somente-leitura → plug-in single-file** (`.cs`). Eclipse 15.6 **não** suporta single-file gravável
  (gravável chegou na v16.1).
- **Grava/cria/edita estruturas → DLL binária `.esapi.dll`** via MSBuild, .NET Framework 4.5.2 x64, DLLs da
  GAC em `C:\Windows\Microsoft.NET\assembly\GAC_64\`. Requer `public class Script` em `namespace VMS.TPS`
  (carregada por reflexão). Inserir `[assembly: ESAPIScript(IsWriteable = true)]` **sempre após os `using`**.
  - Erro típico "entry type not found" = classe `Script` sem modificador `public` (single-file tolera
    `internal`; DLL binária exige `public`).
- **Dados embutidos no código** (constraints/config) — nunca CSV/rede (Citrix-safe).

---

## 4. Template obrigatório

- **Ponto de partida único:** `scripts/_template/Template_Clinica.cs`. Copiar e preencher **apenas** as áreas
  marcadas **PREENCHER**; a `#region PADRÃO CLINICA` permanece **IDÊNTICA**.
- **Preencher só:** `REPORT_TITLE`, `REPORT_SUB`, `FILE_TAG`, config específica, lógica em `Execute`,
  tabela específica em `BuildReport`, textos do `Footer`.
- **Não editar** dentro da região: marca/paleta, `ST_*`, `HtmlOpen`/`Header`/`PatientCard`/`SummaryPills`/
  `ActionBlock`/`Footer`/`BuildStyle`, `Esc`/`Fmt`/`Str`/`Safe`, `BuildLogoTag`, `WriteAndOpen`.
- Atualização de identidade visual: editar em **UM** script e **replicar o bloco byte-a-byte** nos demais,
  numa única entrega em lote. Rodar `tools/check_region_parity.py` depois — deve dar paridade total.
- Ler apenas a região do arquivo existente — nunca inventar um esqueleto paralelo.

### Região compartilhada — delimitadores exatos
```
início: //  #region  PADRÃO CLINICA  —  bloco compartilhado (NÃO EDITAR AQUI)
fim:    //  #endregion  PADRÃO CLINICA
```
**Hash de referência atual (v3.1)** — 327 linhas, idêntico nos 5 arquivos:
- MD5 `a5f117bdfb8fc62aec4a22d56ae2506f`
- SHA-256 `7e14d3ae26d4d52818e92ae2840ceb16d7cabf82b89be35ce39c6e2c65684503`

v3.1 substituiu `Process.Start(path)` puro em `WriteAndOpen` por `AbrirNoNavegador()`: tenta
Edge/Chrome/Firefox/IE conhecidos via `.exe` direto antes de recair na associação de arquivo do SO —
a associação `.html` do Citrix é inconsistente entre sessões publicadas e às vezes abre "Abrir com" /
salva como `.txt` em vez do navegador.

Se o hash de um arquivo divergir dos demais → a região foi editada indevidamente ou dessincronizada.

---

## 5. Convenções de código

- `namespace VMS.TPS`; `public class Script`; entrada em `Execute(ScriptContext ...)`.
- Toda config: **`static readonly`** (nunca `const` → evita CS0162/CS0429 tratados como erro).
- **C# 5** no single-file: sem interpolação de string (`$"..."`), sem membros de corpo-expressão (`=>`).
- Status: `OK / ATN / FAIL / CHK / NA`. Linha via `Add(categoria, item, status, detalhe)`.
- Operadores nos relatórios: **Unicode `\u2264`/`\u2265` (≤/≥)** direto na string — NUNCA entidades HTML
  (evita duplo-escape via `Esc()`).

### Armadilhas conhecidas (custosas de redescobrir)
- **Ordem de init de `static readonly`:** alias como `OK = ST_OK` captura `null` se `ST_*` vier depois no
  arquivo. Compila sem erro no Eclipse e exibe todos os status errados em runtime. → Inicializar aliases com
  **literal** (`OK = "OK"`) ou declará-los textualmente **após** o campo referenciado.
- **`static readonly` não usado → CS0414 fatal** (warning-as-error). Todo token de paleta declarado deve ser
  consumido; `BuildStyle()` referencia por **concatenação**, não hardcode hex inline.
- **Nada de `switch` sobre status** no single-file → usar cadeias `if/else`.

---

## 6. Estruturas

- Casamento **acento- e caixa-insensível** via `Norm()` (remove diacríticos + `ToUpperInvariant`); rótulos de
  exibição mantêm acentuação pt-BR. `Norm()` é lógica **específica** → fica **fora** da `#region PADRÃO CLINICA`.
- Nomes canônicos = template Eclipse da clínica; casar por **dicionário de aliases**.
- Estruturas laterais (Fêmur D / Fêmur E) usam aliases **sem cruzamento** entre lados.
- **Agregação bilateral:** média ponderada por volume para métricas de dose; volumes somados para métricas-V;
  volume frio combinado para métricas-CV.
- **Julgamento clínico veta merge automático:** aliases do mesmo órgão com conteúdo literal diferente NÃO
  podem ser fundidos mecanicamente — muda o casamento de estrutura e exige assinatura do físico. Escalar,
  não resolver sozinho.

---

## 7. Relatórios HTML (Citrix)

- Sequência fixa: `HtmlOpen → Header → PatientCard → SummaryPills → ActionBlock → tabela específica →
  Footer → HtmlClose` → `WriteAndOpen`.
- HTML gravado no temp do servidor e aberto client-side → **caminhos de imagem externos quebram**. Logo
  **sempre base64** via `BuildLogoTag()` (lê o PNG server-side em tempo de execução e embute data URI). Abrir
  com `Process.Start`.
- **Qualidade visual:** legibilidade acima de decoração; cor de status semanticamente correta (nunca vermelho
  para info neutra); status = **cor + rótulo** (nunca só cor); linhas de tabela ≥ 40px; contraste de corpo
  ≥ 4.5:1; sem animação que atrapalhe leitura clínica.

---

## 8. Marca Clinica

Ciano `#00A6DB` · Menta `#11E7A2` · Teal `#00708F` · Teal escuro `#005E78` · logo base64 (`logo_clinica.png`).

---

## 9. Referências clínicas

ASTRO Consensus 2025 (Puckett et al.); Timmerman 2021 SBRT/SABR; ICRU Report 83; AAPM TG-275, TG-218,
TG-263; McNiven et al. Med Phys 2010; Masi et al. Med Phys 2013.

---

## 10. Deploy

`\\srvariadb\va_data$\ProgramData\Vision\PublishedScripts`

### DLL gravável — ciclo de build (NÃO republicar a cada build)

```
powershell -ExecutionPolicy Bypass -File tools\build_esapi.ps1 `
    -Projeto "scripts\<pasta>\<Script>.csproj" -Destino "<pasta de scripts>"
```

A Eclipse identifica o script por **nome + versão do assembly**, e a autorização
de **escrita** está amarrada ao registro publicado/aprovado dessa identidade.
Consequências, todas descobertas na marra:

- **`AssemblyVersion` FIXA, nunca wildcard (`1.0.*`).** Wildcard muda a versão a
  cada build; a DLL deixa de casar com qualquer registro aprovado e a primeira
  gravação estoura com `Argument 'Assembly scriptAssembly' can not be null`.
- **Enquanto nome e versão não mudarem, é só sobrescrever a DLL na pasta.**
  Publicar de novo devolve `o script ... já existe` — e não era necessário.
- **Subir a versão é ato deliberado de release:** aí sim publicar, **aprovar**
  (publicar não basta para gravável) e só então aposentar a anterior.
- **"Aposentar" não libera a identidade.** O registro continua no banco
  ocupando aquele nome+versão, então aquela versão nunca mais pode ser
  publicada. Durante a iteração, não aposente nada.
- Script gravável roda normalmente a partir de **pasta** (não precisa ser
  "Scripts do sistema") — desde que a identidade esteja registrada e aprovada.

### Armadilhas de API em script gravável

- `CanAddStructure()` só responde corretamente **depois** de
  `BeginModifications()`; chamado antes, retorna `false` mesmo quando a
  estrutura poderia ser criada.
- `SegmentVolume` **não expõe volume** — só `Structure.Volume`. Para medir uma
  geometria candidata, atribua a uma estrutura de trabalho e leia de lá.
- `SegmentVolume` que passou por uma estrutura **removida** vira referência
  morta: atribuí-la depois estoura com `External component has thrown an
  exception`. Guarde o parâmetro e **recalcule**, nunca cacheie o objeto.
- `Margin`/`AsymmetricMargin` têm teto de **50 mm por chamada**. Erosão/expansão
  maiores se fazem em **passos encadeados** (a operação é aditiva).

---

## 11. Estado atual da biblioteca

### Scripts — uma pasta por script em `scripts/`

O detalhe de cada um (função, ressalvas, como compilar) está no `README.md` da pasta; o histórico das
rodadas com o Eclipse/ARIA real, no `NOTAS.md` dela.

| pasta | script | tipo | o quê |
|---|---|---|---|
| `constraints/` | `Constraints_Clinica_2026.cs` | single-file | constraints DVH: ASTRO 2025, Timmerman, Consenso Brasileiro de Mama, CORSAIR |
| `constraints-arquivos/` | `Constraints_Arquivos_Clinica.cs` | single-file | avaliador de constraints DVH |
| `plano-indices-qualidade/` | `Plano_Índices_e_Qualidade.cs` | single-file | ICRU 83 + complexidade de feixe |
| `plano-pre-tratamento/` | `Plano_Pré-Tratamento.cs` | single-file | checklist de pré-tratamento (aceita PlanSum) |
| `_template/` | `Template_Clinica.cs` | — | ponto de partida de todo script novo |
| `estruturas-leito-drenagem/` | `EstruturasOpt_Leito_Drenagem` | DLL gravável | PTV_opt e anéis, leito prostático |
| `estruturas-prostata/` | `EstruturasOpt_Prostata` | DLL gravável | PTV_opt e anéis, próstata |
| `estruturas-bexiga-minima/` | `EstruturasOpt_Bexiga_Minima` | DLL gravável | `Bexiga_Min` por erosão, protegendo PTV + margem |
| `5-campos-fif/` | `5Campos_Hotspot_FiF` | DLL gravável | field-in-field nos 5 campos |
| `proprietario-tarefas/` | `Proprietario_Tarefas` | DLL (UI Automation) | assume as tarefas de Care Path no ARIA |
| `preplan/` | `PrePlan` | DLL gravável + exe | monta plano, campos, isocentro e colimador |
| `aneis-otimizacao/` | `AneisOtimizacao` | DLL gravável | Anel1/Anel2 a partir da soma dos PTVs |

### Em progresso / fora do repo (trazer quando retomar)
- `Constraints_Publicacoes.cs` — single-file read-only; ASTRO 2025 + Timmerman; ~1.600 linhas, **UTF-8 BOM**.
  Aberto: (1) estrutura de pulmão combinada para constraints bilaterais (hoje usa pulmão inteiro, impreciso
  para SBRT); (2) resolução de PTV quando há múltiplos PTVs (usa `plan.TargetVolumeID` filtrado só a PTV,
  nunca CTV/GTV).
- `Restricoes_DVH.cs` — interrompido; frações Timmerman (1/2/3/4/5/8 fx) + 25 tabelas ASTRO; diálogo WinForms.
  Falta: `ParseThreshold`, avaliador de métrica, diálogo WinForms, `BuildLogoTag`, render HTML, `Execute()`.

### No horizonte
Portal dosimetry (análise gamma); export JSON de métricas DVH (auditoria/pesquisa); extração em lote de
métricas de qualidade; validação RapidPlan/KBP; skill `skill-creator` encapsulando o PADRÃO CLINICA.
- **v3.1 candidato:** correção de contraste de badge (`StatusBg`/`StatusFg` — atuais OK 3.69:1, ATENÇÃO
  3.17:1, N/A 2.96:1, todos reprovam WCAG AA).
- Deferido v3.x (exige markup fora de `BuildStyle()`): cabeçalho de tabela sticky, zebra striping. Google
  Fonts excluído (recurso externo é risco no Citrix).

---

## 12. Referência ESAPI

Documentação XML das DLLs da Varian em `vendor/esapi-docs/` (`VMS_TPS_Common_Model_API.xml`,
`VMS_TPS_Common_Model_Types.xml`) — FileVersion 15.6.8.73, AssemblyVersion 1.0.300.11. Consultar para
assinaturas/membros da API em vez de assumir.

---

## 13. Verificação antes de commitar

Tudo de uma vez:
```
powershell -ExecutionPolicy Bypass -File tools\check_all.ps1
```
Ou individualmente:
```
python  tools/check_region_parity.py    # paridade byte-a-byte da #region PADRÃO CLINICA
python  tools/check_csharp_traps.py     # armadilhas do single-file C# 5 (const, $"", =>, entidades ≤/≥)
powershell -File tools\typecheck.ps1    # compila cada single-file em C#5/net452 (precisa das DLLs em lib/)
bash    tools/check_encoding.sh         # BOM / fim-de-linha / balanceamento de chaves
```
Toda alteração que toque a região exige paridade verde nos 5 arquivos antes do commit.

O hook **PostToolUse** (`.claude/settings.json`) já roda paridade + armadilhas C# 5 + typecheck a cada
edição de `scripts/<pasta>/*.cs` — mas só depois de ativar a config uma vez via `/hooks` (ou reiniciar). As DLLs
Varian de `lib/` ficam fora do git (ver `lib/README.md`); sem elas o typecheck é pulado.

---

## 14. Organização e registro (automático, sem esperar pedido)

- **Um script = uma pasta** em `scripts/`, com `README.md` (função, estado, como compilar). Script novo
  nasce copiando `_template/` para uma pasta nova. Pasta com `.csproj` é plug-in DLL e fica fora das
  verificações de single-file.
- **Um ramo só, o `main`.** Frente de trabalho = ramo curto que volta para o `main` ao fechar. Os ramos
  antigos por script estão nas tags `arquivo/*`.
- **Ao fim de cada rodada** (versão nova, teste no Eclipse/ARIA real, decisão do usuário): atualizar o
  `NOTAS.md` da pasta (nova entrada no topo) e a linha de estado do `README.md` — no mesmo commit da
  mudança. Este arquivo só muda quando muda uma regra que vale para todos.
- **Renomear script** = `git mv` da pasta e dos arquivos, e atualizar a tabela acima. O `AssemblyName` é
  independente do nome da pasta.
