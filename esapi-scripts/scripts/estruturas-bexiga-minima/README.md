# Estruturas de otimização — bexiga mínima

- `EstruturasOpt_Bexiga_Minima.cs` (+ `.csproj`) — DLL gravável. Gera `Bexiga_Min`, aproximação geométrica do
  volume mínimo de bexiga aceito para o plano, por erosão da bexiga contornada (cheia):
  `V_alvo = MAX(MinimoGlobalCc, VolumeInicialCc × FracaoMinimaRelativa)`, com busca binária da erosão
  (encadeada em passos de até 50 mm). **Restrição dura:** a bexiga dentro do PTV + margem (padrão 15 mm)
  nunca é reduzida — `Bexiga_Min = (bexiga reduzida) ∪ (bexiga ∩ (PTV + margem))`. Bexiga já abaixo do
  alvo = cópia sem redução, com aviso. Sem PTV, pede confirmação antes de seguir sem proteção.
  O cabeçalho do `.cs` explica o porquê de cada regra.
  **VALIDAR EXAUSTIVAMENTE em ambiente não-clínico antes de uso real.**

**Compilar e entregar:** `powershell -ExecutionPolicy Bypass -File tools\build_esapi.ps1 -Projeto scripts\estruturas-bexiga-minima\EstruturasOpt_Bexiga_Minima.csproj -Destino <pasta de scripts>`
(ver “DLL gravável — ciclo de build” no `CLAUDE.md`: `AssemblyVersion` fixa, sobrescrever a DLL, não republicar).

Histórico: ramo `bexiga-minima` (21/09/2026), PR #13; preservado na tag `arquivo/bexiga-minima`.
