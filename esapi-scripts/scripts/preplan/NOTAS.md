# PrePlan

> Notas das rodadas com o usuário. Vieram da memória do Claude em 22/10/2026, sem resumo;
> os caminhos e ramos citados antes dessa data são os da época (o script agora mora nesta pasta, no `main`).

Desde 03/09/2026, repo `c:\Users\geova\Documents\isocentro\programa\preplan` (remoto `github.com/geovanipena/preplan`, privado, desde 22/10/2026). Plug-in ESAPI em C# (`PrePlan.esapi.dll`), irmão do
[Anéis de otimização](../aneis-otimizacao/NOTAS.md) mas repo separado — provavelmente vira
standalone lá na frente.

Monta o esqueleto de um caso novo numa janela só: plano no curso, prescrição,
**VMAT (2 arcos 181→179 / 179→181, colimadores 30 e 330)** ou **N campos fixos
igualmente espaçados a partir de 180°**, isocentro (centro do alvo ou origem do
usuário) e `FitCollimatorToStructure`. Mais o NTO automático.

**Decisões, com o porquê:**
- **Para antes de otimizar.** A Varian só libera `Optimize`/`CalculateDose` em
  aplicativo standalone; num plug-in dentro do Eclipse a recusa vem em execução.
  E o passo que decide dose fica com quem responde por ele.
- **Não cria curso, não escolhe modelo de cálculo, não cria objetivo de alvo** —
  decisões e strings do serviço. A mensagem final lista tudo isso como "FALTA,
  antes de otimizar".
- **Máquina colhida, nunca inventada**: a ESAPI 15.6 não tem catálogo de
  máquinas. A lista vem dos planos do próprio paciente + histórico em
  `%LOCALAPPDATA%\PrePlan\maquinas.txt`, e só entra ali o que funcionou.
- **Depois da primeira escrita nada aborta**: cada passo tem seu `try` e a falha
  vira aviso; o script não apaga o plano que criou.

**Estado em 03/09/2026: compila limpo, binário conferido, NÃO rodou no Eclipse.**
A conferir na primeira rodada, em ordem de risco: `FitCollimatorToStructure` num
feixe VMAT; `AddVMATBeam` com 178 CPs e pesos iguais; os Ids de técnica `ARC` e
`STATIC`; o limite de tamanho do Id de plano/campo.

Armadilhas da API em a skill `esapi` (armadilhas).
