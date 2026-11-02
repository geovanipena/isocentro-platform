# R-58 — divisão de `dicom/`: inventário e cortes (22/10/2026)

Proposta antes de editar. A frente está no `DESTINO.md` (R-58) e a regra no
`ARCHITECTURE-SPINE.md` (AD-38): `rt/` só modela, recebe `pydicom.Dataset`
já lido e não importa nada do pacote além de si.

## O que há hoje (5.944 linhas em 8 arquivos)

| arquivo | modelo → `rt/` | leitura → `adaptadores/dicom/` | desenho | serviço / console |
|---|---|---|---|---|
| `dicom_rt.py` (2.217) | `parse_rtplan`, `parse_rtstruct`, `parse_ct`, `parse_rtdose`, gating, gantry/arco, ordem dos feixes, DRR de setup, `calcular_ssds` e o TP0, `sinais_iop`, `agrupar_planos`, UIDs | `carregar`, `carregar_arquivo`, `_completar_file_meta`, `iter_dicoms`, `cabecalhos_arquivo` (zip/rar) | — | `FISICOS`, `MEDICOS`, `EQUIPE_SAT`, `TRATAMENTO_MEDICO`, casamento de nomes, `equipe_da_maquina`, `completar_equipe`; `_mesa_vert_sign`, `_mesa_angulo_console`, `abreviar_tabela_tolerancia` |
| `ct_series.py` (812) | `CTSerie` (volume, índices, máscaras), dose em %, amostragem | `carregar_series` (bytes → datasets) | `render`, `_desenhar_estruturas_*`, colorwash, colormap | — |
| `corpo3d.py` (692) | `_contornos_body`, `_sem_restos`, voxelizar, malha, suavizar | cache em disco + `threading.Lock` | `renderizar_corpo`, `_desenhar`, sombreamento | — |
| `dvh.py` (366) | `calcular_dvh*`, `mascara_3d`, `_curvas`, `_espessura_dos_contornos` | — | `plotar_dvh`, `_legenda_que_cabe`, `_cor` | — |
| `dose3d.py` (208) | tudo (grade, reamostrar, somar) | — | — | — |
| `cortes.py` (95) | — | — | tudo (`render_axial`) | — |
| `dicom_rede.py` (1.099) | — | tudo | — | — |

`dicom_rt` importa `dominio.constantes` (máquina, unidade, nomes do gating,
tabela de tolerância) e `dados.nomes` (grafia do nome). São essas duas setas
que impedem mover o arquivo como está.

## Cortes, do menor risco ao maior — um commit cada, com `comparar_pdf` no TC8 e no Elekta

1. **Leitura** → `adaptadores/dicom/` (`leitura.py` + `rede.py`). `carregar_series`
   se parte em dois: o adaptador transforma bytes em datasets (mantendo o
   consumo da lista na ordem de chegada, que segura os 3,6 GB do Elekta) e
   `rt` monta a `CTSerie` a partir dos datasets. Cache em disco do `corpo3d`
   vai junto.
2. **Equipe** → `dados/equipe.py` (que já existe e hoje importa `dicom_rt` ao
   contrário). `_formatar_nome` fica onde a grafia é decidida.
3. **Desenho** → `isocentro/desenho/` (`corte`, `grafico_dvh`, `corpo`). Sem mudar um pixel. FEITO 23/10.
4. **Convenção de console** (sinal da mesa, ângulo da série C, abreviação da
   tolerância) sai do `parse_rtplan`: ele passa a devolver o valor IEC 61217, e
   quem imprime aplica a convenção. **É o corte que pode mudar o papel sem
   erro** — 7 pontos fora do `dicom_rt` leem `mesa`/`desl_vert`, e o
   `calcular_ssds` hoje DESFAZ o sinal que o parse aplicou.
5. **Modelo** → `rt/` (o que sobra de `dicom_rt`, `ct_series`, `corpo3d`,
   `dvh`, `dose3d`); `_espessura` da R-62 se junta com a do `dvh`. Importadores
   todos trocados (~60 arquivos com testes), sem módulo de compatibilidade.
   Acende a regra de `rt/` no teste de arquitetura (R-24, se já existir).

## Decisões que são do físico — RESPONDIDAS em 22/10/2026

1. **SSD, `dose3d` e DVH vão os três para `rt/`.** Veredito segue em `dominio/qualidade`.
2. **Desenho em `isocentro/desenho/`**, pacote próprio, importado por `papel/` e `interface/`.
3. **Convenção de console em `papel/console.py`** até existir `modulos/radioteraficha`.

O que foi perguntado:

- **SSD, `dose3d`, `dvh`** — o AD-38 tira de `rt/` o "cálculo que sustenta
  veredito". Proposta: os três são **modelo** e vão para `rt/`. O SSD é número
  impresso conferido contra o TPS, não aprovação; a soma de dose e o DVH são a
  dose como número. Quem decide (índices, tolerância) é `dominio/qualidade`,
  que continua fora.
- **Onde mora o desenho** — o `papel/` e a `interface/` desenham as mesmas
  coisas (corte, DVH, corpo 3D).
- **Onde mora a convenção de console** enquanto `modulos/radioteraficha` não
  existe: `dominio/` está fora da frente.
