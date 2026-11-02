////////////////////////////////////////////////////////////////////////////////
//  EstruturasOpt_Bexiga_Minima.cs           Clinica-Rede · Física Médica
//------------------------------------------------------------------------------
//  Gera uma estrutura "Bexiga_Min" representando uma aproximação geométrica do
//  volume mínimo de bexiga aceito para o plano, a partir de erosão da bexiga
//  contornada (cheia) na imagem de planejamento.
//
//  Volume-alvo:
//
//      V_alvo = MAX( MinimoGlobalCc , VolumeInicialCc * FracaoMinimaRelativa )
//
//  O script busca (busca binária) a intensidade de erosão que produz uma
//  estrutura com volume o mais próximo possível de V_alvo, dentro do limite
//  máximo de erosão configurado.
//
//  EROSÃO ZERO: se a bexiga contornada já está em V_alvo ou abaixo dele, a
//  bexiga mínima É a bexiga atual — o script cria uma cópia, sem redução, e
//  avisa que o paciente está abaixo do protocolo de enchimento. Isso não é
//  erro: é o caso mais conservador (paciente chegou com bexiga menos cheia do
//  que o protocolo pede) e recusá-lo negaria justamente a situação que mais
//  interessa avaliar.
//------------------------------------------------------------------------------
//  RESTRIÇÃO DURA: BEXIGA DENTRO DO PTV + MARGEM NÃO É REDUZIDA
//
//      Bexiga_Min = (bexiga reduzida)  \u222a  (bexiga \u2229 (PTV + margem))
//
//  O volume de bexiga que está dentro do PTV recebe dose de prescrição
//  independentemente do enchimento, e a faixa de margem ao redor (default
//  15 mm, editável na janela) está no gradiente íngreme. Nenhum dos dois pode
//  encolher: uma bexiga mínima que "sai" dessa região descreveria um paciente
//  com menos bexiga irradiada do que o real — viés otimista, inaceitável aqui.
//
//  Essa é uma restrição geométrica ligada ao alvo real, e não depende de
//  suposição sobre em que direção o alvo está. Ela prevalece sobre os pesos
//  direcionais: a união é aplicada depois da erosão, em toda avaliação da
//  busca e na gravação final.
//
//  Consequência: o volume da região protegida é o PISO da estrutura. Se o
//  volume-alvo for menor que ele, o alvo é inatingível — e o script informa
//  quanto de bexiga está comprometido dentro do PTV + margem, que é um dado
//  clínico útil por si só.
//
//  Sem PTV selecionado/encontrado, o script avisa e pede confirmação antes de
//  seguir sem proteção.
//------------------------------------------------------------------------------
//  MODELO GEOMÉTRICO (o que este script FAZ e o que NÃO faz)
//
//  A opção padrão ("colapso da cúpula") NÃO encolhe a bexiga uniformemente.
//  A redução é ponderada por eixo (AsymmetricMargin, eixos alinhados ao
//  sistema de coordenadas da imagem — DICOM PCS: +X = esquerda do paciente,
//  +Y = posterior, +Z = superior):
//
//      cúpula (superior, +Z)        -> desce; é daqui que sai o volume
//      base / trígono (inferior, -Z) -> FIXA (peso zero)
//      parede posterior (+Y)        -> FIXA (peso zero)
//      parede anterior (-Y)         -> recua pouco
//      paredes laterais (X)         -> aproximam-se pouco, simétricas
//
//  POR QUE base e parede posterior NÃO se movem: são as faces voltadas para o
//  alvo (próstata / colo / leito) e para o reto, e o trígono/colo vesical são
//  ancorados anatomicamente (junções ureterovesicais, colo vesical/uretra).
//  Quando a bexiga esvazia, a cúpula desce — a parede que encosta na região
//  de dose alta permanece essencialmente onde está. Um modelo que encolhesse
//  a bexiga em todas as direções afastaria essa parede do PTV e produziria um
//  viés OTIMISTA: sugeriria que com bexiga menos cheia a parede vesical sai
//  da dose alta, quando na prática ela continua lá. Esse é o erro que a
//  primeira versão deste script cometia (erosão isotrópica/ponderada com
//  pesos não-nulos na base), apontado na validação em caso real.
//
//  A distensão predominante pela cúpula é amplamente descrita na literatura
//  de motion/margens de bexiga em radioterapia pélvica (cf. p.ex. Muren LP,
//  Smaaland R, Dahl O. "Organ motion, set-up variation and treatment margins
//  in radical radiotherapy of urinary bladder cancer." Radiother Oncol 2003)
//  e é consistente com o conceito de margem interna (IM) do ICRU 62/83 para
//  variação de volume/forma de órgão.
//
//  Isso é uma SIMPLIFICAÇÃO GEOMÉTRICA, não uma simulação biomecânica nem uma
//  predição da forma real da bexiga parcialmente cheia. Onde disponível, um
//  contorno real de bexiga vazia (protocolo de CT com bexiga vazia/cheia,
//  comum em planejamento de colo uterino) é sempre preferível a esta
//  aproximação. O modelo isotrópico permanece disponível via checkbox, mas
//  SÓ para comparação/QA — ele tem o viés otimista descrito acima e não
//  deveria ser usado para decisão clínica.
//
//  Os pesos direcionais e os volumes mínimos (global/relativo) são provisórios
//  e DEVEM ser calibrados e validados localmente pelo físico responsável antes
//  de uso clínico — critério de verificação: no primeiro uso, conferir no
//  corte SAGITAL que a estrutura gerada tem a cúpula rebaixada e a base/parede
//  posterior COINCIDINDO com a bexiga original; se aparecer folga na base ou
//  se o corte vier pelo lado errado (base rebaixada, cúpula intacta), revisar
//  a orientação da imagem (HFS/FFS) antes de aceitar o resultado.
//------------------------------------------------------------------------------
//  Tipo: DLL binária GRAVÁVEL — compilada via MSBuild (ver
//  EstruturasOpt_Bexiga_Minima.csproj nesta mesma pasta), não roda como
//  single-file (Eclipse 15.6 não suporta single-file gravável; gravável só a
//  partir da v16.1).
//
//  CONVENÇÕES
//    · namespace VMS.TPS · public class Script (deve ser PUBLIC: sem o
//      modificador, o Eclipse falha com "entry type not found" ao carregar a
//      DLL por reflexão — single-file tolera internal, DLL binária não)
//    · [assembly: ESAPIScript(IsWriteable = true)] sempre logo após os usings
//    · [assembly: AssemblyVersion] FIXA, nunca wildcard: a autorização de
//      escrita está amarrada ao registro publicado/aprovado daquela
//      identidade (nome + versão). Wildcard muda a versão a cada build e a
//      gravação passa a falhar com "Argument 'Assembly scriptAssembly' can
//      not be null". Ver nota completa junto do atributo, abaixo dos usings
//    · CanAddStructure() só responde corretamente DEPOIS de
//      BeginModifications(): chamado antes, retorna false mesmo quando a
//      estrutura poderia ser criada — validação de ID precisa vir depois de
//      habilitar a edição
//    · SegmentVolume que passou por uma estrutura REMOVIDA vira referência
//      morta: atribuí-la a outra estrutura estoura com "External component
//      has thrown an exception". Guardar o parâmetro (aqui, a intensidade em
//      mm) e RECALCULAR o segmento, nunca cachear o objeto
//    · static readonly (não const): no compilador do plug-in, ramos não
//      tomados por uma constante viram "código inalcançável" (CS0162/CS0429),
//      tratado como erro
//    · A ESAPI limita cada Margin/AsymmetricMargin a 50 mm, o que é pouco
//      para reduções grandes (bexiga de 700 cc caindo à metade com a base
//      fixa). Erosão morfológica alinhada aos eixos é aditiva, então a
//      redução é aplicada em PASSOS ENCADEADOS sobre o resultado anterior —
//      equivalente a uma erosão única do total, sem o teto de 50 mm. O campo
//      "intensidade máxima" da janela é trava de segurança, não limite da API
//    · SegmentVolume não expõe volume próprio na ESAPI — só Structure.Volume
//      existe. A busca de erosão usa uma estrutura de trabalho provisória
//      ("TMP_BX_MIN_ERO") só para leitura de volume; ela é removida ao final
//      da busca (Execute já habilita edição antes disso — ver comentário em
//      ID_ESTRUTURA_PROVISORIA). Se o script for interrompido no meio da
//      busca (crash/kill), pode sobrar essa estrutura provisória no Structure
//      Set — a próxima execução a remove sozinha antes de recriar; se for
//      notada manualmente, pode ser apagada sem risco.
//
//  VALIDAR EXAUSTIVAMENTE em ambiente NÃO-CLÍNICO antes de uso real —
//  geometria/pesos ainda não confirmados em caso real.
////////////////////////////////////////////////////////////////////////////////

using System;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Reflection;
using System.Collections.Generic;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

[assembly: ESAPIScript(IsWriteable = true)]

// Versão FIXA — nunca wildcard ("1.0.*") num script gravável.
//
// A Eclipse identifica o script por nome + versão, e a autorização de
// ESCRITA está amarrada ao registro publicado/aprovado dessa identidade.
// Com wildcard, cada recompilação gera uma versão nova que não corresponde a
// nenhum registro aprovado: BeginModifications() até passa, mas a primeira
// gravação estoura com "Argument 'Assembly scriptAssembly' can not be null".
//
// Com versão fixa, recompilar e sobrescrever a DLL na pasta mantém a
// identidade aprovada — dá para iterar sem republicar nada. Subir a versão
// aqui é um ato deliberado de release: depois de subir, é preciso publicar a
// nova versão no ESAPI Script Administration, APROVAR e aposentar a antiga,
// senão a gravação para de funcionar.
[assembly: AssemblyVersion("1.0.0.1")]

namespace VMS.TPS
{
    public class Script
    {
        // ===================== CONFIGURAÇÃO DA CLÍNICA =====================
        // Defaults apresentados na janela; o usuário pode ajustá-los antes de
        // confirmar. Ver nota de calibração local no cabeçalho do arquivo.
        private static readonly double DEFAULT_MINIMO_GLOBAL_CC = 150.0;
        private static readonly double DEFAULT_MINIMO_RELATIVO_PCT = 70.0;

        // Intensidade máxima de erosão (mm) — é a magnitude "base" antes dos
        // pesos direcionais; ver PESO_* abaixo. Com a base e a face posterior
        // fixas (peso zero), todo o volume sai pela cúpula, então a
        // intensidade necessária é bem maior do que numa erosão isotrópica:
        // uma bexiga de 700 cc precisa de bem mais de 50 mm para cair à
        // metade. Este valor é só uma trava de segurança, não uma restrição
        // da API — a erosão é aplicada em passos encadeados (ver
        // CalcularSegmentoErodido), então não há teto de 50 mm aqui.
        private static readonly double DEFAULT_EROSAO_MAXIMA_MM = 150.0;

        // Precisão volumétrica desejada na busca binária.
        private static readonly double DEFAULT_TOLERANCIA_VOLUME_CC = 2.0;

        private static readonly int MAX_ITERACOES_BUSCA = 30;

        // Interrompe a busca binária mais cedo quando o intervalo de erosão já
        // convergiu abaixo desta largura (mm), mesmo sem ter atingido a
        // tolerância volumétrica — evita iterações inúteis quando a curva
        // volume x erosão está praticamente plana.
        private static readonly double LARGURA_MINIMA_INTERVALO_MM = 0.05;

        private static readonly string DEFAULT_ID_SAIDA = "Bexiga_Min";
        private static readonly string TIPO_DICOM_SAIDA = "ORGAN";

        // Estrutura de trabalho provisória usada durante a busca de erosão.
        // A ESAPI (SegmentVolume) não expõe volume próprio: o único jeito de
        // ler o volume de uma erosão candidata é atribuí-la a uma Structure
        // real e ler Structure.Volume. Essa estrutura é removida assim que a
        // busca termina — a estrutura definitiva só é criada após a
        // confirmação do usuário.
        // Margem ao redor do PTV que também é preservada. A bexiga dentro de
        // PTV + esta margem não pode ser reduzida: além do volume que recebe
        // dose de prescrição, a faixa vizinha está no gradiente íngreme e
        // continua clinicamente comprometida qualquer que seja o enchimento.
        private static readonly double DEFAULT_MARGEM_PTV_MM = 15.0;

        // Rótulos das opções do seletor de PTV (não são IDs de estrutura).
        private static readonly string OPCAO_TODOS_PTVS = "(todos os PTVs)";
        private static readonly string OPCAO_SEM_PTV = "(nenhum \u2014 sem prote\u00e7\u00e3o)";

        private static readonly string ID_ESTRUTURA_PROVISORIA = "TMP_BX_MIN_ERO";
        private static readonly string TIPO_DICOM_PROVISORIA = "CONTROL";

        // Limite de caracteres para Structure ID no Eclipse.
        private static readonly int LIMITE_CARACTERES_ID = 16;

        // Limite absoluto de margem da ESAPI (mm) POR CHAMADA;
        // Margin/AsymmetricMargin lançam exceção acima disso. Não limita a
        // erosão total: CalcularSegmentoErodido encadeia chamadas.
        private static readonly double LIMITE_MARGEM_ESAPI_MM = 50.0;

        // Passo máximo do encadeamento: o limite da ESAPI menos uma folga,
        // para não esbarrar no teto por arredondamento. Declarado DEPOIS de
        // LIMITE_MARGEM_ESAPI_MM de propósito — static readonly que referencia
        // outro campo captura zero se vier antes dele no arquivo (CLAUDE.md §5).
        private static readonly double PASSO_MAXIMO_SEGURO_MM = LIMITE_MARGEM_ESAPI_MM - 5.0;

        // Trava de sanidade para o campo de erosão máxima da janela. Não tem
        // relação com o limite da ESAPI; só impede valor absurdo digitado.
        private static readonly double LIMITE_INTENSIDADE_MM = 300.0;

        // Usar o modelo de colapso da cúpula por padrão (ver racional no
        // cabeçalho).
        private static readonly bool DEFAULT_MODELO_ANISOTROPICO = true;

        // Pesos direcionais (adimensionais, aplicados sobre a intensidade "t"
        // escolhida pela busca binária): erosão_no_eixo = t * peso.
        //
        // INFERIOR e POSTERIOR são ZERO de propósito: são as faces voltadas
        // para o alvo (próstata / colo / leito) e para o reto. O trígono e o
        // colo vesical são ancorados anatomicamente e NÃO recuam quando a
        // bexiga esvazia — quem desce é a cúpula. Erodir essas faces afastaria
        // a parede vesical da região de dose alta, que é exatamente o viés
        // otimista que este script não pode introduzir: a bexiga menos cheia
        // deve manter a parede onde ela está.
        //
        // Ajustar conforme validação local — mas manter INFERIOR/POSTERIOR em
        // zero a menos que haja razão clínica documentada para o contrário.
        private static readonly double PESO_SUPERIOR = 1.0;   // +Z, cúpula (desce)
        private static readonly double PESO_INFERIOR = 0.0;   // -Z, base/trígono FIXO
        private static readonly double PESO_ANTERIOR = 0.5;   // -Y, parede anterior recua pouco
        private static readonly double PESO_POSTERIOR = 0.0;  // +Y, face do reto/alvo FIXA
        private static readonly double PESO_LATERAL = 0.35;   // X1 = X2, paredes se aproximam pouco

        // Nomes candidatos para localização automática da bexiga.
        private static readonly string[] NOMES_CONHECIDOS_BEXIGA =
        {
            "Bladder", "Bexiga", "BLADDER", "Urinary Bladder", "VES", "Vesica"
        };
        // ===================================================================

        public void Execute(ScriptContext context, Window window)
        {
            // ---------------------------------------------------------------
            // Validação de contexto.
            // ---------------------------------------------------------------
            if (context == null || context.Patient == null)
            {
                MostrarMensagem(window, "Carregue um paciente.", "Bexiga Mínima",
                    MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            StructureSet structureSet =
                (context.PlanSetup != null && context.PlanSetup.StructureSet != null)
                    ? context.PlanSetup.StructureSet
                    : context.StructureSet;

            if (structureSet == null)
            {
                MostrarMensagem(window, "Carregue um plano ou um conjunto de estruturas.",
                    "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // ---------------------------------------------------------------
            // Localizar candidatos a bexiga.
            // ---------------------------------------------------------------
            List<Structure> candidatos = EncontrarCandidatosBexiga(structureSet);

            if (candidatos.Count == 0)
            {
                MostrarMensagem(window,
                    "Nenhuma estrutura de bexiga foi identificada automaticamente.\n\n" +
                    "Verifique a nomenclatura da estrutura ou crie a estrutura " +
                    "da bexiga antes de executar o script.",
                    "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // ---------------------------------------------------------------
            // Janela de configuração.
            // ---------------------------------------------------------------
            JanelaBexigaMinima janela = new JanelaBexigaMinima(
                candidatos,
                MontarOpcoesPtv(structureSet, context.PlanSetup),
                structureSet,
                DEFAULT_MINIMO_GLOBAL_CC,
                DEFAULT_MINIMO_RELATIVO_PCT,
                DEFAULT_EROSAO_MAXIMA_MM,
                DEFAULT_MARGEM_PTV_MM,
                DEFAULT_TOLERANCIA_VOLUME_CC,
                DEFAULT_ID_SAIDA,
                DEFAULT_MODELO_ANISOTROPICO,
                LIMITE_CARACTERES_ID,
                LIMITE_INTENSIDADE_MM);

            if (window != null)
            {
                janela.Owner = window;
                janela.WindowStartupLocation = WindowStartupLocation.CenterOwner;
            }

            bool? resultadoJanela = janela.ShowDialog();

            if (resultadoJanela != true)
            {
                return;
            }

            Structure bexigaSelecionada = janela.BexigaSelecionada;
            double minimoGlobalCc = janela.MinimoGlobalCc;
            double fracaoMinimaRelativa = janela.MinimoRelativoPct / 100.0;
            double erosaoMaximaMm = janela.ErosaoMaximaMm;
            double toleranciaVolumeCc = janela.ToleranciaVolumeCc;
            string idSaida = janela.IdEstruturaSaida;
            bool substituirExistente = janela.SubstituirExistente;
            bool modeloAnisotropico = janela.ModeloAnisotropico;
            string selecaoPtv = janela.SelecaoPtv;
            double margemPtvMm = janela.MargemPtvMm;

            // ---------------------------------------------------------------
            // Validações finais (a janela já valida faixas numéricas; aqui
            // revalidamos o que depende de dados do paciente/estrutura).
            // ---------------------------------------------------------------
            if (bexigaSelecionada == null)
            {
                MostrarMensagem(window, "Nenhuma estrutura de bexiga foi selecionada.",
                    "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            double volumeInicialCc = bexigaSelecionada.Volume;

            if (volumeInicialCc <= 0.0)
            {
                MostrarMensagem(window, "O volume da bexiga selecionada é zero ou inválido.",
                    "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            double volumeRelativoCc = volumeInicialCc * fracaoMinimaRelativa;
            double volumeAlvoCc = Math.Max(minimoGlobalCc, volumeRelativoCc);

            // Bexiga já no mínimo (ou abaixo): a bexiga mínima É a bexiga
            // contornada. Erosão zero, cópia direta — NÃO é erro. Recusar aqui
            // seria negar justamente o caso mais conservador: paciente que
            // chegou com bexiga menos cheia do que o protocolo pede.
            bool semReducao = volumeAlvoCc >= volumeInicialCc;

            if (idSaida.Length > LIMITE_CARACTERES_ID)
            {
                MostrarMensagem(window,
                    "O ID da estrutura de saída excede " + LIMITE_CARACTERES_ID +
                    " caracteres (limite do Eclipse): '" + idSaida + "'.",
                    "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            Structure estruturaExistente = structureSet.Structures.FirstOrDefault(s =>
                s.Id.Equals(idSaida, StringComparison.OrdinalIgnoreCase));

            if (estruturaExistente != null && !substituirExistente)
            {
                MostrarMensagem(window,
                    "A estrutura '" + idSaida + "' já existe.\n\n" +
                    "Marque 'Substituir estrutura existente' se deseja recriá-la.",
                    "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // ---------------------------------------------------------------
            // Habilita edição do Structure Set. Precisa acontecer aqui (e não
            // só na gravação final) porque a busca de erosão usa uma
            // estrutura de trabalho provisória para ler volume (ver
            // ID_ESTRUTURA_PROVISORIA acima) — nenhuma estrutura DEFINITIVA é
            // criada antes da confirmação do usuário, mais abaixo.
            // ---------------------------------------------------------------
            try
            {
                context.Patient.BeginModifications();
            }
            catch (Exception ex)
            {
                MostrarMensagem(window,
                    "Não foi possível habilitar a edição do paciente.\n\n" + ex.Message,
                    "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // CanAddStructure SÓ responde corretamente depois de
            // BeginModifications(): sem o modo de edição habilitado ele
            // retorna false mesmo quando a estrutura poderia ser criada.
            // Por isso esta checagem vem depois, e não junto das demais
            // validações acima.
            if (estruturaExistente == null && !structureSet.CanAddStructure(TIPO_DICOM_SAIDA, idSaida))
            {
                MostrarMensagem(window,
                    "O Eclipse não permite adicionar a estrutura '" + idSaida + "' ao " +
                    "Structure Set atual.\n\n" +
                    "Causas usuais:\n" +
                    "  • Structure Set aprovado ou em uso por plano aprovado — " +
                    "nesse caso é preciso desaprovar ou trabalhar numa cópia;\n" +
                    "  • limite de estruturas do Structure Set atingido;\n" +
                    "  • ID inválido para o Eclipse (caracteres não aceitos).",
                    "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // ---------------------------------------------------------------
            // Região intocável: bexiga dentro do PTV. Resolvida aqui porque as
            // operações booleanas precisam do Structure Set já editável.
            // ---------------------------------------------------------------
            SegmentVolume segmentoProtegido;
            string descricaoPtv;
            try
            {
                segmentoProtegido = ResolverSegmentoProtegido(
                    structureSet, bexigaSelecionada, selecaoPtv, margemPtvMm, out descricaoPtv);
            }
            catch (Exception ex)
            {
                MostrarMensagem(window,
                    "Não foi possível determinar a bexiga dentro do PTV.\n\n" + ex.Message,
                    "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // Sem redução, a proteção é irrelevante (a cópia contém tudo):
            // avisar ali seria ruído.
            if (segmentoProtegido == null && !semReducao)
            {
                MessageBoxResult seguir = MostrarMensagem(window,
                    "SEM PROTEÇÃO DE PTV.\n\n" +
                    "Nenhum PTV foi selecionado ou encontrado, então a bexiga dentro do " +
                    "alvo e da sua margem NÃO será preservada — a estrutura gerada pode se afastar da " +
                    "região de dose alta, que é um viés otimista.\n\n" +
                    "Continuar mesmo assim?",
                    "Bexiga Mínima", MessageBoxButton.YesNo, MessageBoxImage.Warning);

                if (seguir != MessageBoxResult.Yes)
                {
                    return;
                }
            }

            // ---------------------------------------------------------------
            // Erosão. No caso "sem redução" a busca é pulada inteira: não há
            // o que procurar, e assim nem a estrutura de trabalho provisória
            // chega a ser criada.
            // ---------------------------------------------------------------
            ResultadoErosao erosao;

            if (semReducao)
            {
                erosao = new ResultadoErosao();
                erosao.Viavel = true;
                erosao.ToleranciaAtingida = true;
                erosao.IntensidadeErosaoMm = 0.0;
                erosao.VolumeCc = volumeInicialCc;
            }
            else
            {
                string erroErosao;
                erosao = EncontrarErosaoOtima(
                    bexigaSelecionada,
                    structureSet,
                    segmentoProtegido,
                    volumeAlvoCc,
                    erosaoMaximaMm,
                    toleranciaVolumeCc,
                    modeloAnisotropico,
                    out erroErosao);

                if (!erosao.Viavel)
                {
                    // Piso protegido acima do alvo é um resultado clínico, não
                    // uma falha de configuração: diz quanto de bexiga está
                    // comprometida dentro do PTV.
                    string causa = (erosao.VolumeProtegidoCc > volumeAlvoCc)
                        ? ("\nA bexiga dentro do PTV + margem (" + erosao.VolumeProtegidoCc.ToString("F1") +
                           " cc) já é maior que o volume-alvo e não pode ser reduzida. " +
                           "Esse é o mínimo possível para este caso — reveja o volume-alvo.")
                        : ("\nO alvo exige mais erosão do que a trava configurada. Aumente a " +
                           "\"intensidade máxima de erosão\" na janela (não há limite de 50 mm: a " +
                           "erosão é aplicada em passos encadeados), ou reveja o volume-alvo.");

                    MostrarMensagem(window,
                        "Não foi possível encontrar uma erosão adequada.\n\n" +
                        "Volume inicial: " + volumeInicialCc.ToString("F1") + " cc\n" +
                        "Volume-alvo: " + volumeAlvoCc.ToString("F1") + " cc\n" +
                        "Bexiga dentro do PTV + margem (intocável): " +
                        erosao.VolumeProtegidoCc.ToString("F1") + " cc\n" +
                        "Volume no limite máximo de erosão: " +
                        erosao.VolumeNaErosaoMaximaCc.ToString("F1") + " cc\n" +
                        (string.IsNullOrEmpty(erroErosao) ? "" : ("\nDetalhe: " + erroErosao + "\n")) +
                        causa,
                        "Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
            }

            // VolumeProtegidoCc só é medido durante a busca; no caso "sem
            // redução" a busca não roda, então a linha sai sem o número em vez
            // de anunciar um 0,0 cc que nunca foi medido.
            string linhaPtv = (segmentoProtegido == null)
                ? "PTV protegido: NENHUM (sem prote\u00e7\u00e3o)\n"
                : ("PTV protegido: " + descricaoPtv + "\n" +
                   (semReducao
                        ? ""
                        : "Bexiga dentro dessa regi\u00e3o (intoc\u00e1vel): " +
                          erosao.VolumeProtegidoCc.ToString("F1") + " cc\n"));

            string avisoSemReducao = semReducao
                ? ("\nSEM REDUÇÃO: a bexiga contornada (" + volumeInicialCc.ToString("F1") +
                   " cc) já está no volume-alvo (" + volumeAlvoCc.ToString("F1") +
                   " cc) ou abaixo dele, então a bexiga mínima é a própria bexiga atual " +
                   "(erosão zero). Este paciente está abaixo do protocolo de enchimento.\n")
                : "";

            string avisoTolerancia = erosao.ToleranciaAtingida
                ? ""
                : ("\nATENÇÃO: a tolerância volumétrica de " + toleranciaVolumeCc.ToString("F1") +
                   " cc não foi atingida dentro do limite máximo de erosão; usando a " +
                   "aproximação mais próxima encontrada (diferença de " +
                   Math.Abs(erosao.VolumeCc - volumeAlvoCc).ToString("F1") + " cc).\n");

            // ---------------------------------------------------------------
            // Confirmação final antes de alterar dados do paciente.
            // ---------------------------------------------------------------
            string confirmacao =
                "Criar a estrutura de bexiga mínima?\n\n" +
                "Estrutura origem: " + bexigaSelecionada.Id + "\n" +
                "Modelo: " + (modeloAnisotropico ? "Colapso da cúpula (base/posterior fixas)" : "Isotrópico (ATENÇÃO: afasta a parede do alvo)") + "\n" +
                linhaPtv + "\n" +
                "Volume inicial: " + volumeInicialCc.ToString("F1") + " cc\n" +
                "Mínimo global: " + minimoGlobalCc.ToString("F1") + " cc\n" +
                "Mínimo relativo: " + (fracaoMinimaRelativa * 100.0).ToString("F1") + "% = " +
                    volumeRelativoCc.ToString("F1") + " cc\n" +
                "Volume-alvo: " + volumeAlvoCc.ToString("F1") + " cc\n\n" +
                "Intensidade de erosão encontrada: " + erosao.IntensidadeErosaoMm.ToString("F2") + " mm\n" +
                "Volume estimado: " + erosao.VolumeCc.ToString("F1") + " cc\n" +
                avisoSemReducao + avisoTolerancia + "\n" +
                "Estrutura de saída: " + idSaida;

            MessageBoxResult confirmado = MostrarMensagem(window, confirmacao, "Confirmar criação",
                MessageBoxButton.YesNo, MessageBoxImage.Question);

            if (confirmado != MessageBoxResult.Yes)
            {
                return;
            }

            // ---------------------------------------------------------------
            // Gravação definitiva (edição já habilitada acima). A estrutura
            // de trabalho provisória usada na busca já foi removida dentro de
            // EncontrarErosaoOtima antes deste ponto.
            // ---------------------------------------------------------------
            string etapa = "preparação";
            try
            {
                if (estruturaExistente != null)
                {
                    etapa = "remoção da estrutura '" + idSaida + "' existente";
                    structureSet.RemoveStructure(estruturaExistente);
                    estruturaExistente = null;
                }

                // Recalcula o segmento a partir da intensidade vencedora. NÃO
                // reaproveitar a SegmentVolume da busca: ela passou pela
                // estrutura provisória, que já foi removida, e a ESAPI estoura
                // com "External component has thrown an exception" ao
                // atribuí-la aqui. Ver nota em ResultadoErosao.
                etapa = "cálculo do segmento final";
                SegmentVolume segmentoFinal = CalcularCandidato(
                    bexigaSelecionada, erosao.IntensidadeErosaoMm, modeloAnisotropico,
                    segmentoProtegido);

                etapa = "criação da estrutura '" + idSaida + "'";
                Structure bexigaMinima = structureSet.AddStructure(TIPO_DICOM_SAIDA, idSaida);

                etapa = "atribuição do segmento a '" + idSaida + "'";
                bexigaMinima.SegmentVolume = segmentoFinal;

                etapa = "leitura do volume final";
                double volumeFinalCc = bexigaMinima.Volume;
                double diferencaFinalCc = volumeFinalCc - volumeAlvoCc;

                string mensagemFinal =
                    "Bexiga mínima criada com sucesso.\n\n" +
                    "Estrutura origem: " + bexigaSelecionada.Id + "\n" +
                    "Modelo: " + (modeloAnisotropico ? "Colapso da cúpula" : "Isotrópico (ATENÇÃO: afasta a parede do alvo)") + "\n" +
                    linhaPtv + "\n" +
                    "Volume inicial: " + volumeInicialCc.ToString("F1") + " cc\n" +
                    "Volume-alvo: " + volumeAlvoCc.ToString("F1") + " cc\n" +
                    "Intensidade de erosão: " + erosao.IntensidadeErosaoMm.ToString("F2") + " mm\n\n" +
                    "Volume final: " + volumeFinalCc.ToString("F1") + " cc\n" +
                    "Diferença ao alvo: " + diferencaFinalCc.ToString("+0.0;-0.0;0.0") + " cc\n" +
                    avisoSemReducao + avisoTolerancia + "\n" +
                    "Estrutura criada: " + idSaida + "\n\n" +
                    (semReducao
                        ? "Confira no Eclipse: a estrutura criada deve coincidir com a bexiga " +
                          "original (cópia, sem redução)."
                        : "Confira no corte SAGITAL: a cúpula deve estar rebaixada e a base/parede " +
                          "posterior devem COINCIDIR com a bexiga original. Folga na base, ou " +
                          "corte pelo lado errado, indica problema de orientação da imagem.");

                MostrarMensagem(window, mensagemFinal, "Bexiga Mínima",
                    MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                // Identifica a etapa e o tipo da exceção: "External component
                // has thrown an exception" sozinho não diz nada sobre onde
                // quebrou, e cada diagnóstico custa um ciclo de
                // recompilar/republicar.
                string detalhe = ex.GetType().Name + ": " + ex.Message;
                if (ex.InnerException != null)
                {
                    detalhe += "\n\nExceção interna: " +
                        ex.InnerException.GetType().Name + ": " + ex.InnerException.Message;
                }

                MostrarMensagem(window,
                    "Ocorreu um erro durante a modificação do paciente.\n\n" +
                    "Etapa: " + etapa + "\n\n" + detalhe + "\n\n" +
                    "A estrutura '" + idSaida + "' pode ter ficado incompleta — " +
                    "confira no Eclipse antes de salvar.",
                    "Erro - Bexiga Mínima", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        // ====================================================================
        // MessageBox.Show(Window owner, ...) lança ArgumentNullException se
        // owner for null; o parâmetro "window" do Execute pode, em tese, vir
        // null dependendo do host. Este wrapper cai para o overload sem
        // owner nesse caso, em vez de propagar uma exceção não tratada.
        // ====================================================================
        private static MessageBoxResult MostrarMensagem(
            Window owner, string texto, string titulo, MessageBoxButton botao, MessageBoxImage icone)
        {
            return owner != null
                ? MessageBox.Show(owner, texto, titulo, botao, icone)
                : MessageBox.Show(texto, titulo, botao, icone);
        }

        // ====================================================================
        // Localiza estruturas candidatas a bexiga.
        // ====================================================================
        private List<Structure> EncontrarCandidatosBexiga(StructureSet structureSet)
        {
            List<Structure> exatos = structureSet.Structures
                .Where(s => !s.IsEmpty && NOMES_CONHECIDOS_BEXIGA.Any(nome =>
                    string.Equals(s.Id, nome, StringComparison.OrdinalIgnoreCase)))
                .ToList();

            if (exatos.Count > 0)
            {
                return exatos;
            }

            return structureSet.Structures
                .Where(s => !s.IsEmpty &&
                    (s.Id.IndexOf("bladder", StringComparison.OrdinalIgnoreCase) >= 0 ||
                     s.Id.IndexOf("bexiga", StringComparison.OrdinalIgnoreCase) >= 0))
                .ToList();
        }

        // ====================================================================
        // Opções do seletor de PTV: "(todos os PTVs)", cada PTV não vazio do
        // Structure Set, e "(nenhum)". O alvo do plano, quando é um PTV, é
        // promovido para logo depois de "(todos)" — mas o default continua
        // sendo "(todos)", que é a leitura conservadora de "a bexiga dentro
        // do PTV não pode ser reduzida" quando há mais de um PTV (caso comum
        // aqui: PTV_60 + PTV_44).
        // ====================================================================
        private static List<string> MontarOpcoesPtv(StructureSet structureSet, PlanSetup plano)
        {
            List<string> ptvs = structureSet.Structures
                .Where(s => !s.IsEmpty &&
                    string.Equals(s.DicomType, "PTV", StringComparison.OrdinalIgnoreCase))
                .Select(s => s.Id)
                .ToList();

            string alvoDoPlano = (plano != null) ? plano.TargetVolumeID : null;
            if (!string.IsNullOrEmpty(alvoDoPlano) && ptvs.Contains(alvoDoPlano))
            {
                ptvs.Remove(alvoDoPlano);
                ptvs.Insert(0, alvoDoPlano);
            }

            List<string> opcoes = new List<string>();
            if (ptvs.Count > 0)
            {
                opcoes.Add(OPCAO_TODOS_PTVS);
                opcoes.AddRange(ptvs);
            }
            opcoes.Add(OPCAO_SEM_PTV);
            return opcoes;
        }

        // ====================================================================
        // Expansão com encadeamento, pelo mesmo motivo da erosão: a ESAPI
        // limita cada margem a 50 mm por chamada.
        // ====================================================================
        private static SegmentVolume ExpandirComEncadeamento(SegmentVolume segmento, double margemMm)
        {
            SegmentVolume atual = segmento;
            double restante = margemMm;

            while (restante > 0.0)
            {
                double passo = Math.Min(restante, PASSO_MAXIMO_SEGURO_MM);
                restante -= passo;
                atual = atual.Margin(passo);
            }

            return atual;
        }

        // ====================================================================
        // Região da bexiga que NÃO pode ser reduzida: bexiga ∩ (PTV + margem).
        //
        // Regra clínica: o volume de bexiga dentro do PTV recebe dose de
        // prescrição independentemente do enchimento, e a faixa de margem ao
        // redor está no gradiente íngreme. Reduzir qualquer um dos dois
        // produziria uma bexiga mínima que "sai" da dose alta — exatamente o
        // viés otimista que este script não pode introduzir.
        //
        // Retorna null quando não há PTV selecionado ou encontrado (sem
        // proteção); o chamador avisa o usuário nesse caso.
        // ====================================================================
        private static SegmentVolume ResolverSegmentoProtegido(
            StructureSet structureSet, Structure bexiga, string selecao, double margemMm,
            out string descricao)
        {
            descricao = null;

            if (string.IsNullOrEmpty(selecao) || selecao == OPCAO_SEM_PTV)
            {
                return null;
            }

            List<Structure> alvos;
            if (selecao == OPCAO_TODOS_PTVS)
            {
                alvos = structureSet.Structures
                    .Where(s => !s.IsEmpty &&
                        string.Equals(s.DicomType, "PTV", StringComparison.OrdinalIgnoreCase))
                    .ToList();
            }
            else
            {
                alvos = structureSet.Structures
                    .Where(s => !s.IsEmpty && s.Id.Equals(selecao, StringComparison.OrdinalIgnoreCase))
                    .ToList();
            }

            if (alvos.Count == 0)
            {
                return null;
            }

            SegmentVolume uniao = alvos[0].SegmentVolume;
            for (int i = 1; i < alvos.Count; i++)
            {
                uniao = uniao.Or(alvos[i].SegmentVolume);
            }

            string nomes = string.Join(" + ", alvos.Select(a => a.Id).ToArray());

            if (margemMm > 0.0)
            {
                uniao = ExpandirComEncadeamento(uniao, margemMm);
                descricao = nomes + " + " + margemMm.ToString("F0") + " mm";
            }
            else
            {
                descricao = nomes;
            }

            return bexiga.SegmentVolume.And(uniao);
        }

        // ====================================================================
        // Candidato completo: redução + região protegida de volta. A união
        // garante que a bexiga dentro do PTV nunca é removida, qualquer que
        // seja a intensidade da erosão.
        // ====================================================================
        private static SegmentVolume CalcularCandidato(
            Structure bexiga, double intensidadeMm, bool modeloAnisotropico, SegmentVolume protegido)
        {
            SegmentVolume reduzido = CalcularSegmentoErodido(bexiga, intensidadeMm, modeloAnisotropico);
            return protegido == null ? reduzido : reduzido.Or(protegido);
        }

        // ====================================================================
        // Maior peso direcional configurado — dimensiona o passo do
        // encadeamento. INFERIOR/POSTERIOR são zero por definição, então só
        // LATERAL/SUPERIOR/ANTERIOR podem ser o máximo.
        // ====================================================================
        private static double PesoMaximo()
        {
            double maior = PESO_LATERAL;
            if (PESO_SUPERIOR > maior) maior = PESO_SUPERIOR;
            if (PESO_ANTERIOR > maior) maior = PESO_ANTERIOR;
            return maior;
        }

        // ====================================================================
        // Intensidade máxima por CHAMADA, para que nenhum eixo ultrapasse o
        // teto de margem da ESAPI depois de multiplicado pelo seu peso.
        // ====================================================================
        private static double PassoMaximoMm(bool modeloAnisotropico)
        {
            if (!modeloAnisotropico)
            {
                return PASSO_MAXIMO_SEGURO_MM;
            }

            double peso = PesoMaximo();
            return peso > 0.0 ? PASSO_MAXIMO_SEGURO_MM / peso : PASSO_MAXIMO_SEGURO_MM;
        }

        // ====================================================================
        // Calcula a SegmentVolume reduzida para uma dada intensidade "t" (mm).
        //
        // Colapso da cúpula: AsymmetricMargin ponderada por eixo, com base e
        // parede posterior em peso zero (ver PESO_* e o racional clínico no
        // cabeçalho do arquivo).
        // Isotrópico: Margin(-t) — encolhe em todas as direções, inclusive
        // afastando a parede do alvo. Só para comparação/QA.
        //
        // ENCADEAMENTO: a ESAPI limita cada operação de margem a 50 mm, o que
        // é insuficiente — uma bexiga de 700 cc precisa de muito mais que isso
        // para cair à metade com a base fixa. Erosão morfológica com elemento
        // estruturante alinhado aos eixos é aditiva ((A⊖B1)⊖B2 = A⊖(B1⊕B2)),
        // então intensidades maiores são aplicadas em passos sucessivos sobre
        // o resultado anterior, o que é equivalente a uma erosão única do
        // total e remove o teto de 50 mm do problema.
        // ====================================================================
        private static SegmentVolume CalcularSegmentoErodido(
            Structure bexiga, double intensidadeMm, bool modeloAnisotropico)
        {
            if (intensidadeMm <= 0.0)
            {
                return bexiga.SegmentVolume;
            }

            double passoMaximo = PassoMaximoMm(modeloAnisotropico);
            SegmentVolume atual = bexiga.SegmentVolume;
            double restante = intensidadeMm;

            while (restante > 0.0)
            {
                double passo = Math.Min(restante, passoMaximo);
                restante -= passo;

                if (!modeloAnisotropico)
                {
                    atual = atual.Margin(-passo);
                    continue;
                }

                AxisAlignedMargins margens = new AxisAlignedMargins(
                    StructureMarginGeometry.Inner,
                    passo * PESO_LATERAL,    // X1 (-X)
                    passo * PESO_ANTERIOR,   // Y1 (-Y, anterior)
                    passo * PESO_INFERIOR,   // Z1 (-Z, inferior/trígono)
                    passo * PESO_LATERAL,    // X2 (+X)
                    passo * PESO_POSTERIOR,  // Y2 (+Y, posterior)
                    passo * PESO_SUPERIOR);  // Z2 (+Z, superior/cúpula)

                atual = atual.AsymmetricMargin(margens);
            }

            return atual;
        }

        // ====================================================================
        // Cria a estrutura de trabalho provisória usada para leitura de
        // volume durante a busca (ver nota em ID_ESTRUTURA_PROVISORIA).
        // Remove qualquer sobra homônima de uma execução anterior
        // interrompida antes de recriar.
        // ====================================================================
        private static Structure PrepararEstruturaProvisoria(StructureSet structureSet)
        {
            Structure sobra = structureSet.Structures.FirstOrDefault(s =>
                s.Id.Equals(ID_ESTRUTURA_PROVISORIA, StringComparison.OrdinalIgnoreCase));
            if (sobra != null)
            {
                structureSet.RemoveStructure(sobra);
            }

            if (!structureSet.CanAddStructure(TIPO_DICOM_PROVISORIA, ID_ESTRUTURA_PROVISORIA))
            {
                throw new ApplicationException(
                    "o Eclipse não permite criar a estrutura de trabalho '" +
                    ID_ESTRUTURA_PROVISORIA + "'.");
            }

            return structureSet.AddStructure(TIPO_DICOM_PROVISORIA, ID_ESTRUTURA_PROVISORIA);
        }

        // ====================================================================
        // Lê o volume (cc) de uma SegmentVolume candidata. A ESAPI não expõe
        // volume diretamente em SegmentVolume — só em Structure — então a
        // candidata é atribuída à estrutura de trabalho provisória e o
        // volume é lido de lá.
        // ====================================================================
        private static double LerVolumeCc(Structure provisoria, SegmentVolume segmento)
        {
            provisoria.SegmentVolume = segmento;
            return provisoria.Volume;
        }

        // ====================================================================
        // Busca binária pela intensidade de erosão cujo volume resultante mais
        // se aproxima do volume-alvo, dentro do limite máximo configurado.
        // ====================================================================
        private ResultadoErosao EncontrarErosaoOtima(
            Structure bexiga,
            StructureSet structureSet,
            SegmentVolume segmentoProtegido,
            double volumeAlvoCc,
            double erosaoMaximaMm,
            double toleranciaVolumeCc,
            bool modeloAnisotropico,
            out string erroDetalhe)
        {
            erroDetalhe = null;
            ResultadoErosao resultado = new ResultadoErosao();

            Structure provisoria;
            try
            {
                provisoria = PrepararEstruturaProvisoria(structureSet);
            }
            catch (Exception ex)
            {
                resultado.Viavel = false;
                erroDetalhe = "Não foi possível criar a estrutura de trabalho provisória: " + ex.Message;
                return resultado;
            }

            try
            {
                // Volume da região protegida (bexiga dentro do PTV): é o piso
                // absoluto do que a estrutura pode ter.
                if (segmentoProtegido != null)
                {
                    try
                    {
                        resultado.VolumeProtegidoCc = LerVolumeCc(provisoria, segmentoProtegido);
                    }
                    catch (Exception ex)
                    {
                        resultado.Viavel = false;
                        erroDetalhe = "Falha ao medir a bexiga dentro do PTV: " + ex.Message;
                        return resultado;
                    }
                }

                SegmentVolume segmentoMaximo;
                double volumeErosaoMaxima;

                try
                {
                    segmentoMaximo = CalcularCandidato(
                        bexiga, erosaoMaximaMm, modeloAnisotropico, segmentoProtegido);
                    volumeErosaoMaxima = LerVolumeCc(provisoria, segmentoMaximo);
                }
                catch (Exception ex)
                {
                    resultado.Viavel = false;
                    erroDetalhe = "Falha ao avaliar a erosão máxima (" + erosaoMaximaMm.ToString("F1") +
                        " mm): " + ex.Message;
                    return resultado;
                }

                resultado.VolumeNaErosaoMaximaCc = volumeErosaoMaxima;

                // O alvo é inatingível dentro do limite máximo de erosão.
                if (volumeErosaoMaxima > volumeAlvoCc)
                {
                    resultado.Viavel = false;
                    return resultado;
                }

                double melhorIntensidade = erosaoMaximaMm;
                double melhorVolume = volumeErosaoMaxima;
                double melhorDiferenca = Math.Abs(volumeErosaoMaxima - volumeAlvoCc);

                double limiteInferior = 0.0;
                double limiteSuperior = erosaoMaximaMm;

                for (int i = 0; i < MAX_ITERACOES_BUSCA; i++)
                {
                    double meio = (limiteInferior + limiteSuperior) / 2.0;

                    double volumeCandidato;
                    try
                    {
                        SegmentVolume segmentoCandidato = CalcularCandidato(
                            bexiga, meio, modeloAnisotropico, segmentoProtegido);
                        volumeCandidato = LerVolumeCc(provisoria, segmentoCandidato);

                        double diferenca = Math.Abs(volumeCandidato - volumeAlvoCc);
                        if (diferenca < melhorDiferenca)
                        {
                            melhorDiferenca = diferenca;
                            melhorIntensidade = meio;
                            melhorVolume = volumeCandidato;
                        }

                        if (diferenca <= toleranciaVolumeCc)
                        {
                            break;
                        }
                    }
                    catch (Exception)
                    {
                        // Erosão excessiva/inválida nesse ponto do intervalo: trata
                        // como volume nulo, empurrando a busca para menos erosão.
                        volumeCandidato = 0.0;
                    }

                    if (volumeCandidato > volumeAlvoCc)
                    {
                        limiteInferior = meio;
                    }
                    else
                    {
                        limiteSuperior = meio;
                    }

                    if (limiteSuperior - limiteInferior < LARGURA_MINIMA_INTERVALO_MM)
                    {
                        break;
                    }
                }

                resultado.Viavel = true;
                resultado.ToleranciaAtingida = melhorDiferenca <= toleranciaVolumeCc;
                resultado.IntensidadeErosaoMm = melhorIntensidade;
                resultado.VolumeCc = melhorVolume;

                return resultado;
            }
            finally
            {
                // A provisória sempre é removida, tenha a busca dado certo ou
                // não; a estrutura definitiva (se houver) só é criada depois
                // da confirmação do usuário, em Execute().
                structureSet.RemoveStructure(provisoria);
            }
        }
    }

    // =========================================================================
    // Resultado da busca de erosão.
    //
    // Guarda só a INTENSIDADE (mm) vencedora, não a SegmentVolume calculada
    // durante a busca: aquela foi atribuída à estrutura de trabalho
    // provisória, que é removida ao final da busca — reaproveitá-la depois
    // disso fazia a ESAPI estourar com "External component has thrown an
    // exception" na criação da estrutura definitiva. O segmento final é
    // recalculado a partir da intensidade, já com a provisória fora do jogo.
    // =========================================================================
    public class ResultadoErosao
    {
        public bool Viavel { get; set; }
        public bool ToleranciaAtingida { get; set; }
        public double IntensidadeErosaoMm { get; set; }
        public double VolumeCc { get; set; }
        public double VolumeNaErosaoMaximaCc { get; set; }

        // Volume da bexiga dentro do PTV — piso absoluto da estrutura, já que
        // essa região nunca é reduzida. Zero quando não há PTV protegido.
        public double VolumeProtegidoCc { get; set; }
    }

    // =========================================================================
    // Janela de configuração (WPF construída em código para manter o
    // plug-in autocontido em um único arquivo .cs).
    // =========================================================================
    public class JanelaBexigaMinima : Window
    {
        public Structure BexigaSelecionada { get; private set; }
        public double MinimoGlobalCc { get; private set; }
        public double MinimoRelativoPct { get; private set; }
        public double ErosaoMaximaMm { get; private set; }
        public double ToleranciaVolumeCc { get; private set; }
        public string IdEstruturaSaida { get; private set; }
        public bool SubstituirExistente { get; private set; }
        public bool ModeloAnisotropico { get; private set; }
        public string SelecaoPtv { get; private set; }
        public double MargemPtvMm { get; private set; }

        private readonly StructureSet structureSet;
        private readonly int limiteCaracteresId;
        private readonly double limiteIntensidadeMm;

        private ComboBox comboBexiga;
        private ComboBox comboPtv;
        private TextBox campoMargemPtv;
        private TextBox campoMinimoGlobal;
        private TextBox campoMinimoRelativo;
        private TextBox campoErosaoMaxima;
        private TextBox campoTolerancia;
        private TextBox campoIdSaida;
        private CheckBox checkSubstituir;
        private CheckBox checkModeloAnisotropico;
        private TextBlock textoPreview;

        public JanelaBexigaMinima(
            List<Structure> candidatos,
            List<string> opcoesPtv,
            StructureSet structureSet,
            double defaultMinimoGlobalCc,
            double defaultMinimoRelativoPct,
            double defaultErosaoMaximaMm,
            double defaultMargemPtvMm,
            double defaultToleranciaCc,
            string defaultIdSaida,
            bool defaultModeloAnisotropico,
            int limiteCaracteresId,
            double limiteIntensidadeMm)
        {
            this.structureSet = structureSet;
            this.limiteCaracteresId = limiteCaracteresId;
            this.limiteIntensidadeMm = limiteIntensidadeMm;

            Title = "Bexiga Mínima - ESAPI 15.6";
            Width = 540;

            // Sem altura fixa: a janela cresce conforme o conteúdo, mas nunca
            // passa de 90% da área útil da tela. Altura fixa cortava a
            // pré-visualização e escondia os botões em sessão Citrix/tela
            // menor. Permitir redimensionar dá saída manual se ainda faltar
            // espaço.
            SizeToContent = SizeToContent.Height;
            MaxHeight = SystemParameters.WorkArea.Height * 0.9;
            ResizeMode = ResizeMode.CanResize;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;

            StackPanel painel = new StackPanel();
            painel.Margin = new Thickness(20);

            TextBlock titulo = new TextBlock();
            titulo.Text = "Gerador de Bexiga Mínima";
            titulo.FontSize = 20;
            titulo.FontWeight = FontWeights.Bold;
            titulo.Margin = new Thickness(0, 0, 0, 15);
            painel.Children.Add(titulo);

            painel.Children.Add(CriarRotulo("Estrutura da bexiga:"));
            comboBexiga = new ComboBox();
            comboBexiga.Height = 28;
            foreach (Structure s in candidatos)
            {
                comboBexiga.Items.Add(s.Id);
            }
            comboBexiga.SelectedIndex = 0;
            comboBexiga.SelectionChanged += delegate { AtualizarPreview(); };
            painel.Children.Add(comboBexiga);

            painel.Children.Add(CriarRotulo("PTV protegido (bexiga dentro dele + margem n\u00e3o \u00e9 reduzida):"));
            comboPtv = new ComboBox();
            comboPtv.Height = 28;
            foreach (string id in opcoesPtv)
            {
                comboPtv.Items.Add(id);
            }
            comboPtv.SelectedIndex = 0;
            painel.Children.Add(comboPtv);

            painel.Children.Add(CriarRotulo("Margem ao redor do PTV tamb\u00e9m preservada (mm):"));
            campoMargemPtv = CriarCampo(defaultMargemPtvMm.ToString("F0"));
            painel.Children.Add(campoMargemPtv);

            painel.Children.Add(CriarRotulo("Mínimo volumétrico global (cc):"));
            campoMinimoGlobal = CriarCampo(defaultMinimoGlobalCc.ToString("F0"));
            campoMinimoGlobal.TextChanged += delegate { AtualizarPreview(); };
            painel.Children.Add(campoMinimoGlobal);

            painel.Children.Add(CriarRotulo("Mínimo relativo ao volume inicial (%):"));
            campoMinimoRelativo = CriarCampo(defaultMinimoRelativoPct.ToString("F0"));
            campoMinimoRelativo.TextChanged += delegate { AtualizarPreview(); };
            painel.Children.Add(campoMinimoRelativo);

            painel.Children.Add(CriarRotulo("Intensidade máxima de erosão (mm) — trava de segurança:"));
            campoErosaoMaxima = CriarCampo(defaultErosaoMaximaMm.ToString("F0"));
            painel.Children.Add(campoErosaoMaxima);

            painel.Children.Add(CriarRotulo("Tolerância volumétrica (cc):"));
            campoTolerancia = CriarCampo(defaultToleranciaCc.ToString("F1"));
            painel.Children.Add(campoTolerancia);

            painel.Children.Add(CriarRotulo("ID da estrutura de saída (máx. " + limiteCaracteresId + " caracteres):"));
            campoIdSaida = CriarCampo(defaultIdSaida);
            campoIdSaida.MaxLength = limiteCaracteresId;
            painel.Children.Add(campoIdSaida);

            checkModeloAnisotropico = new CheckBox();
            checkModeloAnisotropico.Content = "Colapso da cúpula (base e parede posterior fixas)";
            checkModeloAnisotropico.IsChecked = defaultModeloAnisotropico;
            checkModeloAnisotropico.Margin = new Thickness(0, 15, 0, 0);
            painel.Children.Add(checkModeloAnisotropico);

            TextBlock notaModelo = new TextBlock();
            notaModelo.Text =
                "Recomendado: o volume sai pela cúpula, e a base/trígono e a parede " +
                "posterior ficam onde estão — a parede voltada para o alvo não se " +
                "afasta da dose alta. Desmarcar usa erosão isotrópica, que encolhe em " +
                "todas as direções e AFASTA a parede do PTV (viés otimista): só para " +
                "comparação/QA, não para decisão clínica.";
            notaModelo.TextWrapping = TextWrapping.Wrap;
            notaModelo.FontSize = 11;
            notaModelo.Foreground = System.Windows.Media.Brushes.DimGray;
            notaModelo.Margin = new Thickness(0, 3, 0, 10);
            painel.Children.Add(notaModelo);

            checkSubstituir = new CheckBox();
            checkSubstituir.Content = "Substituir estrutura existente";
            checkSubstituir.Margin = new Thickness(0, 0, 0, 10);
            painel.Children.Add(checkSubstituir);

            GroupBox grupoPreview = new GroupBox();
            grupoPreview.Header = "Pré-visualização";
            grupoPreview.Margin = new Thickness(0, 10, 0, 10);
            textoPreview = new TextBlock();
            textoPreview.Margin = new Thickness(10);
            textoPreview.TextWrapping = TextWrapping.Wrap;
            grupoPreview.Content = textoPreview;
            painel.Children.Add(grupoPreview);

            StackPanel painelBotoes = new StackPanel();
            painelBotoes.Orientation = Orientation.Horizontal;
            painelBotoes.HorizontalAlignment = HorizontalAlignment.Right;
            painelBotoes.Margin = new Thickness(20, 10, 20, 15);

            Button botaoCancelar = new Button();
            botaoCancelar.Content = "Cancelar";
            botaoCancelar.Width = 100;
            botaoCancelar.Height = 30;
            botaoCancelar.Margin = new Thickness(5);
            botaoCancelar.Click += delegate { DialogResult = false; };

            Button botaoCriar = new Button();
            botaoCriar.Content = "Criar Bexiga Mínima";
            botaoCriar.Width = 160;
            botaoCriar.Height = 30;
            botaoCriar.Margin = new Thickness(5);
            botaoCriar.Click += BotaoCriar_Click;

            painelBotoes.Children.Add(botaoCancelar);
            painelBotoes.Children.Add(botaoCriar);

            // Botões ancorados no rodapé, FORA da área de rolagem: continuam
            // visíveis mesmo quando o conteúdo não cabe na tela. O resto vai
            // num ScrollViewer.
            DockPanel raiz = new DockPanel();
            DockPanel.SetDock(painelBotoes, Dock.Bottom);
            raiz.Children.Add(painelBotoes);

            ScrollViewer rolagem = new ScrollViewer();
            rolagem.VerticalScrollBarVisibility = ScrollBarVisibility.Auto;
            rolagem.Content = painel;
            raiz.Children.Add(rolagem);

            Content = raiz;

            AtualizarPreview();
        }

        private TextBlock CriarRotulo(string texto)
        {
            TextBlock rotulo = new TextBlock();
            rotulo.Text = texto;
            rotulo.Margin = new Thickness(0, 10, 0, 3);
            return rotulo;
        }

        private TextBox CriarCampo(string texto)
        {
            TextBox campo = new TextBox();
            campo.Text = texto;
            campo.Height = 26;
            return campo;
        }

        private void AtualizarPreview()
        {
            try
            {
                if (comboBexiga == null || comboBexiga.SelectedItem == null || textoPreview == null)
                {
                    return;
                }

                string idSelecionado = comboBexiga.SelectedItem.ToString();
                Structure bexiga = structureSet.Structures.FirstOrDefault(s => s.Id == idSelecionado);
                if (bexiga == null)
                {
                    return;
                }

                double minimoGlobal;
                double percentualRelativo;
                if (!double.TryParse(campoMinimoGlobal.Text, out minimoGlobal)) return;
                if (!double.TryParse(campoMinimoRelativo.Text, out percentualRelativo)) return;

                double volumeInicial = bexiga.Volume;
                double volumeRelativo = volumeInicial * percentualRelativo / 100.0;
                double volumeAlvo = Math.Max(minimoGlobal, volumeRelativo);

                textoPreview.Text =
                    "Bexiga selecionada: " + bexiga.Id + "\n\n" +
                    "Volume inicial: " + volumeInicial.ToString("F1") + " cc\n\n" +
                    "Mínimo global: " + minimoGlobal.ToString("F1") + " cc\n" +
                    "Mínimo relativo: " + percentualRelativo.ToString("F1") + "% = " +
                        volumeRelativo.ToString("F1") + " cc\n\n" +
                    "VOLUME-ALVO: " + volumeAlvo.ToString("F1") + " cc" +
                    (volumeAlvo >= volumeInicial
                        ? "\n\nSEM REDUÇÃO: a bexiga já está no alvo ou abaixo dele. " +
                          "A estrutura será uma cópia da bexiga atual (erosão zero). " +
                          "Paciente abaixo do protocolo de enchimento."
                        : "");
            }
            catch
            {
                // Erros de preview são ignorados: não alteram dados do paciente.
            }
        }

        private void BotaoCriar_Click(object sender, RoutedEventArgs e)
        {
            double minimoGlobal, percentualRelativo, erosaoMaxima, tolerancia, margemPtv;

            if (!double.TryParse(campoMinimoGlobal.Text, out minimoGlobal))
            { ErroEntrada("Mínimo global inválido."); return; }

            if (!double.TryParse(campoMinimoRelativo.Text, out percentualRelativo))
            { ErroEntrada("Percentual relativo inválido."); return; }

            if (!double.TryParse(campoErosaoMaxima.Text, out erosaoMaxima))
            { ErroEntrada("Erosão máxima inválida."); return; }

            if (!double.TryParse(campoTolerancia.Text, out tolerancia))
            { ErroEntrada("Tolerância volumétrica inválida."); return; }

            if (!double.TryParse(campoMargemPtv.Text, out margemPtv))
            { ErroEntrada("Margem do PTV inválida."); return; }

            if (margemPtv < 0.0 || margemPtv > limiteIntensidadeMm)
            { ErroEntrada("A margem do PTV deve estar entre 0 e " + limiteIntensidadeMm.ToString("F0") + " mm."); return; }

            if (minimoGlobal <= 0.0)
            { ErroEntrada("O mínimo global deve ser maior que zero."); return; }

            if (percentualRelativo <= 0.0 || percentualRelativo > 100.0)
            { ErroEntrada("O percentual relativo deve estar entre 0 e 100%."); return; }

            if (erosaoMaxima <= 0.0 || erosaoMaxima > limiteIntensidadeMm)
            { ErroEntrada("A erosão máxima deve estar entre 0 e " + limiteIntensidadeMm.ToString("F0") + " mm."); return; }

            if (tolerancia <= 0.0)
            { ErroEntrada("A tolerância deve ser maior que zero."); return; }

            if (comboBexiga.SelectedItem == null)
            { ErroEntrada("Selecione uma estrutura de bexiga."); return; }

            bool modeloAnisotropico = checkModeloAnisotropico.IsChecked == true;

            string idSaida = campoIdSaida.Text.Trim();
            if (string.IsNullOrEmpty(idSaida))
            { ErroEntrada("O ID da estrutura de saída não pode estar vazio."); return; }

            if (idSaida.Length > limiteCaracteresId)
            { ErroEntrada("O ID da estrutura de saída excede " + limiteCaracteresId + " caracteres."); return; }

            string idSelecionado = comboBexiga.SelectedItem.ToString();

            BexigaSelecionada = structureSet.Structures.FirstOrDefault(s => s.Id == idSelecionado);
            MinimoGlobalCc = minimoGlobal;
            MinimoRelativoPct = percentualRelativo;
            ErosaoMaximaMm = erosaoMaxima;
            ToleranciaVolumeCc = tolerancia;
            IdEstruturaSaida = idSaida;
            SubstituirExistente = checkSubstituir.IsChecked == true;
            ModeloAnisotropico = modeloAnisotropico;
            SelecaoPtv = comboPtv.SelectedItem == null ? null : comboPtv.SelectedItem.ToString();
            MargemPtvMm = margemPtv;

            DialogResult = true;
        }

        private void ErroEntrada(string mensagem)
        {
            MessageBox.Show(this, mensagem, "Entrada inválida", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }
}
