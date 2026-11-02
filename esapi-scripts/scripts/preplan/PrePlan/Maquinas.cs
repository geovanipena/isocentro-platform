using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

namespace VMS.TPS
{
    /// <summary>
    /// Máquina, energia, taxa de dose e Id de técnica, como o Eclipse os
    /// conhece. As quatro andam juntas porque é assim que o
    /// ExternalBeamMachineParameters as recebe — e porque a técnica de arco de
    /// um serviço pode se chamar ARC, ARC DYNAMIC ou SRS ARC, e só o que já
    /// está gravado no paciente diz qual é a daqui.
    /// </summary>
    public class Equipamento
    {
        public string Maquina;
        public string Energia;
        public string Fluencia;
        public int TaxaDose;
        public string Tecnica;
        public bool Arco;

        /// <summary>
        /// A energia como o Eclipse a MOSTRA: "6X-FFF". O
        /// ExternalBeamMachineParameters não a quer assim — ele quer "6X" e
        /// "FFF" em parâmetros separados —, mas é assim que ela aparece na
        /// tela de quem vai conferir.
        /// </summary>
        public string EnergiaVisivel()
        {
            return string.IsNullOrWhiteSpace(Fluencia) ? Energia : Energia + "-" + Fluencia;
        }

        public override string ToString()
        {
            return string.Format("{0}   {1}   {2} UM/min   {3}",
                Maquina, EnergiaVisivel(), TaxaDose,
                string.IsNullOrWhiteSpace(Tecnica) ? "?" : Tecnica);
        }

        public string Chave()
        {
            return (Maquina + "|" + Energia + "|" + Fluencia + "|" + TaxaDose + "|" + Tecnica)
                   .ToUpperInvariant();
        }
    }

    /// <summary>
    /// De onde sai a lista de máquinas da janela.
    ///
    /// A ESAPI 15.6 NÃO tem catálogo de máquinas: não há como perguntar à API
    /// quais existem no serviço. E os campos do
    /// ExternalBeamMachineParameters são strings cruas que precisam bater
    /// exatamente com a configuração ("TrueBeamSN1234" não é "TrueBeam").
    ///
    /// Então a lista não é inventada: ela é COLHIDA dos planos que o paciente
    /// já tem, mais o que já deu certo nesta estação. Na primeira vez alguém
    /// digita; da segunda em diante escolhe.
    /// </summary>
    public static class Maquinas
    {
        static string Arquivo()
        {
            string pasta = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "PrePlan");
            return Path.Combine(pasta, "maquinas.txt");
        }

        public static List<Equipamento> Conhecidos(Patient paciente)
        {
            var achados = new List<Equipamento>();
            var vistos = new HashSet<string>();

            foreach (Equipamento e in DosPlanos(paciente).Concat(DoArquivo()))
            {
                if (string.IsNullOrWhiteSpace(e.Maquina) || string.IsNullOrWhiteSpace(e.Energia))
                    continue;
                if (vistos.Add(e.Chave()))
                    achados.Add(e);
            }

            return achados
                .OrderBy(e => e.Maquina, StringComparer.CurrentCultureIgnoreCase)
                .ThenBy(e => e.Energia, StringComparer.CurrentCultureIgnoreCase)
                .ThenBy(e => e.Tecnica, StringComparer.CurrentCultureIgnoreCase)
                .ToList();
        }

        /// <summary>
        /// O que este paciente já tem gravado. É a fonte melhor das duas: veio
        /// do próprio banco clínico, não de um arquivo local que pode ter
        /// envelhecido depois de uma troca de acelerador.
        /// </summary>
        static IEnumerable<Equipamento> DosPlanos(Patient paciente)
        {
            var achados = new List<Equipamento>();
            if (paciente == null)
                return achados;

            try
            {
                foreach (Course curso in paciente.Courses)
                    foreach (ExternalPlanSetup plano in curso.PlanSetups.OfType<ExternalPlanSetup>())
                        foreach (Beam feixe in plano.Beams)
                        {
                            // Campo de setup é kV ou um MV de imagem: a energia
                            // e a técnica dele não servem para tratar e
                            // poluiriam a lista.
                            if (feixe.IsSetupField)
                                continue;

                            string tecnica = null;
                            try
                            {
                                if (feixe.Technique != null)
                                    tecnica = feixe.Technique.Id;
                            }
                            catch (Exception)
                            {
                            }

                            var eq = new Equipamento
                            {
                                Maquina = feixe.TreatmentUnit.Id,
                                TaxaDose = feixe.DoseRate,
                                Tecnica = tecnica,
                                Arco = EhArco(feixe, tecnica)
                            };
                            SepararEnergia(feixe.EnergyModeDisplayName, eq);
                            achados.Add(eq);
                        }
            }
            catch (Exception)
            {
                // A lista é conveniência, não requisito: um plano antigo que a
                // API não consegue abrir não pode derrubar o script inteiro. O
                // usuário ainda pode digitar a máquina.
            }

            return achados;
        }

        /// <summary>
        /// "6X-FFF" vira energia "6X" + modo de fluência "FFF".
        ///
        /// O <c>EnergyModeDisplayName</c> é um nome de EXIBIÇÃO e é composto:
        /// ele junta o modo de energia e o modo de fluência primária. O
        /// <c>ExternalBeamMachineParameters</c> quer os dois em parâmetros
        /// separados — passar "6X-FFF" inteiro como energia, com fluência
        /// vazia, dá <c>ApplicationException: External beam configuration not
        /// found</c>, mesmo com a máquina, a taxa e a técnica idênticas às de
        /// um plano que já existe. Pago em 03/09/2026, na primeira rodada no
        /// Eclipse, com um TrueBeamSN1001 6X-FFF.
        ///
        /// Não há como perguntar à API qual é a leitura certa (o
        /// ExternalBeamTreatmentUnit não lista energias, conferido por
        /// reflexão). Por isso esta separação é uma SUGESTÃO na tela, e a
        /// Montagem ainda tenta a leitura oposta se a primeira não criar campo
        /// nenhum.
        /// </summary>
        public static void SepararEnergia(string exibicao, Equipamento eq)
        {
            eq.Energia = exibicao == null ? "" : exibicao.Trim();
            eq.Fluencia = null;

            if (eq.Energia.Length == 0)
                return;

            int corte = eq.Energia.LastIndexOf('-');
            if (corte > 0 && corte < eq.Energia.Length - 1)
            {
                eq.Fluencia = eq.Energia.Substring(corte + 1);
                eq.Energia = eq.Energia.Substring(0, corte);
            }
        }

        /// <summary>
        /// Arco ou campo fixo. Serve para não oferecer a técnica de campo fixo
        /// a um plano de VMAT — que é justamente a recusa que só aparece na
        /// criação do primeiro campo, com o plano já criado.
        /// </summary>
        static bool EhArco(Beam feixe, string tecnica)
        {
            try
            {
                if (feixe.MLCPlanType == MLCPlanType.VMAT ||
                    feixe.MLCPlanType == MLCPlanType.ArcDynamic)
                    return true;
            }
            catch (Exception)
            {
            }

            return tecnica != null && tecnica.ToUpperInvariant().Contains("ARC");
        }

        static IEnumerable<Equipamento> DoArquivo()
        {
            var achados = new List<Equipamento>();
            try
            {
                string arq = Arquivo();
                if (!File.Exists(arq))
                    return achados;

                foreach (string linha in File.ReadAllLines(arq))
                {
                    // Linha curta é de formato antigo: 3 campos é de antes de a
                    // técnica entrar, 5 é de antes de a fluência sair da
                    // energia. As duas continuam valendo — descartar o
                    // histórico de quem já usou o script custaria justamente a
                    // digitação que ele existe para evitar.
                    string[] partes = linha.Split('|');
                    int taxa;
                    if (partes.Length < 3 || !int.TryParse(partes[2], out taxa))
                        continue;

                    var eq = new Equipamento
                    {
                        Maquina = partes[0].Trim(),
                        TaxaDose = taxa,
                        Tecnica = partes.Length > 3 ? partes[3].Trim() : null,
                        Arco = partes.Length > 4 && partes[4].Trim() == "1"
                    };

                    if (partes.Length > 5)
                    {
                        eq.Energia = partes[1].Trim();
                        eq.Fluencia = partes[5].Trim();
                        if (eq.Fluencia.Length == 0)
                            eq.Fluencia = null;
                    }
                    else
                    {
                        // Guardada antes da separação: a energia foi gravada
                        // como o Eclipse a exibe, com o "-FFF" grudado.
                        SepararEnergia(partes[1], eq);
                    }

                    achados.Add(eq);
                }
            }
            catch (Exception)
            {
                // Idem: cache ilegível é como cache inexistente.
            }
            return achados;
        }

        /// <summary>
        /// Grava o que ACABOU de funcionar — chamado depois de os campos terem
        /// sido criados, nunca antes. Guardar a tentativa faria a lista da
        /// próxima vez oferecer justamente a máquina que o Eclipse recusou.
        /// </summary>
        public static void Lembrar(Equipamento e)
        {
            try
            {
                if (DoArquivo().Any(j => j.Chave() == e.Chave()))
                    return;

                string arq = Arquivo();
                Directory.CreateDirectory(Path.GetDirectoryName(arq));
                File.AppendAllText(arq, string.Format("{0}|{1}|{2}|{3}|{4}|{5}{6}",
                    e.Maquina, e.Energia, e.TaxaDose, e.Tecnica, e.Arco ? "1" : "0", e.Fluencia,
                    Environment.NewLine));
            }
            catch (Exception)
            {
                // Não conseguir lembrar custa uma digitação na próxima vez.
                // Não vale um aviso na cara de quem acabou de montar o plano.
            }
        }
    }
}
