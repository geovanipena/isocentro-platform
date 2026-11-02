---
manual: "Eclipse Treatment Planning - Customer Release Note (v15.6 MR5, 2025-12)"
produto: Eclipse Treatment Planning
versao: "15.6 MR5"
versao_instalada: "Eclipse 15.6 MR5 (as três clínicas)"
origem: "manuais/Varian/ECLIPSE/Eclipse Treatment Planning - Customer Release Note (v15.6 MR5, 2025-12).pdf"
paginas: 55
atividades: [B01, B02, B03, B04, A02, A09, C10, C11]
refs: [MPPG-5b-TPS, DICOM-RT, IEC-61217]
manuais: ["ARIA e Eclipse 15.1-15.6 - Technical Specifications Guide (P1025260-005-E, 2026-06)", "Beam Configuration 15.5 Reference Guide", "Radiation Therapy Management Client 15.6 XENAPP 7.15 System Administration Manual"]
repos: []
isocentro: []
conferida: 2026-10-16
---

# Eclipse 15.6 MR5: release note do cliente

**Em uma frase.** É o documento que diz **o que mudou** até a MR5, **com quais versões o Eclipse foi validado** e **quais defeitos conhecidos** a equipe precisa contornar. É a leitura obrigatória antes e depois de cada upgrade (B03).

## Índice por tarefa

| Tarefa | Seção | Página |
| --- | --- | --- |
| Avisos gerais de segurança | Introduction | 6–7 |
| Componentes e versões compatíveis | System Components and Compatibility | 8–9 |
| Requisitos de sistema | System Requirements | 10 |
| Novidades 15.5 → 15.6 MR5 | New Features and Enhancements | 11–16 |
| Mudanças de comportamento | Changes from the Previous Release | 17–31 |
| **Defeitos conhecidos** (por módulo) | Known Issues | 32–52 |
| Desempenho | Performance Information | 53 |

## Avisos que viram regra no serviço [p. 6–7]

| Aviso | Consequência prática | Atividade |
| --- | --- | --- |
| Mudanças no RT Administration afetam **todas** as aplicações integradas, por exemplo o sistema de coordenadas de planejamento | Mudança de configuração é mudança de sistema: exige controle de mudança e reteste | B03 |
| Verificar o setup com método de posicionamento **antes do tratamento**, sobretudo quando se usam os deslocamentos de mesa impressos no relatório | Teste fim a fim com fantoma para validar os deslocamentos impressos | C10, A19 |
| Edição simultânea pode causar **perda de dados** | Treinar a equipe a ler as mensagens de edição concorrente | B05 |
| Na simulação virtual, o Eclipse precisa saber se o laser está alinhado à **origem DICOM** ou ao **pixel central da TC**; o protocolo da TC pode deslocar a imagem | Erro aqui marca o isocentro errado na pele: teste no comissionamento da TC e a cada protocolo novo | A09, C10 |
| Dados de feixe e modelos de cálculo têm **checksum** gerenciado pelo Beam Configuration; arquivo alterado gera "Check failed" | **Revalidar e reaprovar** o modelo afetado. É o controle de integridade pedido pelo MPPG-5b §9 | B01, B03 |
| Encerrar o programa travado à força pode perder dados do plano | Procedimento de travamento | B05 |
| **Vírgula decimal** da configuração regional do Windows não é reconhecida ("1,23" ≠ 1.23) | Padronizar a configuração regional das estações; cuidado em script e planilha | B06 |

## Compatibilidade validada pelo fabricante [p. 8]

Componentes: Varian System Server 15.1, ARIA RTM 15.6, DICOM Services 15.6, Distributed Calculation Framework 15.6, Contouring/Registration/SmartAdapt 15.6, Microsoft SQL 2014. Aplicações aprovadas: **ARIA OIS 15.5, 15.6 e 16.1**, Image Browser, Offline Review, **Portal Dosimetry 15.6**, RT Summary, Tx Preparation, Smart Segmentation 15.6.

Validação limitada a "instalar e verificar que não afeta o Eclipse": Acrobat Reader, MS Office, CutePDF, .decimal p.d., **IMSure 3.7** e **K&S DIAMOND 6.2** (softwares de cálculo independente). Qualquer software fora desta lista instalado na estação do Eclipse, inclusive o ISOCENTRO, é **responsabilidade do serviço** (B10).

## Mudança da MR5 que importa [p. 17]

O Eclipse passou a **impedir otimização e cálculo** em TC que use a faixa completa de 16 bits. Havia **overflow**: voxels de densidade mais alta eram lidos como mais baixa, gerando **dose errada**. O defeito antigo continua descrito nas *known issues*: áreas acima de 32.767 HU (metais) podem ser lidas errado; recomenda-se **sobrescrever o valor de TC** dessas áreas [p. 38].

## Defeitos conhecidos selecionados

| Módulo | Defeito | Contorno | Página |
| --- | --- | --- | --- |
| Beam Configuration | Curva de calibração da TC entra como **densidade eletrônica relativa à água**, não absoluta | Conferir as unidades na entrada | 47 |
| Beam Configuration | Ao **recalcular os dados de campo aberto**, os acessórios (*add-ons*) precisam ser recalculados; se máquinas compartilham os dados de campo aberto, **o sistema não avisa** | Comissionar cada máquina em separado ou recomissionar os acessórios | 48 |
| Beam Configuration | **Não detecta perfil diagonal errado** (AAA, Acuros) se não bater com o tamanho de campo | Conferir os diagonais à mão | 48 |
| Beam Configuration | Em **FullScale ou Citrix**, falha ao abrir o checksum pode **apagar a configuração do eMC** | Recalcular o modelo eMC | 48 |
| Import/Export | Estruturas enviadas por DICOM entre sistemas podem sofrer **pequenas mudanças de contorno** | **Sempre conferir os contornos** recebidos | 48 |
| Plano | Plano com protocolo de movimento copiado, desaprovado ou trocado de máquina pode **perder o protocolo sem aviso** | Conferir o protocolo de movimento | 38 |
| Plano | Cópia ou revisão de plano com camadas na imagem do campo pode **distorcer as camadas** se os parâmetros do DRR mudaram sem o DRR ativo | Revisar o DRR na vista | 38 |
| Dose | eMC é 3D e **não calcula plano único** (F6) | — | 43 |

## Como se aplica

- **DUO:** o comissionamento do VitalBeam deixou os modelos eMC para o físico calcular e aprovar (A02). Em Citrix, o defeito da p. 48 pode apagá-los: conferir após cada atualização.
- **Upgrade (B03):** ler as seções "Changes" e "Known Issues" da versão nova contra esta tabela e recalcular os planos de referência (MPPG-5b §9, 1%/1 mm).
- **Scripts e planilhas:** a regra da vírgula decimal vale para qualquer dado que entre no Eclipse.
