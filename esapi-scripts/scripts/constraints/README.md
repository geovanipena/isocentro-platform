# Constraints Clinica 2026

- `Constraints_Clinica_2026.cs` (~120K, antigo `Constraints_Astro_e_Timmerman.cs`) — 3 publicações:
  ASTRO 2025 + Timmerman + Consenso Brasileiro de Mama (`BuildBrazilBreast`, 8 trials, Site "Mama").
  `aHeart` já consolidado em `ALS_HEART`. Pendência aberta: demais literais de alias de órgão duplicados
  entre métodos (`aEso`, `aRib`/`aRibs`, `aSkin`, `aSto`, `aDuo`, `aFemD`/`aFemurD`, `aFemE`/`aFemurE`) —
  consolidação para `static readonly` em andamento. Aliases com conteúdo divergente (`aLiver`, `aKid`,
  `aLung`) aguardam julgamento clínico do Geovani — merge muda comportamento. Pulmão ipsi de mama casa o
  o pulmão do lado do alvo por geometria (`ResolveIpsiLung`/`TargetRefX`, X do sistema do paciente).

**Compilar:** single-file (somente leitura): publicar o `.cs`.
