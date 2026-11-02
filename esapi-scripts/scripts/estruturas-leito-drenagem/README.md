# Estruturas de otimização — leito prostático

- `EstruturasOpt_Leito_Drenagem.cs` (+ `.csproj`) — DLL gravável, caso **Leito Prostático**
  (boost `PTV_52`): cria `PTV_44_opt`, `anel_1-20`, `anel_20-40`. x64, .NET Framework 4.5.2, DLLs da Varian
  via `HintPath` em `lib/` (raiz) (fora do git — copiar do GAC do servidor antes de compilar).
  **VALIDAR EXAUSTIVAMENTE em ambiente não-clínico antes de uso real** — geometria ainda não confirmada em
  caso real.

**Compilar:** DLL: `MSBuild.exe EstruturasOpt_Leito_Drenagem.csproj /p:Configuration=Release` nesta pasta.
