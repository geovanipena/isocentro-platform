# Política de uso de LLM no serviço — RASCUNHO

> **Rascunho da IA, pedido pelo físico em 26/10/2026 (frente R-63). Nada aqui
> é decisão.** Fica em `docs/planejamento/` de propósito: o `docs/qms/` é lido
> pelos agentes como fato, e uma política escrita pela IA viraria regra que
> ninguém tomou. Quando o físico definir cada seção, o texto dele vai para
> `docs/qms/politica-llm.md` e este arquivo fica como histórico.

Base: AD-42 da espinha (aceito em 26/10/2026), que governa o **ISOCENTRO**.
Esta política é mais larga: governa o uso de LLM **pelas pessoas do serviço**
(ChatGPT, Claude, Copilot e afins), dentro ou fora do ISOCENTRO. A pesquisa
NORRIS-2025 (doi 10.1007/s13246-025-01571-9) achou entre físicos médicos
ganho de eficiência, menos ganho de qualidade, preocupação com dados e falta
de diretriz e de treinamento; as três frentes abaixo são as que ela aponta.

Cada seção tem a **pergunta**, um **texto-semente** tirado do AD-42 (para o
físico aceitar, editar ou riscar) e as **lacunas** que só ele responde.

---

## 1. Dado de paciente e de funcionário

**Pergunta.** O que pode e o que não pode ser colado num LLM?

**Texto-semente (do AD-42, regra 4).** Dado de paciente ou de funcionário
(nome, registro, data de nascimento, imagem, laudo, ASO) só passa por modelo
que roda na rede do serviço. Texto de norma, manual de equipamento e código
podem usar serviço externo. Na dúvida, não colar.

**Lacunas.**
- Dado pseudonimizado (900NNNN, como em `dicom-teste/`) pode ir a serviço
  externo?
- Conta institucional × conta pessoal: o serviço contrata alguma, e com que
  termo de uso de dados?
- Quem é o encarregado (LGPD) consultado nesta política?

## 2. Revisão humana

**Pergunta.** O que sai de um LLM pode ser usado sem revisão?

**Texto-semente (AD-42, regras 1, 2 e 8).** Saída de LLM é sugestão. Quem a
usa responde por ela como se a tivesse escrito. Citação de norma ou artigo é
conferida no documento original antes de ser usada. Nada de LLM em decisão
de dose, braquiterapia ou cálculo sem verificação independente.

**Lacunas.**
- Usos permitidos sem restrição (ex.: redação de e-mail, resumo de manual)?
- Usos proibidos além da regra 8 (ex.: contorno, prescrição, laudo)?
- Documento do QMS (POP, relatório) feito com ajuda de LLM precisa dizer
  isso?

## 3. Treinamento

**Pergunta.** Quem usa LLM no serviço precisa saber o quê, e como isso é
registrado?

**Texto-semente.** Antes do primeiro uso no trabalho, a pessoa lê esta
política e conhece três limites: alucinação (o modelo inventa citação e
número com a mesma confiança), viés de automação (aceitar porque parece
certo) e vazamento de dado (o que foi colado pode não sair mais de lá).

**Lacunas.**
- Treinamento por perfil (físico, médico, dosimetrista, técnico…) ou um só?
- Registro: lista de presença, ciência assinada, outro?
- Periodicidade de revisão desta política?

## 4. Responsável e revisão

**Lacunas.**
- Quem aprova esta política (físico responsável, direção, NSP)?
- Onde ela se cruza com o PPR e com o programa de garantia da qualidade?
- Data de revisão.
