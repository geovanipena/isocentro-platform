////////////////////////////////////////////////////////////////////////////////
//  Constraints.cs                          Clinica-Rede · Física Médica
//------------------------------------------------------------------------------
//  Avaliação de constraints DVH a partir de um MODELO CSV escolhido pelo usuário.
//  Motor de avaliação (parseCSV / ReadObjectives / EvaluateMetrics / DvhExtensions)
//  herdado do script legado (autor original: Plinio Coelho); camada de saída
//  substituída pela região PADRÃO CLINICA (identidade visual, status, HTML).
//------------------------------------------------------------------------------
//  Tipo: single-file (SOMENTE LEITURA) — lê DVH e grava relatório HTML.
//  Suporta PlanSetup ativo ou uma única PlanSum em escopo.
//
//  CONVENÇÕES
//    · namespace VMS.TPS · public class Script · pt-BR com acentos UTF-8 reais
//    · status: OK / ATN / FAIL / CHK / NA
//    · operadores no relatório: Unicode ≤/≥ (\u2264/\u2265), nunca entidades HTML
//    · todo config em static readonly (o compilador trata warning como erro)
////////////////////////////////////////////////////////////////////////////////

using System;
using System.Linq;
using System.Text;
using System.IO;
using System.Windows;
using System.Globalization;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

namespace VMS.TPS
{
    public class Script
    {
        // ===================== CONFIG ESPECÍFICA =====================
        private static readonly string REPORT_TITLE = "Avaliação de constraints DVH";
        private static readonly string REPORT_SUB   = "Conferência de objetivos dosimétricos a partir de modelo CSV selecionado";
        private static readonly string FILE_TAG     = "Constraints";
        // Pasta inicial do diálogo de seleção do CSV (client-side no Citrix).
        private static readonly string CSV_INITIAL_DIR =
            @"\\Client\G$\4 - FÍSICA\22. Scripts Clinica\Constraints";
        // ============================================================

        // Objetivo lido do CSV (colunas do modelo). Doses internamente em Gy.
        public class StructureObjective
        {
            public string Name { get; set; }
            public string Code { get; set; }
            public string[] Aliases { get; set; }
            public string DVHObjective { get; set; }
            public string Evaluator { get; set; }
            public string Priority { get; set; }
            public string Variation { get; set; }
            public string Met { get; set; }
            public string Achieved { get; set; }
            public string FoundStructureName { get; set; }
        }
        private StructureObjective[] m_objectives;

        // Linha específica do relatório (uma por objetivo do CSV).
        private class EvalRow
        {
            public string Group, Structure, Metrica, Criterio, Alcancado, Status, Detail;
        }

        public Script() { }

        public void Execute(ScriptContext context)
        {
            if (context == null || context.Patient == null)
            { MessageBox.Show("Carregue um paciente."); return; }

            PlanningItem pitem = null;
            StructureSet ss = context.StructureSet;

            // PlanSetup ativo tem prioridade; senão, exige exatamente uma PlanSum.
            if (context.PlanSetup == null &&
                (context.PlanSumsInScope == null || context.PlanSumsInScope.Count() == 0))
            { MessageBox.Show("Carregue um plano (PlanSetup) ou uma soma de planos (PlanSum)."); return; }

            if (context.PlanSetup == null && context.PlanSumsInScope.Count() > 1)
            { MessageBox.Show("Feche todas as somas de planos, exceto uma."); return; }
            else if (context.PlanSetup == null && context.PlanSumsInScope.Count() == 1)
            {
                PlanSum plansum = context.PlanSumsInScope.Single();
                pitem = plansum;
                ss = plansum.StructureSet;
            }
            if (pitem == null) pitem = context.PlanSetup;

            if (ss == null || pitem == null)
            { MessageBox.Show("Carregue paciente, plano/soma e conjunto de estruturas."); return; }
            if (!pitem.IsDoseValid())
            { MessageBox.Show("Calcule a dose do plano antes de executar o script."); return; }

            // Seleção do modelo de constraints (CSV).
            var dlg = new Microsoft.Win32.OpenFileDialog();
            dlg.DefaultExt = "csv";
            dlg.InitialDirectory = CSV_INITIAL_DIR;
            dlg.Multiselect = false;
            dlg.Title = "Selecione o modelo de constraints (CSV)";
            dlg.Filter = "Arquivos CSV (*.csv)|*.csv";
            dlg.FilterIndex = 0;
            dlg.CheckFileExists = true;
            if (dlg.ShowDialog() == false) return; // usuário cancelou

            string file = dlg.FileName;
            if (!System.IO.File.Exists(file))
            { MessageBox.Show("O modelo selecionado não existe:\n" + file); return; }

            try
            {
                List<string[]> csv = parseCSV(file);
                if (csv.Count == 0) { MessageBox.Show("O modelo está vazio."); return; }
                csv.RemoveAt(0); // remove o cabeçalho
                ReadObjectives(csv, out m_objectives);
                if (m_objectives.Length == 0)
                { MessageBox.Show("Nenhum objetivo válido encontrado no modelo."); return; }
                EvaluateMetrics(ss, pitem);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Falha ao processar o modelo:\n" + ex.Message);
                return;
            }

            PlanSetup plan = context.PlanSetup; // pode ser null quando for PlanSum
            string html = BuildReport(context, pitem, plan);
            WriteAndOpen(context.Patient.Id, FILE_TAG, html);
        }

        // ==================================================================
        //  RELATÓRIO (esqueleto padrão + tabela específica de constraints)
        // ==================================================================
        private string BuildReport(ScriptContext ctx, PlanningItem pitem, PlanSetup plan)
        {
            var rows = new List<EvalRow>();
            foreach (var o in m_objectives) rows.Add(ToEvalRow(o));

            int nOk   = rows.Count(r => r.Status == ST_OK);
            int nAtn  = rows.Count(r => r.Status == ST_ATN);
            int nFail = rows.Count(r => r.Status == ST_FAIL);
            int nChk  = rows.Count(r => r.Status == ST_CHK);
            int nNa   = rows.Count(r => r.Status == ST_NA);

            var sb = new StringBuilder();
            sb.Append(HtmlOpen(REPORT_TITLE + " — " + ctx.Patient.Id));
            sb.Append(Header(REPORT_TITLE, REPORT_SUB));

            string extra = Cell("Item avaliado", pitem != null ? pitem.Id : "-")
                         + Cell("Tipo", (pitem is PlanSum) ? "Soma de planos" : "Plano");
            sb.Append(PatientCard(ctx.Patient, plan, extra)); // plan pode ser null (PlanSum)
            sb.Append(SummaryPills(nFail, nAtn, nChk, nOk, nNa));

            // Bloco "Ação necessária" (FALHA e ATENÇÃO, risco primeiro).
            var lines = new List<RptLine>();
            foreach (var r in rows)
                if (r.Status == ST_FAIL || r.Status == ST_ATN)
                    lines.Add(new RptLine(r.Status, r.Structure + " · " + r.Metrica,
                        "Critério " + Esc(r.Criterio) + " · Alcançado " + Esc(r.Alcancado)));
            sb.Append(ActionBlock(lines));

            // ---------------- tabela específica ----------------
            sb.Append("<table><thead><tr>");
            sb.Append("<th>Estrutura</th>");
            sb.Append("<th style='width:130px'>Métrica</th>");
            sb.Append("<th style='width:110px'>Critério</th>");
            sb.Append("<th style='width:120px'>Alcançado</th>");
            sb.Append("<th style='width:110px;text-align:center'>Status</th>");
            sb.Append("<th>Observação</th>");
            sb.Append("</tr></thead><tbody>");

            foreach (var grp in rows.Select(r => r.Group).Distinct())
            {
                sb.Append("<tr class='grp'><td colspan='6'>").Append(Esc(grp)).Append("</td></tr>");
                foreach (var r in rows.Where(x => x.Group == grp))
                {
                    sb.Append("<tr>");
                    sb.Append("<td>").Append(Esc(r.Structure)).Append("</td>");
                    sb.Append("<td>").Append(Esc(r.Metrica)).Append("</td>");
                    sb.Append("<td>").Append(Esc(r.Criterio)).Append("</td>");
                    sb.Append("<td>").Append(Esc(r.Alcancado)).Append("</td>");
                    sb.Append("<td style='text-align:center'>").Append(Badge(r.Status)).Append("</td>");
                    sb.Append("<td>").Append(Esc(r.Detail)).Append("</td>");
                    sb.Append("</tr>");
                }
            }
            sb.Append("</tbody></table>");
            // ---------------------------------------------------

            sb.Append(Footer(
                "Modelo de constraints (CSV) selecionado pelo usuário — colunas: Nome, Código, Aliases, Objetivo DVH, Avaliador, Prioridade, Variação.",
                "Doses processadas internamente em Gy (conversão automática cGy&#8596;Gy conforme o modelo). Métricas CV/DC (dose/volume coberto) ainda não são suportadas pelo motor."));
            sb.Append(HtmlClose());
            return sb.ToString();
        }

        // Converte um objetivo avaliado em linha do relatório (mapeia Met -> status).
        private EvalRow ToEvalRow(StructureObjective o)
        {
            var r = new EvalRow();
            r.Group = string.IsNullOrWhiteSpace(o.Priority) ? "Objetivos DVH" : ("Prioridade " + o.Priority.Trim());

            bool found = !string.IsNullOrEmpty(o.FoundStructureName);
            r.Structure = found ? o.FoundStructureName
                                : (!string.IsNullOrWhiteSpace(o.Name) ? o.Name : Str(o.Code));
            r.Metrica   = Str(o.DVHObjective);
            r.Criterio  = PrettyOp(o.Evaluator);
            r.Alcancado = Str(o.Achieved);

            if (!found)
            {
                r.Status = ST_NA;
                r.Detail = "Estrutura não encontrada no conjunto (verifique aliases/ID).";
                return r;
            }

            string met = (o.Met == null ? "" : o.Met.Trim());
            if (met == "Satisfatorio")      { r.Status = ST_OK;   r.Detail = ""; }
            else if (met == "Variation")    { r.Status = ST_ATN;  r.Detail = "Dentro da variação aceitável."; }
            else if (met == "Nao")          { r.Status = ST_FAIL; r.Detail = "Fora do critério."; }
            else
            {
                r.Status = ST_CHK;
                if (string.IsNullOrWhiteSpace(o.Evaluator))
                    r.Detail = "Medida informativa (sem critério no modelo).";
                else if (LooksNonNumeric(o.Achieved))
                    r.Detail = Str(o.Achieved); // ex.: "Not supported", "Unable to calculate..."
                else
                    r.Detail = "Não avaliado.";
            }
            return r;
        }

        // Renderiza o avaliador com operadores Unicode (<= -> ≤, >= -> ≥).
        private static string PrettyOp(string ev)
        {
            if (string.IsNullOrWhiteSpace(ev)) return "\u2014"; // travessão
            string s = ev.Trim();
            s = s.Replace("<=", " \u2264 ").Replace(">=", " \u2265 ");
            s = s.Replace("<", " < ").Replace(">", " > ").Replace("=", " = ");
            while (s.Contains("  ")) s = s.Replace("  ", " ");
            return s.Trim();
        }

        private static bool LooksNonNumeric(string s)
        {
            if (string.IsNullOrEmpty(s)) return true;
            return string.IsNullOrEmpty(Regex.Match(s, @"\d+\p{P}\d+|\d+").Value);
        }

        // ==================================================================
        //  MOTOR DE AVALIAÇÃO (herdado — CSV -> objetivos -> métricas -> Met)
        // ==================================================================
        private List<string[]> parseCSV(string path)
        {
            List<string[]> parsedData = new List<string[]>();
            try
            {
                var parser = new StreamReader(File.OpenRead(path));
                while (!parser.EndOfStream)
                {
                    string raw = parser.ReadLine();
                    if (string.IsNullOrWhiteSpace(raw)) continue; // ignora linhas vazias
                    parsedData.Add(raw.Split(','));
                }
                parser.Close();
            }
            catch (Exception e) { MessageBox.Show(e.Message); }
            return parsedData;
        }

        // Colunas: Nome | Código | Aliases | Objetivo DVH | Avaliador | Prioridade | Variação
        private int ReadObjectives(List<string[]> CSVsheet, out StructureObjective[] objectives)
        {
            var list = new List<StructureObjective>();
            foreach (string[] line in CSVsheet)
            {
                if (line == null || line.Length < 7) continue; // linha malformada -> ignora

                var o = new StructureObjective();
                o.Name = line[0];
                o.Code = line[1];

                // Aliases: empilha Code (ID), Name e o campo de aliases do CSV (busca por s.Id).
                var aliasList = new List<string>();
                if (!string.IsNullOrWhiteSpace(o.Code)) aliasList.Add(o.Code.Trim());
                if (!string.IsNullOrWhiteSpace(o.Name)) aliasList.Add(o.Name.Trim());
                string aliases = line[2];
                if (!string.IsNullOrWhiteSpace(aliases))
                    aliasList.AddRange(aliases.Split('|').Select(a => a.Trim()));

                o.Aliases = aliasList
                    .Where(s => !string.IsNullOrWhiteSpace(s))
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToArray();

                // Objetivo DVH / Avaliador / Variação (mantém conversão cGy -> Gy interna).
                string obj = line[3];
                string evaluator = line[4];
                string variation = line[5];

                if (obj.Contains("cGy"))
                {
                    ConvertUnitToGy(ref obj);
                    if (obj.Contains("D") || obj.Contains("M"))
                    {
                        ConvertValueToGy(ref evaluator);
                        ConvertValueToGy(ref variation);
                    }
                    else
                    {
                        ConvertValueToGy(ref obj);
                    }
                }

                o.DVHObjective = obj;
                o.Evaluator = evaluator;
                o.Variation = variation;
                o.Priority = line[6];
                o.Met = "";
                o.Achieved = "";
                list.Add(o);
            }
            objectives = list.ToArray();
            return objectives.Length;
        }

        private void ConvertUnitToGy(ref string expression)
        {
            if (string.IsNullOrEmpty(expression)) return;
            expression = expression.Replace("cGy", "Gy");
        }

        private void ConvertValueToGy(ref string expression)
        {
            var resultString = Regex.Match(expression, @"\d+\p{P}\d+|\d+").Value;
            double newValue;
            if (double.TryParse(resultString, out newValue))
            {
                newValue = newValue / 100.0;
                expression = expression.Replace(resultString, newValue.ToString());
            }
        }

        // Busca por ID/aliases: exato (OrdinalIgnoreCase) e, como fallback, acento-insensível via Norm().
        private Structure FindStructureByIdOrAliases(StructureSet ss, string[] candidateIds)
        {
            if (ss == null || candidateIds == null || candidateIds.Length == 0)
                return null;

            // 1) exato, ignorando caixa
            foreach (var cid in candidateIds)
            {
                if (string.IsNullOrWhiteSpace(cid)) continue;
                var s = ss.Structures.FirstOrDefault(x =>
                    x.Id.Equals(cid.Trim(), StringComparison.OrdinalIgnoreCase));
                if (s != null && !s.IsEmpty) return s;
            }

            // 2) fallback acento- e caixa-insensível
            foreach (var cid in candidateIds)
            {
                if (string.IsNullOrWhiteSpace(cid)) continue;
                string key = Norm(cid);
                var s = ss.Structures.FirstOrDefault(x => Norm(x.Id) == key);
                if (s != null && !s.IsEmpty) return s;
            }
            return null;
        }

        // Normaliza para casamento acento- e caixa-insensível (mantém rótulos acentuados na exibição).
        private static string Norm(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            string formD = s.Normalize(NormalizationForm.FormD);
            var sb = new StringBuilder();
            foreach (char ch in formD)
            {
                UnicodeCategory uc = CharUnicodeInfo.GetUnicodeCategory(ch);
                if (uc != UnicodeCategory.NonSpacingMark) sb.Append(ch);
            }
            return sb.ToString().Normalize(NormalizationForm.FormC).Trim().ToUpperInvariant();
        }

        private void EvaluateMetrics(StructureSet ss, PlanningItem plan)
        {
            string pattern = @"^(?<type>[^\[\]]+)(\[(?<evalunit>[^\[\]]+)\])$";
            string minmaxmean_Pattern = @"^(M(in|ax|ean)|Volume)$";
            string d_at_v_pattern = @"^D(?<evalpt>\d+\p{P}\d+|\d+)(?<unit>(%|cc))$"; // D95%, D2cc
            string dc_at_v_pattern = @"^DC(?<evalpt>\d+)(?<unit>(%|cc))$";           // DC95%, DC700cc
            string v_at_d_pattern = @"^V(?<evalpt>\d+\p{P}\d+|\d+)(?<unit>(%|Gy|cGy))$"; // V98%, V40Gy
            string cv_at_d_pattern = @"^CV(?<evalpt>\d+)(?<unit>(%|Gy|cGy))$";       // CV98%, CV40Gy

            foreach (var objective in m_objectives)
            {
                var candidateIds = objective.Aliases; // já inclui Code e Name
                Structure evalStructure = FindStructureByIdOrAliases(ss, candidateIds);
                if (evalStructure == null)
                {
                    objective.FoundStructureName = "";
                    continue;
                }
                objective.FoundStructureName = evalStructure.Id;

                var matches = Regex.Matches(objective.DVHObjective, pattern);
                if (matches.Count != 1)
                {
                    objective.Achieved = string.Format(
                        "DVH Objective expression \"{0}\" is not a recognized expression type.",
                        objective.DVHObjective);
                    continue; // não aborta os demais objetivos
                }
                Match m = matches[0];
                Group type = m.Groups["type"];
                Group evalunit = m.Groups["evalunit"];

                var testMatch = Regex.Matches(type.Value, minmaxmean_Pattern);
                if (testMatch.Count != 1)
                {
                    testMatch = Regex.Matches(type.Value, v_at_d_pattern);
                    if (testMatch.Count != 1)
                    {
                        testMatch = Regex.Matches(type.Value, d_at_v_pattern);
                        if (testMatch.Count != 1)
                        {
                            testMatch = Regex.Matches(type.Value, cv_at_d_pattern);
                            if (testMatch.Count != 1)
                            {
                                testMatch = Regex.Matches(type.Value, dc_at_v_pattern);
                                if (testMatch.Count != 1)
                                {
                                    objective.Achieved = string.Format(
                                        "DVH Objective expression \"{0}\" is not a recognized expression type.",
                                        objective.DVHObjective);
                                }
                                else
                                {
                                    objective.Achieved = "Not supported"; // Covered Dose at Volume
                                }
                            }
                            else
                            {
                                objective.Achieved = "Not supported"; // Covered Volume at Dose
                            }
                        }
                        else
                        {
                            // Dose at Volume (Dxx% / Dxxcc)
                            DVHData dvh = plan.GetDVHCumulativeData(evalStructure, DoseValuePresentation.Absolute, VolumePresentation.Relative, 0.1);
                            if ((dvh.SamplingCoverage < 0.9) || (dvh.Coverage < 0.9))
                            {
                                objective.Achieved = "Unable to calculate - insufficient dose or sampling coverage";
                                continue;
                            }
                            Group eval = testMatch[0].Groups["evalpt"];
                            Group unit = testMatch[0].Groups["unit"];
                            VolumePresentation vp = (unit.Value.CompareTo("%") == 0) ? VolumePresentation.Relative : VolumePresentation.AbsoluteCm3;
                            double volume = double.Parse(eval.Value);
                            DoseValuePresentation dvpFinal = (evalunit.Value.CompareTo("%") == 0) ? DoseValuePresentation.Relative : DoseValuePresentation.Absolute;
                            DoseValue dvAchieved = plan.GetDoseAtVolume(evalStructure, volume, vp, dvpFinal);

                            if (dvAchieved.UnitAsString.CompareTo(evalunit.Value.ToString()) != 0)
                            {
                                if ((evalunit.Value.CompareTo("Gy") == 0) && (dvAchieved.Unit.CompareTo(DoseValue.DoseUnit.cGy) == 0))
                                    dvAchieved = new DoseValue(dvAchieved.Dose / 100, DoseValue.DoseUnit.Gy);
                                else
                                    throw new ApplicationException("internal error: unidade de dose incompatível em " + objective.DVHObjective);
                            }
                            objective.Achieved = dvAchieved.ToString();
                        }
                    }
                    else
                    {
                        // Volume at Dose (Vxx% / VxxGy / VxxcGy)
                        DVHData dvh = plan.GetDVHCumulativeData(evalStructure, DoseValuePresentation.Absolute, VolumePresentation.Relative, 0.1);
                        if ((dvh.SamplingCoverage < 0.9) || (dvh.Coverage < 0.9))
                        {
                            objective.Achieved = "Unable to calculate - insufficient dose or sampling coverage";
                            continue;
                        }
                        Group eval = testMatch[0].Groups["evalpt"];
                        Group unit = testMatch[0].Groups["unit"];

                        DoseValue.DoseUnit du =
                            unit.Value == "%"  ? DoseValue.DoseUnit.Percent :
                            unit.Value == "Gy" ? DoseValue.DoseUnit.Gy :
                            DoseValue.DoseUnit.cGy;

                        DoseValue dv;
                        if (du == DoseValue.DoseUnit.Percent)
                        {
                            dv = new DoseValue(double.Parse(eval.Value), DoseValue.DoseUnit.Percent);
                        }
                        else
                        {
                            double doseVal = double.Parse(eval.Value);
                            if (du == DoseValue.DoseUnit.cGy) doseVal /= 100.0;
                            dv = new DoseValue(doseVal, DoseValue.DoseUnit.Gy);
                        }

                        VolumePresentation vpFinal = (evalunit.Value.CompareTo("%") == 0)
                            ? VolumePresentation.Relative
                            : VolumePresentation.AbsoluteCm3;

                        double volumeAchieved = DvhExtensions.GetVolumeAtDose(plan, evalStructure, dv, vpFinal);
                        objective.Achieved = string.Format("{0:0.00} {1}", volumeAchieved, evalunit.Value);
                    }
                }
                else
                {
                    // Min / Max / Mean / Volume
                    if (type.Value.CompareTo("Volume") == 0)
                    {
                        objective.Achieved = string.Format("{0:0.00} {1}", evalStructure.Volume, evalunit.Value);
                    }
                    else
                    {
                        DoseValuePresentation dvp = (evalunit.Value.CompareTo("%") == 0) ? DoseValuePresentation.Relative : DoseValuePresentation.Absolute;
                        DVHData dvh = plan.GetDVHCumulativeData(evalStructure, dvp, VolumePresentation.Relative, 0.1);
                        if (type.Value.CompareTo("Max") == 0)
                        {
                            if ((evalunit.Value.CompareTo("Gy") == 0) && (dvh.MaxDose.Unit.CompareTo(DoseValue.DoseUnit.cGy) == 0))
                                objective.Achieved = new DoseValue(dvh.MaxDose.Dose / 100, DoseValue.DoseUnit.Gy).ToString();
                            else
                                objective.Achieved = dvh.MaxDose.ToString();
                        }
                        else if (type.Value.CompareTo("Min") == 0)
                        {
                            if ((evalunit.Value.CompareTo("Gy") == 0) && (dvh.MinDose.Unit.CompareTo(DoseValue.DoseUnit.cGy) == 0))
                                objective.Achieved = new DoseValue(dvh.MinDose.Dose / 100, DoseValue.DoseUnit.Gy).ToString();
                            else
                                objective.Achieved = dvh.MinDose.ToString();
                        }
                        else
                        {
                            if ((evalunit.Value.CompareTo("Gy") == 0) && (dvh.MeanDose.Unit.CompareTo(DoseValue.DoseUnit.cGy) == 0))
                                objective.Achieved = new DoseValue(dvh.MeanDose.Dose / 100, DoseValue.DoseUnit.Gy).ToString();
                            else
                                objective.Achieved = dvh.MeanDose.ToString();
                        }
                    }
                }
            }

            // Compara o alcançado ao objetivo/variação -> Met.
            foreach (var objective in m_objectives)
            {
                string evalpattern = @"^(?<type><|<=|=|>=|>)(?<goal>\d+\p{P}\d+|\d+)$";
                if (!String.IsNullOrEmpty(objective.Evaluator))
                {
                    var matches = Regex.Matches(objective.Evaluator, evalpattern);
                    if (matches.Count != 1)
                    {
                        objective.Met = string.Format(
                            "Evaluator expression \"{0}\" is not a recognized expression type.",
                            objective.Evaluator);
                        continue;
                    }
                    Match m = matches[0];
                    Group goal = m.Groups["goal"];
                    Group evaltype = m.Groups["type"];

                    if (String.IsNullOrEmpty(Regex.Match(objective.Achieved, @"\d+\p{P}\d+|\d+").Value))
                    {
                        objective.Met = "-";
                    }
                    else
                    {
                        double evalvalue = Double.Parse(Regex.Match(objective.Achieved, @"\d+\p{P}\d+|\d+").Value);
                        if (evaltype.Value.CompareTo("<") == 0)
                        {
                            if ((evalvalue - Double.Parse(goal.ToString())) < 0) objective.Met = "Satisfatorio";
                            else if (String.IsNullOrEmpty(objective.Variation)) objective.Met = "Nao";
                            else objective.Met = ((evalvalue - Double.Parse(objective.Variation)) < 0) ? "Variation" : "Nao";
                        }
                        else if (evaltype.Value.CompareTo("<=") == 0)
                        {
                            if ((evalvalue - Double.Parse(goal.ToString())) <= 0) objective.Met = "Satisfatorio";
                            else if (String.IsNullOrEmpty(objective.Variation)) objective.Met = "Nao";
                            else objective.Met = ((evalvalue - Double.Parse(objective.Variation)) <= 0) ? "Variation" : "Nao";
                        }
                        else if (evaltype.Value.CompareTo("=") == 0)
                        {
                            if ((evalvalue - Double.Parse(goal.ToString())) == 0) objective.Met = "Satisfatorio";
                            else if (String.IsNullOrEmpty(objective.Variation)) objective.Met = "Nao";
                            else objective.Met = ((evalvalue - Double.Parse(objective.Variation)) == 0) ? "Variation" : "Nao";
                        }
                        else if (evaltype.Value.CompareTo(">=") == 0)
                        {
                            if ((evalvalue - Double.Parse(goal.ToString())) >= 0) objective.Met = "Satisfatorio";
                            else if (String.IsNullOrEmpty(objective.Variation)) objective.Met = "Nao";
                            else objective.Met = ((evalvalue - Double.Parse(objective.Variation)) >= 0) ? "Satisfatorio" : "Nao";
                        }
                        else if (evaltype.Value.CompareTo(">") == 0)
                        {
                            if ((evalvalue - Double.Parse(goal.ToString())) > 0) objective.Met = "Satisfatorio";
                            else if (String.IsNullOrEmpty(objective.Variation)) objective.Met = "Nao";
                            else objective.Met = ((evalvalue - Double.Parse(objective.Variation)) > 0) ? "Variation" : "Nao";
                        }
                    }
                }
            }
        }

        // ================================================================
        //  #region  PADRÃO CLINICA  —  bloco compartilhado (NÃO EDITAR AQUI)
        // ----------------------------------------------------------------
        //  Este bloco é IDÊNTICO em todos os scripts da biblioteca. Para
        //  atualizar a identidade visual (logo, cores, cabeçalho, rodapé),
        //  edite-o em UM script e cole a versão nova nos demais.
        //  Fornece: marca/paleta, modelo de status, atalhos de HTML
        //  (cabeçalho, cartão do paciente, pílulas de resumo, bloco "Ação
        //  necessária", rodapé) e utilitários (Esc, Fmt, Str, Safe, logo,
        //  gravar-e-abrir). Tudo static readonly (o compilador single-file
        //  trata warnings como erro; const gera ramos inalcançáveis).
        // ================================================================

        // ---- Marca / paleta (amostrada do logo Clinica) ----
        private static readonly string BRAND_CYAN    = "#00A6DB"; // ciano da marca (anel + wordmark)
        private static readonly string BRAND_CYAN_DK = "#0089B8"; // ciano escuro (títulos)
        private static readonly string BRAND_MINT    = "#11E7A2"; // verde-menta (gradiente do anel)
        private static readonly string BRAND_TEAL    = "#00708F"; // teal profundo (cartões / cabeçalho de tabela)
        private static readonly string BRAND_TEAL_DK = "#005E78"; // teal escuro (banda "Ação necessária")

        // ---- Logo: 1) tenta caminho de rede -> base64; 2) base64 embutido;
        //             3) wordmark textual (sempre funciona, sem depender de caminho). ----
        private static readonly string[] LOGO_PATHS = new string[]
        {
            @"\\Client\G$\4 - FÍSICA\22. Scripts Clinica\logo_clinica.png",
        };
        private static readonly string LOGO_BASE64 = ""; // opcional: PNG em base64 puro (sem o prefixo data:)

        // ---- Modelo de status (chaves internas; rótulos acentuados em StatusLabel) ----
        private static readonly string ST_OK   = "OK";
        private static readonly string ST_ATN  = "ATN";
        private static readonly string ST_FAIL = "FAIL";
        private static readonly string ST_CHK  = "CHK";
        private static readonly string ST_NA   = "NA";

        private static int SeverityRank(string s)
        {
            if (s == ST_FAIL) return 0;
            if (s == ST_ATN)  return 1;
            if (s == ST_CHK)  return 2;
            if (s == ST_NA)   return 3;
            return 4; // OK por último
        }
        private static string StatusLabel(string s)
        {
            if (s == ST_OK)   return "OK";
            if (s == ST_ATN)  return "ATENÇÃO";
            if (s == ST_FAIL) return "FALHA";
            if (s == ST_NA)   return "N/A";
            return "VERIFICAR"; // CHK
        }
        private static string StatusBg(string s)
        {
            if (s == ST_OK)   return "#E4F7EC";
            if (s == ST_ATN)  return "#FFF4DE";
            if (s == ST_FAIL) return "#FDE4E4";
            if (s == ST_NA)   return "#EEF1F3";
            return "#E7EFFA"; // CHK
        }
        private static string StatusFg(string s)
        {
            if (s == ST_OK)   return "#0A8F5B";
            if (s == ST_ATN)  return "#B3810C";
            if (s == ST_FAIL) return "#C0392B";
            if (s == ST_NA)   return "#77909B";
            return "#3A6EA5"; // CHK
        }

        // linha genérica para o bloco "Ação necessária"
        private class RptLine
        {
            public string Status, Title, Detail;
            public RptLine(string status, string title, string detail)
            { Status = status; Title = title; Detail = detail; }
        }

        // ---- Componentes de HTML ----
        private static string HtmlOpen(string docTitle)
        {
            var sb = new StringBuilder();
            sb.Append("<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>");
            sb.Append("<meta name='viewport' content='width=device-width, initial-scale=1'>");
            sb.Append("<title>").Append(Esc(docTitle)).Append("</title>");
            sb.Append("<style>").Append(BuildStyle()).Append("</style>");
            sb.Append("</head><body><div class='wrap'>");
            return sb.ToString();
        }
        private static string HtmlClose() { return "</div></body></html>"; }

        private static string Header(string reportTitle, string subtitle)
        {
            var sb = new StringBuilder();
            sb.Append("<div class='hdr'>").Append(BuildLogoTag());
            sb.Append("<h1 class='rep-title'>").Append(Esc(reportTitle)).Append("</h1>");
            if (!string.IsNullOrEmpty(subtitle))
                sb.Append("<div class='sub'>").Append(Esc(subtitle)).Append("</div>");
            sb.Append("</div>");
            return sb.ToString();
        }

        private static string Cell(string k, string v)   // valor de texto simples (escapado)
        { return "<div><b>" + Esc(k) + ":</b> " + Esc(v) + "</div>"; }
        private static string CellRaw(string k, string html) // valor já em HTML (confiável)
        { return "<div><b>" + Esc(k) + ":</b> " + html + "</div>"; }

        private static string PatientCard(Patient p, PlanSetup plan, string extraCellsHtml)
        {
            var sb = new StringBuilder();
            sb.Append("<div class='card'><h2>Paciente &amp; plano</h2><div class='grid'>");
            sb.Append(Cell("Nome", p != null ? p.Name : "-"));
            sb.Append(Cell("ID", p != null ? p.Id : "-"));
            string nasc = (p != null && p.DateOfBirth.HasValue) ? p.DateOfBirth.Value.ToString("dd/MM/yyyy") : "-";
            sb.Append(Cell("Nascimento", nasc));
            string course = (plan != null && plan.Course != null) ? plan.Course.Id : "-";
            sb.Append(Cell("Curso/Plano", course + " / " + (plan != null ? plan.Id : "-")));
            sb.Append(Cell("Emitido", DateTime.Now.ToString("dd/MM/yyyy HH:mm")));
            if (!string.IsNullOrEmpty(extraCellsHtml)) sb.Append(extraCellsHtml);
            sb.Append("</div></div>");
            return sb.ToString();
        }

        private static string SummaryPills(int nFail, int nAtn, int nChk, int nOk, int nNa)
        {
            var sb = new StringBuilder();
            sb.Append("<div class='pills'>");
            sb.Append(Pill("Falha", nFail, ST_FAIL));
            sb.Append(Pill("Atenção", nAtn, ST_ATN));
            sb.Append(Pill("Verificar", nChk, ST_CHK));
            if (nNa > 0) sb.Append(Pill("N/A", nNa, ST_NA));
            sb.Append(Pill("OK", nOk, ST_OK));
            sb.Append("</div>");
            return sb.ToString();
        }
        private static string Pill(string label, int n, string s)
        {
            return "<span class='pill' style='background:" + StatusBg(s) + ";color:" + StatusFg(s) + "'>"
                 + Esc(label) + ": " + n + "</span>";
        }
        private static string Badge(string s)
        {
            return "<span class='badge' style='background:" + StatusBg(s) + ";color:" + StatusFg(s) + "'>"
                 + StatusLabel(s) + "</span>";
        }

        // bloco "Ação necessária" (risco primeiro: FALHA, depois ATENÇÃO...). Detail é HTML confiável.
        private static string ActionBlock(List<RptLine> lines)
        {
            if (lines == null || lines.Count == 0) return "";
            lines.Sort(delegate (RptLine a, RptLine b) { return SeverityRank(a.Status).CompareTo(SeverityRank(b.Status)); });
            var sb = new StringBuilder();
            sb.Append("<div class='acao'>");
            sb.Append("<div class='acao-hd'>&#9888; Ação necessária (revisão orientada a risco)</div>");
            sb.Append("<table class='acao-tb'><tbody>");
            foreach (var l in lines)
            {
                sb.Append("<tr><td class='acao-st'>").Append(Badge(l.Status)).Append("</td>");
                sb.Append("<td class='acao-it'>").Append(Esc(l.Title)).Append("</td>");
                sb.Append("<td class='acao-dt'>").Append(l.Detail).Append("</td></tr>");
            }
            sb.Append("</tbody></table></div>");
            return sb.ToString();
        }

        // rodapé padrão. sourcesHtml/notesHtml são HTML confiável (podem ser "" ).
        private static string Footer(string sourcesHtml, string notesHtml)
        {
            var sb = new StringBuilder();
            sb.Append("<div class='foot'>");
            if (!string.IsNullOrEmpty(sourcesHtml)) sb.Append("<b>Fontes:</b> ").Append(sourcesHtml).Append("<br>");
            sb.Append("<b>Legenda:</b> OK = dentro do objetivo &middot; ATENÇÃO = desvio aceitável / revisar &middot; ");
            sb.Append("FALHA = fora da tolerância &middot; VERIFICAR = conferência manual &middot; N/A = ausente / não avaliado.<br>");
            if (!string.IsNullOrEmpty(notesHtml)) sb.Append(notesHtml).Append("<br>");
            sb.Append("Relatório auxiliar gerado por plug-in ESAPI (somente leitura) &mdash; não substitui o julgamento do físico/médico responsável. ");
            sb.Append("Clinica-Rede &middot; Física Médica.");
            sb.Append("</div>");
            return sb.ToString();
        }

        // folha de estilo — PADRÃO CLINICA v3: design system em :root (v2) +
        // camada de legibilidade (skills web-design / ui-ux-pro-max):
        //   · linhas de tabela ~40px + line-height 1.5 (tabela densa TG-275)
        //   · hover de linha para rastreio; cabeçalhos de coluna em caixa-alta
        //   · espaçamentos alinhados à grade 8px; rodapé com contraste WCAG AA
        // Marca Clinica inalterada (teal/ciano/menta). String idêntica em toda a
        // biblioteca; para reajustar a identidade, edite só o :root.
        private static string BuildStyle()
        {
            return
              // ---------- design tokens (única fonte de cor) ----------
              ":root{" +
                "--brand-cyan:"    + BRAND_CYAN    + ";" +
                "--brand-cyan-dk:" + BRAND_CYAN_DK + ";" +
                "--brand-mint:"    + BRAND_MINT    + ";" +
                "--brand-teal:"    + BRAND_TEAL    + ";" +
                "--brand-teal-dk:" + BRAND_TEAL_DK + ";" +
                "--bg:#F4F8FA;--surface:#FFFFFF;--text:#243B46;--text-sub:#5A7480;" +
                "--text-muted:#5F7480;--text-inverse:#FFFFFF;--text-strong:#333344;" +
                "--border:#E2EDF1;--border-soft:#EEF3F5;--border-foot:#DDE8EC;" +
                "--label:#33525F;--grp-bg:#EAF6FA;--acao-border:#CFE7EE;--row-hover:#F1F8FB;" +
                "--shadow-card:0 1px 3px rgba(0,60,80,.06);" +
              "}" +
              // ---------- base ----------
              "body{font-family:'Segoe UI',Arial,sans-serif;color:var(--text);margin:0;background:var(--bg);line-height:1.5;-webkit-font-smoothing:antialiased;}" +
              ".wrap{max-width:1120px;margin:0 auto;padding:24px;}" +
              // ---------- cabeçalho / marca ----------
              ".hdr{border-bottom:3px solid var(--brand-cyan);padding-bottom:16px;margin-bottom:20px;}" +
              ".logo{height:46px;display:block;margin-bottom:8px;}" +
              ".brand{font-size:24px;font-weight:700;letter-spacing:.5px;}" +
              ".brand .c{color:var(--brand-cyan);}.brand .m{color:var(--brand-mint);}" +
              ".rep-title{font-size:20px;color:var(--brand-cyan-dk);margin:8px 0 2px;font-weight:700;line-height:1.25;}" +
              ".sub{color:var(--text-sub);font-size:13px;margin-top:2px;line-height:1.4;}" +
              // ---------- cartão do paciente ----------
              ".card{background:var(--surface);border:1px solid var(--border);border-left:5px solid var(--brand-teal);border-radius:10px;padding:16px 20px;margin-bottom:20px;}" +
              ".card h2{margin:0 0 10px;font-size:15px;color:var(--brand-teal);}" +
              ".grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px 24px;font-size:13px;}" +
              ".grid b{color:var(--label);}" +
              // ---------- pílulas de resumo ----------
              ".pills{margin-bottom:20px;}" +
              ".pill{display:inline-block;border-radius:20px;padding:6px 14px;font-size:13px;font-weight:600;margin-right:8px;}" +
              // ---------- tabela (densa, legível) ----------
              "table{border-collapse:collapse;width:100%;background:var(--surface);border-radius:10px;overflow:hidden;box-shadow:var(--shadow-card);margin-bottom:12px;}" +
              "thead th,th{background:var(--brand-teal);color:var(--text-inverse);font-size:11px;text-transform:uppercase;letter-spacing:.06em;text-align:left;padding:11px 14px;font-weight:600;}" +
              "td{padding:11px 14px;font-size:13px;line-height:1.5;border-top:1px solid var(--border-soft);vertical-align:top;}" +
              "tbody tr:not(.grp):hover td{background:var(--row-hover);}" +
              ".grp td{background:var(--grp-bg);font-weight:700;color:var(--brand-teal);border-left:4px solid var(--brand-cyan);padding:10px 14px;}" +
              ".badge{display:inline-block;border-radius:14px;padding:3px 10px;font-size:11px;font-weight:700;letter-spacing:.03em;white-space:nowrap;}" +
              // ---------- bloco "Ação necessária" ----------
              ".acao{background:var(--surface);border:1px solid var(--acao-border);border-radius:10px;overflow:hidden;margin-bottom:20px;}" +
              ".acao-hd{background:var(--brand-teal-dk);color:var(--text-inverse);font-weight:700;padding:10px 14px;font-size:14px;}" +
              ".acao-tb{box-shadow:none;border-radius:0;margin:0;}" +
              ".acao-st{width:110px;text-align:center;white-space:nowrap;}" +
              ".acao-it{font-weight:700;width:34%;}" +
              ".acao-dt{color:var(--text-strong);}" +
              // ---------- rodapé ----------
              ".foot{color:var(--text-muted);font-size:11px;margin-top:24px;line-height:1.6;border-top:1px solid var(--border-foot);padding-top:14px;}";
        }

        // ---- Utilitários ----
        private static string Esc(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;");
        }
        private static string Str(string s) { return string.IsNullOrEmpty(s) ? "-" : s; }
        private static string Safe(string s)
        {
            if (string.IsNullOrEmpty(s)) return "arquivo";
            foreach (char c in System.IO.Path.GetInvalidFileNameChars()) s = s.Replace(c, '_');
            return s;
        }
        private static string Fmt(double v)
        {
            if (double.IsNaN(v)) return "-";
            return v.ToString("0.##", CultureInfo.InvariantCulture);
        }

        private static string BuildLogoTag()
        {
            if (LOGO_PATHS != null)
                foreach (string p in LOGO_PATHS)
                {
                    try
                    {
                        if (!string.IsNullOrEmpty(p) && System.IO.File.Exists(p))
                        {
                            byte[] bytes = System.IO.File.ReadAllBytes(p);
                            string ext = System.IO.Path.GetExtension(p).TrimStart('.').ToLowerInvariant();
                            if (ext == "jpg") ext = "jpeg";
                            if (string.IsNullOrEmpty(ext)) ext = "png";
                            return "<img class='logo' src='data:image/" + ext + ";base64," +
                                   Convert.ToBase64String(bytes) + "' alt='Clinica'>";
                        }
                    }
                    catch { /* tenta o próximo candidato */ }
                }
            if (!string.IsNullOrEmpty(LOGO_BASE64))
                return "<img class='logo' src='data:image/png;base64," + LOGO_BASE64 + "' alt='Clinica'>";
            return "<div class='brand'><span class='c'>Clinica</span> <span class='m'>Rede</span></div>";
        }

        // Navegadores conhecidos, em ordem de preferência — abrir o .exe direto
        // evita depender da associação de arquivo .html do Windows/Citrix, que
        // varia entre sessões publicadas e às vezes cai em "Abrir com" / salvar
        // como .txt em vez de abrir no navegador.
        private static readonly string[] NAVEGADORES_CONHECIDOS = new string[]
        {
            @"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
            @"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
            @"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            @"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            @"%ProgramFiles%\Mozilla Firefox\firefox.exe",
            @"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe",
            @"%ProgramFiles%\Internet Explorer\iexplore.exe",
            @"%ProgramFiles(x86)%\Internet Explorer\iexplore.exe",
        };

        // grava o HTML no temp (UTF-8 com BOM) e abre num navegador conhecido do
        // cliente (Citrix) — nunca via associação de arquivo do SO (instável).
        private static void WriteAndOpen(string patientId, string tag, string html)
        {
            string fname = Safe(patientId) + "_" + Safe(tag) + "_" +
                           DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".html";
            string path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), fname);
            System.IO.File.WriteAllText(path, html, new UTF8Encoding(true));
            AbrirNoNavegador(path);
            System.Threading.Thread.Sleep(1200);
        }

        // tenta cada navegador conhecido primeiro; só recai na associação do SO
        // (ShellExecute) se nenhum executável for encontrado no cliente.
        private static void AbrirNoNavegador(string path)
        {
            foreach (string candidato in NAVEGADORES_CONHECIDOS)
            {
                string exe = Environment.ExpandEnvironmentVariables(candidato);
                try
                {
                    if (System.IO.File.Exists(exe))
                    {
                        System.Diagnostics.Process.Start(exe, "\"" + path + "\"");
                        return;
                    }
                }
                catch { /* tenta o próximo candidato */ }
            }
            System.Diagnostics.Process.Start(path); // nenhum navegador conhecido -> associação do SO
        }
        //  #endregion  PADRÃO CLINICA
        // ================================================================
    }

    // ==================================================================
    //  Extensões DVH (herdadas) — suporte a PlanSetup e PlanSum
    // ==================================================================
    public static class DvhExtensions
    {
        public static DoseValue GetDoseAtVolume(this PlanningItem pitem, Structure structure, double volume, VolumePresentation volumePresentation, DoseValuePresentation requestedDosePresentation)
        {
            if (pitem is PlanSetup)
            {
                return ((PlanSetup)pitem).GetDoseAtVolume(structure, volume, volumePresentation, requestedDosePresentation);
            }
            else
            {
                if (requestedDosePresentation != DoseValuePresentation.Absolute)
                    throw new ApplicationException("Only absolute dose supported for Plan Sums");
                DVHData dvh = pitem.GetDVHCumulativeData(structure, DoseValuePresentation.Absolute, volumePresentation, 0.001);
                return DvhExtensions.DoseAtVolume(dvh, volume);
            }
        }
        public static double GetVolumeAtDose(this PlanningItem pitem, Structure structure, DoseValue dose, VolumePresentation requestedVolumePresentation)
        {
            if (pitem is PlanSetup)
            {
                try
                {
                    return ((PlanSetup)pitem).GetVolumeAtDose(structure, dose, requestedVolumePresentation);
                }
                catch
                {
                    if (dose.Unit.CompareTo(DoseValue.DoseUnit.cGy) == 0)
                        return ((PlanSetup)pitem).GetVolumeAtDose(structure, new DoseValue(dose.Dose / 100, DoseValue.DoseUnit.Gy), requestedVolumePresentation);
                    else if (dose.Unit.CompareTo(DoseValue.DoseUnit.Gy) == 0)
                        return ((PlanSetup)pitem).GetVolumeAtDose(structure, new DoseValue(dose.Dose * 100, DoseValue.DoseUnit.cGy), requestedVolumePresentation);
                    else
                        return ((PlanSetup)pitem).GetVolumeAtDose(structure, dose, requestedVolumePresentation);
                }
            }
            else
            {
                DVHData dvh = pitem.GetDVHCumulativeData(structure, DoseValuePresentation.Absolute, requestedVolumePresentation, 0.001);
                try
                {
                    ((PlanSum)pitem).PlanSetups.First().GetVolumeAtDose(structure, dose, requestedVolumePresentation);
                    return DvhExtensions.VolumeAtDose(dvh, dose.Dose);
                }
                catch
                {
                    if (dose.Unit.CompareTo(DoseValue.DoseUnit.cGy) == 0)
                        return DvhExtensions.VolumeAtDose(dvh, dose.Dose / 100);
                    else if (dose.Unit.CompareTo(DoseValue.DoseUnit.Gy) == 0)
                        return DvhExtensions.VolumeAtDose(dvh, dose.Dose * 100);
                    else
                        return DvhExtensions.VolumeAtDose(dvh, dose.Dose);
                }
            }
        }

        public static DoseValue DoseAtVolume(DVHData dvhData, double volume)
        {
            if (dvhData == null || dvhData.CurveData.Count() == 0)
                return DoseValue.UndefinedDose();
            double absVolume = dvhData.CurveData[0].VolumeUnit == "%" ? volume * dvhData.Volume * 0.01 : volume;
            if (volume < 0.0 || absVolume > dvhData.Volume)
                return DoseValue.UndefinedDose();

            DVHPoint[] hist = dvhData.CurveData;
            for (int i = 0; i < hist.Length; i++)
            {
                if (hist[i].Volume < volume)
                    return hist[i].DoseValue;
            }
            return dvhData.MaxDose;
        }

        public static double VolumeAtDose(DVHData dvhData, double dose)
        {
            if (dvhData == null)
                return Double.NaN;

            DVHPoint[] hist = dvhData.CurveData;
            int index = (int)(hist.Length * dose / dvhData.MaxDose.Dose);
            if (index < 0 || index >= hist.Length)
                return 0.0;
            else
                return hist[index].Volume;
        }
        public static bool IsDoseValid(this PlanningItem pitem)
        {
            if (pitem is PlanSetup)
            {
                return ((PlanSetup)pitem).IsDoseValid;
            }
            else if (pitem is PlanSum)
            {
                PlanSum psum = (PlanSum)pitem;
                var plans = (from p in psum.PlanSetups where p.IsDoseValid == false select p);
                return plans.Count() <= 0;
            }
            else
            {
                throw new ApplicationException("Unknown PlanningItem type " + pitem.ToString());
            }
        }
    }
}
