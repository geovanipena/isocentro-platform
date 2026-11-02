using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

namespace VMS.TPS
{
    /// <summary>
    /// A sonda existe porque a ESAPI 15.6 não tem catálogo: não dá para
    /// perguntar quais máquinas, energias, taxas e técnicas o serviço tem
    /// configuradas. Quando o AddBeam responde "External beam configuration not
    /// found", ele não diz QUAL das cinco strings não bate — e adivinhar de
    /// fora, uma tentativa por vez, custa uma ida à clínica por palpite.
    ///
    /// Então em vez de adivinhar: lê tudo o que a API sabe sobre os campos que
    /// JÁ existem, e experimenta as combinações num plano temporário que é
    /// apagado no fim. O que sobra é a lista das combinações que o Eclipse
    /// ACEITA — não um palpite sobre elas.
    ///
    /// Nada disto entra no caminho normal do script: é ferramenta de
    /// diagnóstico, atrás de um botão.
    /// </summary>
    public static class Sonda
    {
        /// <summary>
        /// Teto de tentativas. A varredura é rápida (a recusa é imediata, e não
        /// grava nada), mas um teto evita que uma lista grande de planos vire
        /// uma espera de minutos com o Eclipse travado.
        /// </summary>
        const int MAXIMO_DE_TENTATIVAS = 240;

        /// <summary>
        /// Quantas combinações boas bastam. Cada acerto cria um campo de
        /// verdade no plano temporário; cinco já dizem o que precisa ser dito.
        /// </summary>
        const int ACERTOS_QUE_BASTAM = 5;

        // -------------------------------------------------------------------
        // Leitura — não escreve nada
        // -------------------------------------------------------------------

        /// <summary>
        /// Tudo o que a API sabe sobre os campos que já existem no paciente.
        ///
        /// Inclui Id E Name da técnica de propósito: o EnergyModeDisplayName já
        /// se mostrou um nome de EXIBIÇÃO, e não um identificador — pode ser
        /// que o Technique.Id também seja.
        /// </summary>
        public static string Inventario(Patient paciente)
        {
            var sb = new StringBuilder();
            sb.AppendLine("CAMPOS QUE JÁ EXISTEM NESTE PACIENTE");
            sb.AppendLine();

            int quantos = 0;
            foreach (Course curso in paciente.Courses)
            {
                foreach (ExternalPlanSetup plano in curso.PlanSetups.OfType<ExternalPlanSetup>())
                {
                    foreach (Beam feixe in plano.Beams)
                    {
                        if (feixe.IsSetupField)
                            continue;

                        quantos++;
                        sb.AppendLine(curso.Id + " / " + plano.Id + " / " + feixe.Id);
                        Linha(sb, "máquina Id", Ler(() => feixe.TreatmentUnit.Id));
                        Linha(sb, "máquina Name", Ler(() => feixe.TreatmentUnit.Name));
                        Linha(sb, "modelo", Ler(() => feixe.TreatmentUnit.MachineModel));
                        Linha(sb, "escala", Ler(() => feixe.TreatmentUnit.MachineScaleDisplayName));
                        Linha(sb, "energia (exibição)", Ler(() => feixe.EnergyModeDisplayName));
                        Linha(sb, "taxa de dose", Ler(() => feixe.DoseRate.ToString()));
                        Linha(sb, "técnica Id", Ler(() => feixe.Technique.Id));
                        Linha(sb, "técnica Name", Ler(() => feixe.Technique.Name));
                        Linha(sb, "MLCPlanType", Ler(() => feixe.MLCPlanType.ToString()));
                        Linha(sb, "MLC Id", Ler(() => feixe.MLC == null ? "(sem MLC)" : feixe.MLC.Id));
                        Linha(sb, "direção", Ler(() => feixe.GantryDirection.ToString()));
                        Linha(sb, "pontos de controle", Ler(() => feixe.ControlPoints.Count().ToString()));
                        Linha(sb, "setup technique", Ler(() => feixe.SetupTechnique.ToString()));
                        Linha(sb, "tolerância", Ler(() => feixe.ToleranceTableLabel));
                        sb.AppendLine();
                    }
                }
            }

            if (quantos == 0)
                sb.AppendLine("(nenhum — este paciente só tem campos de setup, ou nenhum campo)");

            return sb.ToString();
        }

        static void Linha(StringBuilder sb, string rotulo, string valor)
        {
            sb.AppendLine(string.Format("   {0,-20} [{1}]", rotulo, valor));
        }

        /// <summary>
        /// Um campo do inventário que estoura não pode levar o inventário
        /// inteiro junto: a razão de ele existir é justamente não se saber o
        /// que a API responde aqui.
        /// </summary>
        static string Ler(Func<string> leitura)
        {
            try
            {
                string v = leitura();
                return v == null ? "(nulo)" : v;
            }
            catch (Exception e)
            {
                return "!" + e.GetType().Name;
            }
        }

        // -------------------------------------------------------------------
        // Varredura — cria um plano temporário e o apaga
        // -------------------------------------------------------------------

        public class Tentativa
        {
            public string Energia;
            public string Fluencia;
            public int Taxa;
            public string Tecnica;
            public string Metodo;

            public override string ToString()
            {
                return string.Format("energia [{0}]  fluência [{1}]  taxa [{2}]  técnica [{3}]  {4}",
                    Energia, Fluencia == null ? "" : Fluencia, Taxa, Tecnica, Metodo);
            }
        }

        /// <summary>
        /// Experimenta as combinações num plano temporário e devolve o
        /// relatório. O plano é apagado no fim — e, se não puder ser apagado, o
        /// relatório diz o nome dele em vez de deixar a limpeza por conta da
        /// sorte.
        /// </summary>
        public static string Varrer(Bancada bancada, Pedido p)
        {
            var sb = new StringBuilder();
            var aceitas = new List<Tentativa>();
            var recusas = new Dictionary<string, int>();

            bancada.Paciente.BeginModifications();

            if (!p.Curso.CanAddPlanSetup(bancada.Conjunto))
                return "O curso não aceita um plano novo — a varredura precisa de um plano " +
                       "temporário para experimentar.";

            ExternalPlanSetup temporario = p.Curso.AddExternalPlanSetup(bancada.Conjunto);
            string idTemporario = temporario.Id;
            try
            {
                temporario.Id = "ZZ_SONDA";
                idTemporario = temporario.Id;
            }
            catch (Exception)
            {
                // O Id automático serve: o plano vai ser apagado a seguir.
            }

            int tentativas = 0;
            try
            {
                foreach (string tecnica in Tecnicas(bancada.Paciente, p))
                {
                    foreach (Equipamento energia in Energias(bancada.Paciente, p))
                    {
                        foreach (int taxa in Taxas(bancada.Paciente, p))
                        {
                            foreach (string metodo in new[] { "AddVMATBeam", "AddArcBeam", "AddStaticBeam" })
                            {
                                if (tentativas >= MAXIMO_DE_TENTATIVAS || aceitas.Count >= ACERTOS_QUE_BASTAM)
                                    goto fim;

                                tentativas++;
                                var t = new Tentativa
                                {
                                    Energia = energia.Energia,
                                    Fluencia = energia.Fluencia,
                                    Taxa = taxa,
                                    Tecnica = tecnica,
                                    Metodo = metodo
                                };

                                string erro = Experimentar(temporario, p, t);
                                if (erro == null)
                                {
                                    aceitas.Add(t);
                                }
                                else
                                {
                                    int quantas;
                                    recusas.TryGetValue(erro, out quantas);
                                    recusas[erro] = quantas + 1;
                                }
                            }
                        }
                    }
                }
            fim: ;
            }
            finally
            {
                sb.AppendLine("VARREDURA DE CONFIGURAÇÃO");
                sb.AppendLine();
                sb.AppendLine("Máquina fixa em [" + p.Maquina + "], " + tentativas + " combinações tentadas.");
                sb.AppendLine();

                if (aceitas.Count == 0)
                {
                    sb.AppendLine("NENHUMA combinação foi aceita.");
                }
                else
                {
                    sb.AppendLine("ACEITAS pelo Eclipse:");
                    foreach (Tentativa t in aceitas)
                        sb.AppendLine("   " + t);
                }

                sb.AppendLine();
                sb.AppendLine("Recusas, por mensagem:");
                foreach (var par in recusas.OrderByDescending(x => x.Value))
                    sb.AppendLine("   " + par.Value + "x  " + par.Key);

                sb.AppendLine();
                sb.AppendLine(Apagar(p, temporario, idTemporario));
            }

            return sb.ToString();
        }

        /// <summary>
        /// Devolve null se o Eclipse aceitou, ou a mensagem da recusa. Um
        /// AddBeam que falha não grava nada — é por isso que dá para varrer.
        /// </summary>
        static string Experimentar(ExternalPlanSetup plano, Pedido p, Tentativa t)
        {
            try
            {
                var mp = new ExternalBeamMachineParameters(
                    p.Maquina, t.Energia, t.Taxa, t.Tecnica,
                    string.IsNullOrWhiteSpace(t.Fluencia) ? null : t.Fluencia);

                var jaws = new VRect<double>(-50, -50, 50, 50);

                if (t.Metodo == "AddVMATBeam")
                    plano.AddVMATBeam(mp, Montagem.PesosIguais(178), 30, 181, 179,
                                      GantryDirection.Clockwise, 0, p.Isocentro);
                else if (t.Metodo == "AddArcBeam")
                    plano.AddArcBeam(mp, jaws, 30, 181, 179,
                                     GantryDirection.Clockwise, 0, p.Isocentro);
                else
                    plano.AddStaticBeam(mp, jaws, 0, 0, 0, p.Isocentro);

                return null;
            }
            catch (Exception e)
            {
                string msg = e.Message.Trim();
                if (e.InnerException != null)
                    msg += " | " + e.InnerException.Message.Trim();
                return msg;
            }
        }

        static string Apagar(Pedido p, ExternalPlanSetup temporario, string id)
        {
            try
            {
                if (!p.Curso.CanRemovePlanSetup(temporario))
                    return "ATENÇÃO: o plano temporário '" + id + "' NÃO pôde ser apagado. Apague no Eclipse.";

                p.Curso.RemovePlanSetup(temporario);
                return "Plano temporário '" + id + "' apagado.";
            }
            catch (Exception e)
            {
                return "ATENÇÃO: o plano temporário '" + id + "' não pôde ser apagado (" +
                       e.Message.Trim() + "). Apague no Eclipse.";
            }
        }

        // -------------------------------------------------------------------
        // Os candidatos
        // -------------------------------------------------------------------

        /// <summary>
        /// Técnicas a experimentar: primeiro as que EXISTEM gravadas neste
        /// paciente (Id e Name, porque não se sabe qual dos dois é o
        /// identificador), depois os nomes padrão da Varian.
        ///
        /// Experimentar um nome e ouvir a recusa não é inventar dado: nenhum
        /// deles é gravado em plano de tratamento nenhum, e o que a varredura
        /// devolve é a resposta do Eclipse, não um palpite.
        /// </summary>
        static List<string> Tecnicas(Patient paciente, Pedido p)
        {
            var lista = new List<string>();
            Juntar(lista, p.TecnicaId);

            foreach (Equipamento e in Maquinas.Conhecidos(paciente))
                Juntar(lista, e.Tecnica);

            foreach (string padrao in new[] { "ARC", "ARC DYNAMIC", "SRS ARC", "VMAT", "STATIC" })
                Juntar(lista, padrao);

            return lista;
        }

        static List<Equipamento> Energias(Patient paciente, Pedido p)
        {
            var lista = new List<Equipamento>();
            var vistos = new HashSet<string>();

            foreach (Equipamento e in Montagem.Leituras(p).Concat(Maquinas.Conhecidos(paciente)))
            {
                if (string.IsNullOrWhiteSpace(e.Energia))
                    continue;
                if (vistos.Add((e.Energia + "|" + e.Fluencia).ToUpperInvariant()))
                    lista.Add(e);
            }

            return lista;
        }

        static List<int> Taxas(Patient paciente, Pedido p)
        {
            var lista = new List<int> { p.TaxaDose };
            foreach (Equipamento e in Maquinas.Conhecidos(paciente))
                if (!lista.Contains(e.TaxaDose))
                    lista.Add(e.TaxaDose);
            foreach (int padrao in new[] { 600, 1400 })
                if (!lista.Contains(padrao))
                    lista.Add(padrao);
            return lista;
        }

        static void Juntar(List<string> lista, string valor)
        {
            if (string.IsNullOrWhiteSpace(valor))
                return;
            if (!lista.Any(x => string.Equals(x, valor, StringComparison.CurrentCultureIgnoreCase)))
                lista.Add(valor.Trim());
        }

        // -------------------------------------------------------------------
        // Saída
        // -------------------------------------------------------------------

        /// <summary>
        /// O relatório vai para ARQUIVO, não para uma MessageBox: ele é longo,
        /// e o que se faz com ele é copiar e mandar para alguém. Caixa de
        /// mensagem só se copia inteira, e às vezes nem isso.
        /// </summary>
        public static string Gravar(string texto)
        {
            var candidatos = new List<string>();
            try
            {
                candidatos.Add(Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
                    "PrePlan_diagnostico.txt"));
            }
            catch (Exception)
            {
            }
            candidatos.Add(Path.Combine(Path.GetTempPath(), "PrePlan_diagnostico.txt"));

            foreach (string caminho in candidatos)
            {
                try
                {
                    File.WriteAllText(caminho, texto, Encoding.UTF8);
                    return caminho;
                }
                catch (Exception)
                {
                }
            }

            return null;
        }
    }
}
