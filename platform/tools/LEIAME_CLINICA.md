# Ferramentas que falam com a clínica (banco, ARIA, DICOM)

Saíram do `CLAUDE.md` em 08/09/2026. Não porque valham menos: porque o
`CLAUDE.md` entra em **toda** requisição da sessão e estas só
importam quando o assunto é banco ou DICOM. Eram ~970 tokens por turno —
em 40 turnos, 39 mil — pagos também nas sessões de PDF e de tela, que são
a maioria. É a mesma conta que quebrou o `NOTAS.md` em três arquivos,
aplicada ao arquivo que se paga mais vezes.

Carrega pela skill `/clinica`, ou lendo este arquivo direto.

---

## Regras de quem roda o que (vieram do `CLAUDE.md` em 22/10/2026)

**E a doc OFICIAL da Varian antes de escrever a chamada**, não depois de ela
falhar: `docs.developer.varian.com/api/15.6/` para ESAPI e para o data
warehouse. A reflexão nas DLLs dá a FORMA da
chamada; só a doc diz o que os parâmetros esperam — e é aí que o erro dói, uma
ida à clínica por vez.

**O que exige identidade de rede vai SEMPRE pelo `.bat`** (combinado em
04/09/2026), nunca `python tools/x.py` dentro de um `runas`: o console do
`runas` fecha ao terminar e o relatório se perde na hora exata em que importa.
**E avisar, em voz alta, quando chegou a hora de rodar um** — quem roda é o
usuário, e ele precisa saber que a bola está com ele, com o comando pronto para
copiar e o que conferir na saída.

**Depois que o usuário roda, ler o ARQUIVO, não pedir para colar** (achado em
25/09/2026, rodada do `resumo_mensal_por_maquina`): os `.bat` de diagnóstico
gravam a saída num caminho PREVISÍVEL (`%TEMP%\mapear_..._AAAAMMDD-HHMM.txt`,
o próprio `.bat` imprime o nome) — quem tem acesso ao disco da estação lê
direto por ali. Pedir para colar no chat é fazer à mão o que já dá para fazer
sozinho, e ainda arrisca um recorte cortado ou colado errado.

---

## As ferramentas

**`tools\checkup_clinica.bat`** — a que se roda quando a ida é UMA. Mede numa
rodada só tudo o que o app precisa da infraestrutura — identidade da máquina,
as 18 variáveis e de onde vieram, cada pasta (existe, lê, **escreve**), o banco
do DNS até a permissão **tabela a tabela**, e o DICOM inteiro: C-ECHO, C-FIND,
o censo do estudo, a porta do receptor, o firewall, e o `trazer()` de verdade,
ponta a ponta. `--ct` traz uma série de CT e diz quantos objetos, quantos MB e
quantos segundos ela custa; `--carga 4` pergunta se o daemon aceita várias
estações pedindo junto.

**O bloco 12 escreve o chamado**, separado por fase (agora / produção /
depois) e — o que importa mais — separando o que é da TI do que é **nosso**.
Cada item de pedido nasce da medida que o gerou: lista de pendências escrita à
mão envelhece na primeira mudança de degrau, e o texto do chamado passa a pedir
o que já foi resolvido.

Só leitura. Escreve em dois lugares e os dois se apagam: um arquivo de teste em
cada pasta que precisa aceitar escrita, e a pasta temporária onde o DICOM cai —
que o relatório NOMEIA, porque é dado de paciente.

**Na clínica ele vai como EXECUTÁVEL**, não como `.bat`: lá não há Python nem
o repositório. `python tools/gerar_checkup.py` gera o
`dist/CheckupClinica_AAAAMMDD.zip` — com o `LEIAME_CHECKUP.txt` dentro, porque
quem roda na estação não é quem escreveu isto — e o empacotador confere o que
já deu errado: os imports tardios que ficam de fora do pacote (falha **calada**
na clínica), o console em code page 850 que derruba bloco por acento, e
relatório de teste viajando no zip. O `.bat` continua valendo **aqui**, onde há
Python.

**Rodar nas DUAS pontas** — aqui e numa estação da clínica — e guardar os dois
arquivos. É a comparação entre eles que responde a pergunta que decide o custo
de produção: **o cadastro do nosso AE Title amarra IP?** Se amarrar, é um
chamado por estação, para sempre. O contexto inteiro do pedido está em
`docs/PEDIDO_TI.md`.

**`tools\sondar_estacao.ps1`** — a mesma medida, para a máquina onde **nada
executa**. PowerShell puro, e o C-ECHO é montado **byte a byte**: monta o
A-ASSOCIATE-RQ do DICOM (PS3.8), lê a resposta e separa as três coisas que o
telefone confunde — "não chega", "chega e recusa o NOSSO AE" (só a TI resolve),
"chega e recusa o AE do ARIA" (erro de parâmetro nosso). Medido contra servidor
DICOM de verdade em 10/09/2026, nos três desfechos.

Responde também a pergunta dos **dois domínios**, que nenhuma outra máquina
pode responder: a conta `REDE` consegue provar quem é para o SQL do
`CLINICA`? Usa `System.Data.SqlClient` com `Integrated Security` — a mesma
autenticação do app, sem `sqlcmd` e sem driver ODBC.

**`python tools/gravar_banco.py`** — grava o **banco local**: pergunta ao
`variandw`, uma vez, tudo o que o app pergunta sobre os pacientes que já estão
em `TCs_Teste/`, e guarda as respostas cruas num SQLite que o `banco_local.py`
reproduz depois **sem rede**. É o que permite mexer na Capa e na Ficha Virtual
fora da clínica — sem ele, esta máquina (fora do domínio, SSPI recusado) não tem
banco nenhum e a Ficha Virtual simplesmente não existe.

Gravar exige identidade de rede: `runas /netonly /user:CLINICA\geovani.pena
"…\tools\gravar_banco.bat"`. Usar não exige nada:
`tools\rodar_com_banco_local.bat`. O dado é **congelado no dia da gravação** e a
tela anuncia isso — a Capa sai com aviso de SIMULAÇÃO em primeiro lugar e a
origem vira `banco LOCAL gravado`, pela mesma regra da capa que veio de reserva.
Consulta cujo SQL mudou depois da gravação **falha** em vez de responder a
pergunta antiga.

**`python tools/atividades.py`** — pergunta ao `variandw` **que tabelas de
atividade existem** (as do ARIA: care path, tarefa, "Documentação"), lista as
colunas de cada uma, amostra os valores das pequenas e procura a palavra. Não
tem SQL de atividade escrito de propósito: o nome dessas tabelas muda de versão
para versão do ARIA, e consulta montada sobre chute devolve lista com cara de
certa. Só leitura, e com duas travas — tabela grande é FATO (sai com contagem e
colunas, não é varrida) e coluna de identidade ou texto livre não é amostrada.
Exige identidade de rede, como o gravador: `runas /netonly` +
`tools\atividades.bat`, que já grava o relatório em arquivo porque o console do
`runas` fecha. **O arquivo cai em `relatorios_ferramentas/`**, ao lado do código —
vale para as três ferramentas daqui, e o nome ganha data e hora quando já existe
um relatório com aquele nome: nenhuma delas sobrescreve o que a rodada anterior
trouxe.

**`python tools/sondar_dicom.py`** — pergunta ao **DB Daemon do ARIA o que ele
implementa**: C-ECHO, C-FIND por `SOPInstanceUID`, C-GET e C-MOVE, cada degrau
tentado mesmo que o anterior falhe. A pergunta que ela existe para responder é
**"o servidor faz C-GET?"** — se fizer, os arquivos voltam pela mesma conexão e
a exportação não precisa de porta ouvindo, de regra de firewall para dentro,
nem de AE de destino cadastrado, e o pedido à TI encolhe para "cadastrem este
AE Title". Escolher entre C-GET e C-MOVE pelo manual seria decidir sobre o que
não se mediu, que é a armadilha do `mapear_gatilho.py` outra vez.

O UID vem do `gatilho_db` (o plano que a automação buscaria), não de um
palpite: UID inventado faz o C-FIND responder "0 achados" com toda a
legitimidade, e isso se parece com servidor quebrado. Os quatro endereços podem
ir por argumento (`--servidor`, `--ae-remoto`, `--ae-local`, `--ae-destino`)
para testar o que a TI disser **sem gravar nada em estação nenhuma**.

Duas identidades diferentes aqui: o DICOM autentica por AE Title e não precisa
de `runas`; o passo do UID fala com o `variandw` e precisa. Pelo
`tools\sondar_dicom.bat` com `runas /netonly` os dois funcionam de uma vez —
sem ele, `--uid` dispensa o banco.

**`tools\descobrir_dicom.bat`** (+ o `.ps1` ao lado) — roda **no servidor**
e descobre o que a sonda precisa saber: que serviços da Varian existem, **que
porta cada um ouve**, o que o registro e os arquivos de configuração dizem de
AE Title, e as regras de firewall das portas DICOM. **PowerShell puro**, porque
o servidor não tem Python nem o `.venv` — e nada se instala lá.

**Somente leitura, e isso é a característica principal**: não escreve nada além
do próprio relatório, não toca no banco do ARIA nem em dado de paciente, não
altera serviço, firewall, registro nem configuração. Roda sem administrador,
e o bloco que precisar de privilégio sai com o motivo escrito em vez de
derrubar os outros — meio relatório vale mais que nenhum, e diz o que refazer.

Existe pela mesma razão do `mapear_gatilho.py`: a alternativa era eu chutar um
caminho de instalação e mandar procurar lá. **O que ele NÃO descobre** é o AE
Title da estação que vai ler — esse não se lê, se cadastra, e cadastrar é
mudança de configuração em produção.

### As cinco do mapeamento e da conferência

Estas entraram aqui em 09/09/2026, pela `tools/manutencao.py`: existiam, tinham
docstring boa e não estavam em documentação nenhuma. Ferramenta que não está
onde se procura não é encontrada — é reescrita, e a segunda versão não sabe o
que a primeira já tinha medido.

**`tools\mapear_indicadores.bat`** (13/10/2026) — responde as quatro perguntas
de banco que o PRD do Radioteradados (aba de indicadores) deixou abertas: onde
mora o **motivo de encerramento** do curso (o abandono da RDC 20/2006 exclui
alta, óbito e mudança de conduta), onde mora a **frequência prescrita** (a
interrupção depende dela — e, se o campo não existir, o histograma das pausas
reais diz se dá para inferir), se **simulação e consulta** são atividades
registradas, e se a **braquiterapia** está no ARIA. **Só catálogos e
contagens, nenhuma linha de paciente** — o `tests/test_mapear_indicadores.py`
reprova a consulta que trouxer nome ou registro. `runas /netonly
/user:CLINICA\geovani.pena` + o `.bat`; a saída vai para
`%TEMP%\mapear_indicadores_AAAAMMDD-HHMM.txt`.

**`python tools/diagnostico_db.py`** — responde **por que não conecta**, em
camadas: DNS, porta, SSPI, permissão. É o primeiro a rodar quando o banco some,
porque cada camada falha com uma cara diferente e só a primeira delas é
"problema de rede". De máquina fora do domínio a autenticação integrada falha em
SSPI **antes** de tocar em permissão — a estação não consegue provar quem é, e
isso se parece com senha errada sem ser.

**`python tools/testar_reconexao.py`** — outra pergunta, e é a que importa
depois: **o app volta sozinho quando a conexão cai?** Nasceu do relato da
clínica de que só voltava entrando como admin e salvando a configuração, porque
`_salvar` chama `capa_db.esquecer()` de passagem. Exercita os quatro momentos na
ordem da sala: conectar, a queda (e o que a tela DIZ — tem de nomear a causa,
não "sem conexão"), a espera que CRESCE a cada falha seguida
(`capa_db.ESPERAS_APOS_FALHA_S`) e a volta, automática e manual.

**`python tools/mapear_dw.py`** — descobre em qual coluna de qual tabela mora
cada campo que sai impresso na **capa**. Existe para o `capa_db.py` não ser
escrito por adivinhação: nome de coluna inventado dá erro na hora, o que é bom;
coluna PARECIDA com a certa (`PatientId` × `PatientID` × `ctrPatientSer`)
devolve dado plausível e errado, e isso vira número errado numa folha grampeada
na ficha. Sem `--paciente` lê só metadados, nenhuma linha de paciente.

**`python tools/mapear_tratamento.py`** — o mesmo, para o que **aconteceu**, que
é o que a aba Ficha Virtual pergunta: fração atual, quem tratou, a que horas, em
qual acelerador, quanta dose já foi entregue. Risco maior que o do `mapear_dw`:
"frações planejadas" no lugar de "frações ENTREGUES" devolve um número plausível
e errado — e é justamente o número que o médico lê grande no meio da tela para
decidir. **Enquanto esta saída não existir, o SQL da aba não deve ser escrito**
(é o que segura as duas pendências de 19/08 no `NOTAS.md`).

Com **`--consulta`** ele responde outra pergunta, e é a que falta hoje: em vez
de descobrir o que EXISTE no DW, roda o `tratamento_db` de verdade e imprime a
LISTA do painel — curso a curso, com as marcas, quem a janela deixou de fora e
por quê, o filtro de cada médico, e o tempo da **função inteira** (seis
consultas: as três auxiliares da lista falham caladas, e o relatório escuta o
`logging` para dizer quando isso aconteceu). É a rodada que preenche o
`tratamento_db.LISTA_VERIFICADA_EM`, e a única em que este mapeador **lê nome e
registro de paciente** — a conferência contra o ARIA é nome por nome, e a saída
fica no `%TEMP%` da estação.

**`python tools/comparar_fontes.py`** — lê os MESMOS pacientes pelos dois
caminhos, banco e relatórios exportados, e mostra campo a campo onde diverge. É
a rede de segurança de ter trocado a fonte da capa: o erro que assusta não é o
que quebra, é o que devolve valor plausível e errado semanas depois, no papel.
**Divergência não é necessariamente erro do banco** — o CSV é o retrato do dia
da exportação, e o banco é hoje.

As cinco precisam de identidade de rede: vão pelo `.bat` ao lado, nunca por
`python tools/x.py` dentro de um `runas` — ver a regra logo abaixo.

---

## As duas regras que valem sempre que uma destas roda

Estas ficaram **também** no `CLAUDE.md`, em forma curta, porque valem em
qualquer sessão em que a bola passe para o usuário — e a sessão em que
isso acontece não se sabe de antemão.

**O que exige identidade de rede vai SEMPRE pelo `.bat`** (combinado em
04/09/2026). Nunca mandar o usuário digitar `python tools/x.py` dentro de um
`runas`: o console do `runas` fecha ao terminar, e o relatório se perde na
hora exata em que ele importa. O `.bat` já grava em arquivo e já imprime QUEM
está rodando — o `runas /netonly` não valida a senha na hora, e sem essa linha
a falha aparece só depois, como `18452 — untrusted domain`.

**E avisar, em voz alta, quando chegou a hora de rodar um.** Estas ferramentas
não rodam desta máquina (fora do domínio, SSPI recusado): quem as roda é o
usuário, e ele precisa saber que a bola está com ele — com o comando pronto
para copiar e o que conferir na saída.
