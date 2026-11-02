# Classificação de segurança do software (IEC 62304)

> **A preencher pelo físico responsável.** A classe de cada módulo é decisão
> clínica, não proposta da IA. Os agentes do BMad leem este arquivo e apontam
> módulo sem classe; não a decidem.

Referência: IEC 62304:2006 + A1:2015, cláusula 4.3. Classe A: o software não
contribui para situação perigosa, ou contribui sem risco inaceitável depois
das medidas de controle de risco externas a ele. Classe B: risco inaceitável
cujo dano possível é lesão não grave. Classe C: risco inaceitável cujo dano
possível é morte ou lesão grave. Pelo A1, as medidas de controle **externas**
ao software (hardware, outro software independente, procedimento) entram na
conta e podem rebaixar a classe; as que contam aqui estão em `riscos.md`,
"Medidas de controle externas ao software". (Corrigido em 26/10/2026 a pedido
do físico: a redação anterior, da edição de 2006, mandava classificar sem
elas e contradizia a classe A do núcleo e do Plano.)

| Módulo / item de software | Classe | Justificativa | Decidido em |
| --- | --- | --- | --- |
| ISOCENTRO — Radioteradados (aba de indicadores) | A | Nenhum dano possível: só lê o banco, não toca dose nem vai para a sala de tratamento; números de gestão e avaliação externa. | 13/10/2026, Geovani Pena |
| ISOCENTRO — `dominio/ritmo` (frequência, calendário e contagem de frações, compartilhado por Ficha Virtual, Capa e Radioteradados) | A | Nenhum dano possível: a frequência impressa é conferida pela equipe e não entra em cálculo de dose. | 13/10/2026, Geovani Pena |
| ISOCENTRO — núcleo (Fundação) | A | Contribui para risco só através dos módulos, e o risco fica aceitável pelas medidas externas: a trava de aprovação do ARIA (o ISOCENTRO é advisory) e a assinatura em papel. ANVISA: classe I ou II até todos os testes. | 26/10/2026, Geovani Pena (G1) |
| ISOCENTRO — módulo Plano | A | Idem: a segunda checagem e as listas são advisory; a liberação do plano continua na trava do ARIA e na assinatura em papel. ANVISA: classe I ou II até todos os testes. | 26/10/2026, Geovani Pena (G1) |
| ISOCENTRO — módulo GQ (exceto o cálculo TRS-398) | A | Registro de testes, vencidos, cartas e análise de imagem são advisory; parar a máquina é decisão do físico. ANVISA: classe I ou II até todos os testes. | 26/10/2026, Geovani Pena (G1 do GQ) |
| ISOCENTRO — cálculo da calibração TRS-398 (item próprio em `modulos/qualidade`, ex.: `modulos/qualidade/calibracao`; nunca no `rt`) | C | Um fator errado atinge todos os pacientes da máquina e passa pelas conferências de plano (TPS e segunda checagem partem da mesma dose de referência); planilha, advisory e auditoria externa bienal não o pegam a tempo. | 26/10/2026, Geovani Pena (G1 do GQ) |
| ISOCENTRO — camada `rt` (leitura e modelo de objetos de RT: geometria, cortes, DVH como números; sem veredito) | A | Acompanha o consumidor mais crítico (AD-39), que é A: Plano e Radioteraficha; o número que chega à ficha ou à conferência passa pela trava do ARIA e pelo papel conferido. O cálculo TRS-398 não mora no `rt`. | 26/10/2026, Geovani Pena (classe por item) |
| ISOCENTRO — módulo Segurança do paciente | A | Advisory: nada vai para a dose nem para a sala; a matriz de risco só vale depois da confirmação do físico e o SEVRRA segue em paralelo. | 26/10/2026, Geovani Pena (classe por item) |
| ISOCENTRO — módulo Documentação | A | Nenhum dano direto possível: vencimento perdido é falha de conformidade, não de dose. | 26/10/2026, Geovani Pena (classe por item) |
| ISOCENTRO — módulo Radioteraficha | A | Idem: a ficha e a capa impressas continuam conferidas e assinadas pela equipe. ANVISA: classe I ou II até todos os testes. | 26/10/2026, Geovani Pena (G1) |
