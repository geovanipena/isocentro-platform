# ISOCENTRO — visão da arquitetura para a gestão

*Clinica · 19/10/2026 · resumo da arquitetura aprovada em rascunho*

## O que o sistema resolve

Hoje, conferências e registros ficam espalhados em arquivos na rede, que qualquer estação pode editar e que não têm prova de integridade. O ISOCENTRO reúne tudo num só programa: confere planos e tratamentos de forma automática, registra assinaturas, controle de qualidade, incidentes e prazos, e guarda um histórico que não pode ser alterado sem que se perceba. São nove áreas (Plano, Tratamento, Qualidade, Segurança, Documentação, Software, Indicadores, Conhecimento e Radioteraficha) sobre uma base comum.

## O desenho em termos simples

- **Um programa só**, instalado nas estações das três unidades: **CEL, BET e DUO**. Todas usam a mesma versão.
- **Um servidor na rede do Clinica** (`clinica-python01`) guarda todos os registros num banco de dados central. No mesmo servidor roda uma rotina automática, sem tela, que faz as conferências agendadas e controla os prazos, mesmo com as estações desligadas.
- **O ARIA continua sendo a trava.** O ISOCENTRO só lê o ARIA e o Eclipse e nunca escreve neles. Quando encontra algo fora do esperado, ele **avisa e registra**. Nenhum aviso bloqueia o tratamento: a decisão continua com a equipe e com o ARIA.
- Se o servidor central sair do ar, as estações continuam consultando, mas não gravam nada, e um aviso aparece na tela. Nesse período os registros são feitos em papel e lançados depois.

## Por que é seguro para inspeção

- **Registro que não se apaga.** Nada é apagado nem editado. Uma correção vira um novo registro, ligado ao anterior. Cada gravação registra, no mesmo instante, quem fez, quando e o quê. Os registros formam uma corrente: mexer em qualquer um deles quebra a sequência.
- **Testemunha diária na pasta da TI.** Todo dia o sistema deixa uma "impressão digital" do histórico, sem dado de paciente, numa pasta da TI em que nem o responsável pelo banco consegue apagar ou editar nada. Uma ferramenta compara o histórico com essas testemunhas e aponta qualquer alteração.
- **Backup cifrado guardado por 10 anos.** A cópia diária sai do servidor já cifrada e fica 30 dias em outra máquina. Uma cópia por mês vai para uma mídia separada. A guarda dura 10 anos contados **após o descarte** do software, conforme a RDC 657. A restauração é testada todo mês, e o teste também fica registrado.
- **Dado do paciente não sai da rede do Clinica.** Ele não vai para serviços de terceiros nem para ferramentas de IA. As exportações saem sem identificação.
- **Cada pessoa entra com o próprio login**, conferido pelo próprio servidor. Assim cada assinatura tem autoria comprovada, e cada pessoa só vê as unidades a que tem acesso.

## O que se pede da gestão

1. **Guarda lacrada da cópia da chave do backup.** A chave fica com o físico responsável, e uma cópia lacrada fica com a SPR/gestão.
2. **Pasta da TI só-acrescentar** (aceita arquivos novos, mas não permite apagar nem editar), para receber a testemunha diária.
3. **Servidor `clinica-python01`** reservado para o banco central e para a rotina automática.
4. **Decisão sobre a classe regulatória** (IEC 62304/ANVISA), que ainda está pendente e precisa sair antes da construção da área de Plano. Até lá, a base comum e a área de Plano são construídas no nível mais rigoroso.
5. **Atualização dos perfis de acesso.** Hoje existem três versões diferentes (no programa, no documento de requisitos e no desenho das telas), ainda sem lista final, e é preciso fechar uma lista única.

## Custos

O software é **gratuito**: o banco de dados PostgreSQL e as bibliotecas usadas são abertos, sem licença paga. O custo real é o **tempo de manutenção de uma pessoa**: o físico que instala e mantém o servidor, faz o backup e aplica as atualizações trimestrais. Isso cria um **risco de pessoa única**. A mitigação é um **roteiro escrito de manutenção**, com testes de restauração registrados, para que outra pessoa possa assumir.

## Riscos e pendências principais

Além da classe regulatória e dos perfis de acesso (itens 4 e 5 acima):

- **Análise de riscos** dos perigos trazidos pela nova arquitetura, a ser escrita pelo físico antes da primeira gravação de dado clínico.
- **Programa atual em Qt 5**, versão da biblioteca de telas fora do suporte padrão desde 2025. A interface migra para Qt 6 junto com o novo visual.
- **Detalhes de segurança da rede e do servidor** (criptografia da conexão, contas administrativas) e **metas de desempenho** ainda a detalhar.

## Próximos passos

1. **Atualizar o documento de requisitos:** perfis, registro do banco central no escopo e a decisão regulatória.
2. **Construir por etapas.** Primeiro a base comum, depois a área de Plano (primeira entrega), Qualidade e Segurança do paciente, cada uma testada num ambiente de homologação, sem dado clínico, antes de entrar em produção.
3. **Migrar o Radioteraficha por partes**, um tipo de dado por vez (usuários, depois equipe, depois checklist e assim por diante): migra, confere e, a partir daí, só o banco grava aquele dado. O arquivo antigo fica só para leitura e depois é arquivado.
