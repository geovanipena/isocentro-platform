# Estruturas auxiliares (anéis de otimização)

> Notas das rodadas com o usuário. Vieram da memória do Claude em 22/10/2026, sem resumo;
> os caminhos e ramos citados antes dessa data são os da época (o script agora mora nesta pasta, no `main`).

Desde 03/09/2026, projeto novo em `c:\Users\geova\Documents\isocentro\programa\Estruturas-auxiliares_API`
(GitHub: `geovanipena/Estruturas-auxiliares_API`), **separado do ficha-py** porque
é C#/.NET, não Python.

É um **binary plug-in do Eclipse (ESAPI)** que cria dois anéis de otimização:
`Anel1` (soma dos PTVs +2mm a +20mm) e `Anel2` (+20mm a +40mm), ambos cortados
pelo contorno externo. O usuário tem licença **Eclipse Automation**
(write-enabled), confirmado por ele.

**Decisões tomadas com o usuário, com o porquê:**
- Os PTVs são **escolhidos numa janela**, não por filtro de nome ou tipo — um
  PTV a mais ou a menos muda os dois anéis em silêncio, e `PTV_eval`/`PTV_old`
  poluiriam qualquer filtro automático.
- Anéis cortados por `And(EXTERNAL)` — sem isso um anel de 4cm sai da pele.
- O externo do Anel1 é igual ao interno do Anel2 de propósito: encostam sem
  lacuna nem sobreposição.

**Escopo atual: só essas duas estruturas.** O usuário falou em 4 e depois
recuou ("vamos só com duas por enquanto") — as outras duas ficaram em aberto.

**Funcionando desde 03/09/2026**: rodou no Eclipse do serviço e criou os dois
anéis. As DLLs da ESAPI 15.6 estão em `lib/` (vieram de `~/Downloads`, fora do
git por serem licenciadas — o repo era público; privado desde 22/10/2026).

Compilar com `tools/compilar.ps1`; `-Sufixo v3` versiona o nome do assembly,
que é o que destrava a reimportação no Eclipse.

Ver a skill `esapi` (armadilhas) para as armadilhas da API.
