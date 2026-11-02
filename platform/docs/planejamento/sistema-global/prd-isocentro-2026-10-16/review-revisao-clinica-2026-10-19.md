# Revisão de segurança clínica — Update de 19/10/2026

Escopo: só o que mudou no Update (FR-7, FR-10, FR-12, FR-13, FR-14, FR-22, FR-23, FR-29, FR-32, FR-33, FR-34, FR-35, FR-36 movido, FR-43 a FR-48, NFR-10, §10, §12.2, §12.3, §15, §16). Regras de `docs/qms/revisao-clinica.md`.

| Trecho citado | Regra | Gravidade | Pergunta ao físico |
| --- | --- | --- | --- |
| FR-10: "a tabela traz também a transmissão do MLC e o DLG, com a origem da medida" | 1 | importante | O comissionamento atual (DOSEMED 2020, 600CD 2010) tem transmissão do MLC e DLG medidos? Se não, quem mede e quando, antes do FR-14 de modulado? |
| FR-13: "Campo modulado (IMRT/VMAT) é calculado pelo Clarkson por ponto de controle" | 5, 8 | importante | Como o arco é amostrado (passo angular), e qual caso TG-119 por máquina prova o método antes do veredito? |
| FR-45: "O cálculo define a dose de todos os pacientes: a classe dele é decisão do físico" | 9 | importante | A classe B provisória do módulo vale para o cálculo TRS-398, ou ele sobe ao rigor C junto do núcleo e do Plano? |
| FR-45: "k_Q da tabela do TRS-398 Rev. 1 para a câmara cadastrada e N_D,w do certificado" | 6 | importante | O certificado da câmara é pré ou pós ICRU 90? Usar k_Q da Rev. 1 (ICRU 90) com N_D,w antigo mistura bases (C5). |
| FR-46: "Origem das imagens a levantar (§15, C4)" | 1 | importante | De onde vem cada imagem (EPID/kV exportado pelo ARIA ou arquivo da estação)? Sem fonte, o teste nasce vazio. |
| FR-23: "Resultado fora da tolerância é `nao_conforme` com alerta `alta`" | 6 | observação | A regra 6 impede reprovar *plano* com tolerância de literatura. Aqui é CQ de máquina e nada bloqueia; confirmar que a carta e o sinal da máquina dizem "literatura, não derivado do serviço". |
| FR-29: "A notificação é identificada no log, mas tela [...] não mostram quem notificou" | 7, 8 | observação | Quem pode consultar o log para ver o notificador (só o verificador de integridade)? Escrever no `riscos.md` o modo de falha "notificador exposto". |
| FR-33: "Do ASO, o ISOCENTRO guarda só a pessoa, a data do exame e a validade" | 7 | observação | O nome do funcionário no banco central está coberto pelo RIPD/LGPD do serviço? |
| FR-43 a FR-48 | 9 | observação | Nenhum dos FRs novos tem classe declarada em `classificacao-62304.md` (G1). |
| §12.2: novas linhas FR-43 a FR-48 | 8 | observação | As linhas do `riscos.md` (S, O, D) continuam por escrever (frentes R-27, R-37, R-44, R-48). |

**0 achados bloqueantes**, 5 importantes, 5 observações. Todos os importantes já estão como questão em aberto no §15 (P3, G1, C4, C5) ou nas frentes do `DESTINO.md`; nenhum exige mudar o texto do PRD.
