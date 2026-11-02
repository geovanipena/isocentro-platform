---
codigo: IHE-RO-TF
titulo: "IHE Radiation Oncology Technical Framework, Volume 3 (RO TF-3): Content Modules, Rev. 3.0 Final Text"
ano: 2025
emissor: IHE International, domínio Radiation Oncology (IHE-RO)
tipo: guia técnico (perfil de interoperabilidade sobre o padrão DICOM)
vigencia: "vigente (2025-09-05); referência DICOM edição 2018d"
atividades: [B04, C10, C11, B10, B06]
refs: [DICOM-RT, TG-201, IEC-61217, TG-263]
manuais: []
repos: []
isocentro: []
texto: "../../texto/03 Nomenclatura, prescrição e coordenadas/IHE-RO-TF.md"
origem: "referencias/03 Nomenclatura, prescrição e coordenadas/IHE-RO-TF - IHE Radiation Oncology Technical Framework Vol 3 Rev 3.0 (2025-09-05).pdf"
conferida: 2026-10-20
---

# IHE-RO Technical Framework, Vol. 3 (Rev. 3.0, 2025): conteúdo dos objetos DICOM-RT

**Em uma frase.** Define, módulo a módulo, **quais atributos DICOM cada objeto de radioterapia deve ter** (RT Plan de fótons em planejamento e em entrega, RT Plan de composição de dose e de dose tracking, RT Ion Plan, imagem, **RT Structure Set**, **RT Dose**, registro de tratamento, dicionário de ROI, workflow UPS) para que sistemas de fornecedores diferentes troquem dados sem perda. Fornecedores que passam no **Connectathon** IHE-RO seguem estas regras.

O PDF tem cerca de 150 páginas, quase todo em tabelas de atributos (IOD e módulos); o texto saiu legível, com números de linha do documento misturados.

## Regras gerais úteis ao físico (seção 7)

| Regra | Conteúdo | Página |
| --- | --- | --- |
| Atributos extras | Pode enviar mais do que o pedido; **é erro o receptor rejeitar** um objeto por atributo a mais | [IHE-RO-TF p. 18] |
| Conjunto de caracteres | Todos os atores aceitam pelo menos o padrão e **ISO-IR 100 (Latin-1)**; sem conjunto comum, usar ISO-IR 100 | [IHE-RO-TF p. 19–20] |
| Dados do paciente | Nome, ID, nascimento e sexo **copiados da TC** para estruturas, planos, dose e registro; inconsistência tratada com segurança | [IHE-RO-TF p. 20] |
| Estudo | Recomenda **novo Study** para o RT Structure Set; objetos derivados copiam o Study do antecessor; mudar atributo de estudo exige Study novo | [IHE-RO-TF p. 20] |
| **Frame of Reference** | Todo objeto baseado na série de planejamento **copia o Frame of Reference** dessa série | [IHE-RO-TF p. 20] |
| RT Dose | Para dose em grade, módulos de imagem (General Image, Image Plane, Image Pixel, Multi-Frame) são obrigatórios no IHE-RO | [IHE-RO-TF p. 31–32] |

## Pontos de atenção

- O documento não traz requisitos clínicos nem tolerâncias; é a especificação que explica **por que** um plano exportado de um sistema às vezes não abre em outro (atributo exigido ausente, Frame of Reference diferente, caracteres fora do Latin-1).
- Acentos em nomes de paciente e de estrutura dependem do conjunto de caracteres; nomes TG-263 (só ASCII) evitam o problema.

## Como se aplica no CLINICA

- C11/B04: ao integrar sistema de terceiros (segundo cálculo, QA de paciente, registro de imagens) com o Eclipse/ARIA, pedir ao fornecedor a **declaração de conformidade DICOM e a participação em perfis IHE-RO**; testar a importação com casos-teste (TG-201).
- B06: scripts do ISOCENTRO que gravam DICOM (exportação, pseudonimização) devem copiar o Frame of Reference e os dados do paciente como aqui exigido.
