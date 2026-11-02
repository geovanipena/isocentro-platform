# 5 Campos — field-in-field (hotspot)

- `5Campos_Hotspot_FiF.cs` (+ `.csproj`) — DLL gravável, **field-in-field nos 5 campos**
  (origem: projeto Cervix, renomeado). Reduz hotspot ≥107% mantendo D95 = 100% do Rx. Os subcampos são
  cópias manuais feitas na Eclipse, nomeadas `<campo>.0`, `.1`, `.2` (criar feixe por API falha com
  "Several MLCs found for technique 'STATIC'"); campo sem cópias mantém o peso. Com n subcampos, `.i`
  bloqueia a região acima de 107% + (Dmax−107%)·i/n; pesos otimizados pelas doses por feixe (`Beam.Dose`),
  mínimo 5 UM por feixe (linearidade), renormalização a D95 = 100% e remoção das estruturas `zFIF_*`.
  Máquinas aceitas: 600CD, 6EX, TrueBeamSN1001. Compilar com **`dotnet msbuild`** (usa C# 7; o MSBuild do
  .NET Framework não compila). **Relatório ainda em inglês** — pendente traduzir para pt-BR.
  **VALIDAR EXAUSTIVAMENTE em ambiente não-clínico antes de uso real.**

**Compilar:** DLL: `dotnet msbuild 5Campos_Hotspot_FiF.csproj /p:Configuration=Release` nesta pasta (C# 7).

Histórico das rodadas e o que está pendente: [NOTAS.md](NOTAS.md).
