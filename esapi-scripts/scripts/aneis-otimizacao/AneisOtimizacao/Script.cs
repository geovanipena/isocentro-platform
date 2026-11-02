using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Windows;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

// Sem este atributo o plug-in nasce read-only: compila igual, e falha na
// PRIMEIRA escrita, em tempo de execução, com o paciente aberto na tela.
[assembly: ESAPIScript(IsWriteable = true)]

namespace VMS.TPS
{
    public class Script
    {
        const string NOME = "Anéis de otimização";

        // Margens em MILÍMETROS — a API inteira trabalha em mm, enquanto a
        // conversa clínica é em cm. É uma casa decimal entre um anel de 2 cm e
        // um de 20 cm, e nenhuma das duas versões dá erro.
        //
        //   Anel1: da superfície dos PTVs + 2 mm até + 2 cm   (casca de 18 mm)
        //   Anel2: de + 2 cm            até + 4 cm            (casca de 20 mm)
        //
        // O interno do Anel2 é igual ao externo do Anel1 de propósito: os dois
        // encostam sem lacuna e sem sobreposição.
        const double ANEL1_INTERNO = 2.0;
        const double ANEL1_EXTERNO = 20.0;
        const double ANEL2_INTERNO = 20.0;
        const double ANEL2_EXTERNO = 40.0;

        const string ANEL1_ID = "Anel1";
        const string ANEL2_ID = "Anel2";

        // CONTROL é o tipo DICOM das estruturas que existem para guiar o
        // otimizador e não representam anatomia nenhuma.
        const string TIPO_DICOM = "CONTROL";

        public Script()
        {
        }

        public void Execute(ScriptContext context)
        {
            if (context.Patient == null || context.StructureSet == null)
            {
                Avisar("Abra um paciente com imagem e structure set antes de rodar o script.");
                return;
            }

            StructureSet ss = context.StructureSet;

            // ---------------------------------------------------------------
            // Contorno externo
            // ---------------------------------------------------------------
            // Achado pelo TIPO DICOM, não pelo Id: o nome muda de serviço para
            // serviço e de versão para versão (BODY, External, Corpo), o tipo
            // EXTERNAL é o mesmo em todos.
            Structure corpo = ss.Structures.FirstOrDefault(s => s.DicomType == "EXTERNAL");
            if (corpo == null || corpo.IsEmpty)
            {
                Avisar("Não há contorno externo (tipo EXTERNAL) preenchido neste structure set.\n\n" +
                       "Os anéis são cortados por ele — sem isso, um anel de 4 cm sai da pele e " +
                       "fica no ar, e o otimizador tenta poupar um volume que não existe.");
                return;
            }

            // ---------------------------------------------------------------
            // Quais PTVs entram na soma
            // ---------------------------------------------------------------
            // Quem escolhe é o usuário. Filtro automático por prefixo "PTV"
            // pegaria junto PTV_eval, PTV-2mm e as auxiliares de casos
            // anteriores que ficaram no structure set — e um PTV a mais ou a
            // menos muda os dois anéis inteiros, em silêncio.
            List<Structure> candidatos = ss.Structures
                .Where(s => !s.IsEmpty && s.DicomType != "EXTERNAL")
                .OrderBy(s => s.Id, StringComparer.CurrentCultureIgnoreCase)
                .ToList();

            if (candidatos.Count == 0)
            {
                Avisar("Este structure set não tem nenhuma estrutura preenchida além do contorno externo.");
                return;
            }

            var janela = new JanelaEscolha(candidatos, ANEL1_ID, ANEL2_ID);
            if (janela.ShowDialog() != true)
                return;                                  // cancelado pelo usuário

            List<Structure> ptvs = janela.Escolhidos;

            // ---------------------------------------------------------------
            // Resolução
            // ---------------------------------------------------------------
            // Não se opera entre resolução padrão e alta resolução: o Or e o
            // And lançam exceção. Recusar agora, com os nomes na tela, é muito
            // melhor que estourar no meio da criação — lá, o Anel1 já estaria
            // gravado e o Anel2 não.
            var envolvidas = new List<Structure>(ptvs) { corpo };
            var alta = envolvidas.Where(s => s.IsHighResolution).ToList();
            var baixa = envolvidas.Where(s => !s.IsHighResolution).ToList();
            if (alta.Count > 0 && baixa.Count > 0)
            {
                Avisar("As estruturas escolhidas misturam resolução alta e padrão, e a API não " +
                       "opera entre as duas.\n\n" +
                       "Alta resolução: " + string.Join(", ", alta.Select(s => s.Id)) + "\n" +
                       "Resolução padrão: " + string.Join(", ", baixa.Select(s => s.Id)) + "\n\n" +
                       "Uniformize a resolução no Eclipse e rode de novo.");
                return;
            }

            // ---------------------------------------------------------------
            // Os anéis já existem?
            // ---------------------------------------------------------------
            var jaExistem = new[] { ANEL1_ID, ANEL2_ID }
                .Select(id => ss.Structures.FirstOrDefault(s => s.Id == id))
                .Where(s => s != null)
                .ToList();

            // Anel que já existe e está travado (aprovado, em plano aprovado)
            // precisa parar o script ANTES de qualquer escrita. O
            // CanEditSegmentVolume devolve junto o motivo — e o motivo é
            // justamente o que o usuário precisa para resolver sozinho.
            foreach (Structure existente in jaExistem)
            {
                string motivo;
                if (!existente.CanEditSegmentVolume(out motivo))
                {
                    Avisar("'" + existente.Id + "' já existe e não pode ser modificada.\n\n" +
                           "Motivo: " + motivo + "\n\n" +
                           "Resolva no Eclipse — desaprovar ou renomear — e rode de novo.");
                    return;
                }
            }

            if (jaExistem.Count > 0)
            {
                bool substituir = Perguntar(
                    "Já existe(m) " + string.Join(" e ", jaExistem.Select(s => "'" + s.Id + "'")) +
                    " neste structure set.\n\nSubstituir o conteúdo?");
                if (!substituir)
                    return;
            }

            // ---------------------------------------------------------------
            // Escrita
            // ---------------------------------------------------------------
            // BeginModifications vem ANTES de qualquer pergunta sobre escrita.
            // O CanAddStructure responde sobre o estado ATUAL do paciente, e num
            // paciente que ainda não foi aberto para modificação a resposta é
            // sempre "não" — a recusa não fala do structure set, fala do modo.
            //
            // Pago em 03/09/2026, na primeira rodada real: a tela culpou o teto
            // de 99 estruturas num structure set que tinha 13. Chamar cedo não
            // grava nada, só habilita.
            context.Patient.BeginModifications();

            // Só agora a pergunta significa alguma coisa.
            foreach (string id in new[] { ANEL1_ID, ANEL2_ID })
            {
                if (ss.Structures.Any(s => s.Id == id))
                    continue;
                if (!ss.CanAddStructure(TIPO_DICOM, id))
                {
                    Avisar(Diagnostico(ss, id));
                    return;
                }
            }

            // União dos PTVs escolhidos. Fica só como SegmentVolume: a soma é
            // material de trabalho, não uma estrutura para o structure set.
            SegmentVolume soma = ptvs[0].SegmentVolume;
            for (int i = 1; i < ptvs.Count; i++)
                soma = soma.Or(ptvs[i].SegmentVolume);

            Structure anel1 = ObterOuCriar(ss, ANEL1_ID);
            anel1.SegmentVolume = Casca(soma, corpo, ANEL1_INTERNO, ANEL1_EXTERNO);

            Structure anel2 = ObterOuCriar(ss, ANEL2_ID);
            anel2.SegmentVolume = Casca(soma, corpo, ANEL2_INTERNO, ANEL2_EXTERNO);

            // ---------------------------------------------------------------
            // Conferência
            // ---------------------------------------------------------------
            // Operação booleana que não sobrepõe nada devolve estrutura VAZIA,
            // não erro. Sem esta checagem, "o script rodou" e "o script
            // funcionou" ficam indistinguíveis.
            var vazios = new[] { anel1, anel2 }.Where(s => s.IsEmpty).ToList();

            var msg = new StringBuilder();
            msg.AppendLine("PTVs somados: " + string.Join(", ", ptvs.Select(s => s.Id)));
            msg.AppendLine("Cortados por: " + corpo.Id);
            msg.AppendLine();
            msg.AppendLine(string.Format("{0}   ({1:0} a {2:0} mm)   {3:0.00} cm³",
                anel1.Id, ANEL1_INTERNO, ANEL1_EXTERNO, anel1.Volume));
            msg.AppendLine(string.Format("{0}   ({1:0} a {2:0} mm)   {3:0.00} cm³",
                anel2.Id, ANEL2_INTERNO, ANEL2_EXTERNO, anel2.Volume));

            if (vazios.Count > 0)
            {
                msg.AppendLine();
                msg.AppendLine("ATENÇÃO: " + string.Join(" e ", vazios.Select(s => s.Id)) +
                               " saiu(ram) VAZIO(S). Confira a escolha dos PTVs e o contorno externo.");
                Avisar(msg.ToString());
            }
            else
            {
                MessageBox.Show(msg.ToString(), NOME, MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        /// <summary>
        /// Quando o CanAddStructure recusa, a tela precisa dizer o que foi
        /// TESTADO, não chutar uma causa. A primeira versão afirmava o teto de
        /// 99 estruturas e imprimia "ele tem 13" na linha seguinte — uma
        /// mensagem que se contradiz manda o usuário procurar no lugar errado.
        /// </summary>
        static string Diagnostico(StructureSet ss, string id)
        {
            var sb = new StringBuilder();
            sb.AppendLine("Não é possível criar '" + id + "' neste structure set.");
            sb.AppendLine();
            sb.AppendLine("Estruturas hoje: " + ss.Structures.Count() + "   (o teto é 99)");
            sb.AppendLine();
            sb.AppendLine("Tipos DICOM testados agora, neste structure set:");
            foreach (string t in new[] { "CONTROL", "AVOIDANCE", "ORGAN", "PTV", "DOSE_REGION" })
                sb.AppendLine("     " + (ss.CanAddStructure(t, id) ? "aceito  " : "recusado") + "   " + t);
            sb.AppendLine();
            sb.AppendLine("Se algum foi aceito, basta trocar TIPO_DICOM no script.");
            sb.AppendLine("Se TODOS foram recusados, o structure set está travado para escrita: " +
                          "aprovado, ou preso a um plano aprovado.");
            return sb.ToString();
        }

        /// <summary>
        /// Casca entre duas expansões da soma, cortada pelo contorno externo.
        /// </summary>
        static SegmentVolume Casca(SegmentVolume soma, Structure corpo,
                                   double interno, double externo)
        {
            // O And com o corpo vem por último, sobre um volume já reduzido
            // pela subtração — mesmo resultado, menos trabalho.
            return soma.Margin(externo)
                       .Sub(soma.Margin(interno))
                       .And(corpo.SegmentVolume);
        }

        /// <summary>
        /// Reaproveita a estrutura existente em vez de remover e recriar: assim
        /// a cor e o tipo que o serviço já ajustou sobrevivem a uma segunda
        /// rodada do script.
        /// </summary>
        static Structure ObterOuCriar(StructureSet ss, string id)
        {
            Structure existente = ss.Structures.FirstOrDefault(s => s.Id == id);
            return existente ?? ss.AddStructure(TIPO_DICOM, id);
        }

        static void Avisar(string texto)
        {
            MessageBox.Show(texto, NOME, MessageBoxButton.OK, MessageBoxImage.Exclamation);
        }

        static bool Perguntar(string texto)
        {
            return MessageBox.Show(texto, NOME, MessageBoxButton.YesNo, MessageBoxImage.Question)
                   == MessageBoxResult.Yes;
        }
    }
}
