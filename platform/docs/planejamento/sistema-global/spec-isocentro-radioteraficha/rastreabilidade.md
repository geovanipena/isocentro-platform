# Rastreabilidade — Módulo Radioteraficha

Liga cada capacidade ao requisito (PRD) ou decisão, à regra (espinha), ao modo de falha a avaliar e à forma de verificação. A coluna **riscos.md** fica vazia até o físico escrever as linhas: este arquivo não inventa risco.

| CAP | FR / decisão | AD | Modo de falha a avaliar | riscos.md | Verificação |
| --- | --- | --- | --- | --- | --- |
| CAP-1 | FR-9, FR-7 | AD-11, AD-18 | perfil vendo ou liberando o que não deve; papel desconhecido com acesso a tudo | — | teste em PostgreSQL de capacidade; teste do recorte por perfil |
| CAP-2 | decisão do usuário (encaixe) | AD-18, AD-36 | layout que salta; verde fora da dose; reserva não anunciada | — | print antes/depois; `test_padrao_visual` |
| CAP-3 | regra do domínio | — | campo, ordem ou geometria do PDF mudando em silêncio | — | comparação de PDFs com referência, página a página |
| CAP-4 | AD-9 | AD-5, AD-9 | versão perdida ou sobrescrita; DICOM apagado sem registro | — | teste de versão idêntica/nova; teste de exclusão após gravação |
| CAP-5 | decisão do usuário (pendente) | AD-23, AD-26 | registro ligado ao paciente errado; gravação local com banco fora | — | teste de vínculo por `PatientId`; teste com banco fora |
| CAP-6 | regra do domínio | AD-5 | correção apagada; relatório escrito | — | teste: correção que deixa de divergir fica no histórico |
| CAP-7 | — | AD-5, AD-26 | marcação SUS no paciente errado | — | teste de chave canônica; validação do cartão |
| CAP-8 | decisão do físico (inventário e notas, 26/10) | AD-5, AD-9, AD-12 | simulação de outro paciente na capa; foto sem hash; máscara de uso desconhecido tratada como nova; item de paciente visível em outra clínica | — | teste de busca por paciente; hash divergente avisado; teste: usos vazios não viram 0; teste de RLS do inventário e das notas de paciente |
| CAP-9 | — | AD-9 | preferência aplicada sem dizer de onde veio | — | teste da ordem sessão → estação → serviço → padrão |
| CAP-10 | FR-40; decisão do físico (raízes, 26/10) | AD-37 | entidade perdida ou gravação dupla; ficha antiga fora das raízes ou só dentro do `.zip` | — | relatório de migração conferido item a item, com a raiz de cada ficha |
| CAP-11 | decisão do usuário (Virtual, checklist) | AD-18 | checklist gravando depois do corte | — | teste: sem gravação nova após o corte |
| CAP-12 | FR-40 | AD-35 | uso real sem validação | — | relatório assinado pelo físico |
