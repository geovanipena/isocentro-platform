////////////////////////////////////////////////////////////////////////////////
//  Constraints_Clinica_2026.cs             Clinica-Rede · Física Médica
//------------------------------------------------------------------------------
//  Tipo........: Plug-in ESAPI single-file, SOMENTE LEITURA (Eclipse 15.6+)
//  Padrão......: Biblioteca Clinica (região "PADRÃO CLINICA" compartilhada)
//  Autor.......: Geovani / Física Médica
//------------------------------------------------------------------------------
//  OBJETIVO
//    Avalia o plano ativo (PlanSetup) OU uma soma de planos (PlanSum, ex.: plano
//    primário + boost) contra os constraints de QUATRO publicações de referência,
//    e gera um relatório HTML (aberto automaticamente):
//      (1) ASTRO Consensus 2025 — Puckett LL et al., "Dose-Volume Histogram
//          Compendium of Dose Constraints", Pract Radiat Oncol 2025.
//      (2) Timmerman 8-2021 — Timmerman R, "A Story of Hypofractionation and
//          the Table on the Wall", Int J Radiat Oncol Biol Phys 2022;112(1):4-21.
//      (3) Consenso Brasileiro de Mama (hipofracionamento) — Tabela 2 (8 trials).
//      (4) CORSAIR (2022) — resumo prático "all-in-one" (agrega QUANTEC/HyTEC/
//          ESTRO/protocolos); aqui a coluna CONVENCIONAL, por região anatômica.
//
//  FLUXO
//    0) se houver PlanSetup ativo E soma(s) de planos no escopo, escolher qual
//       avaliar (senão o único candidato disponível é usado direto).
//    0b) soma (PlanSum): AVALIAÇÃO CONJUNTA — a soma inteira é um alvo só. Uma
//       única janela confirma/ajusta a Prescrição do conjunto (Σ física ou EQD2). Sem
//       rótulos de grupo, sem loop.
//    1) escolher a PUBLICAÇÃO -> ASTRO: sítio+tabela / Timmerman: nº de frações /
//       Consenso de Mama: trial (sítio único, sem janela de sítio).
//    2) avaliar o DVH da tabela escolhida (soma completa nas métricas em Gy/cc).
//
//  SOMA DE PLANOS (PlanSum) — AVALIAÇÃO CONJUNTA
//    PlanSum não tem TotalDose/NumberOfFractions próprios (só PlanSetup tem). Os
//    componentes (ex.: mama + FSC-linfonodos, ou mama + boost) são tratados
//    JUNTOS no mesmo curso e avaliados EM CONJUNTO: uma única tabela contra o
//    DVH da soma COMPLETA. O que interessa clinicamente é a dose COMBINADA nos
//    OARs (coração, pulmão), que já vem correta do DVH somado — sem precisar
//    separar por grupo nem somar prescrições manualmente.
//
//    Prescrição do conjunto (usada SÓ nas métricas em %, cobertura de alvo):
//    - PARALELO, mesma dose (ex.: mama + FSC, TotalDose igual e mesmo fracionamento):
//      cada volume recebe a MESMA dose e NÃO somam — a prescrição é essa dose COMUM
//      (nenhum volume recebe a soma). Usada direto, SEM janela.
//    - BOOST sequencial (mesmo volume, doses diferentes): a dose do alvo é a soma —
//      Σ TotalDose × peso (mesmo fracionamento) ou Σ EQD2 (difere; α/β=10 padrão,
//      ajustável; ICRU 83). Sugerida numa janela editável para o físico confirmar.
//    É aproximação escalar sobre TotalDose — o script NÃO reconverte o grid voxel a
//    voxel; se a soma mistura fracionamentos, o relatório avisa que as métricas em
//    Gy/cc vêm do DVH físico somado, SEM correção EQD2/BED, e devem ser lidas com cautela.
//
//    O PTV genérico só é resolvido automaticamente se houver exatamente um
//    PTV no StructureSet da soma.
//
//  COBERTURA (v1.0)
//    ASTRO: Próstata, Pulmão, Fígado. Timmerman: 1,2,3,4,5,8 fx. Demais sítios
//    e regimes ficam como pontos de extensão (a estrutura de dados facilita).
//
//  >>> AVISO CLÍNICO <<<  Valores TRANSCRITOS das tabelas publicadas. VALIDE
//      cada constraint contra o artigo original antes do uso clínico. Métricas
//      volumétricas dependem de contorno correto (ex.: Lungs-GTV, Liver-GTV).
//
//  ENCODING: salvar em UTF-8. static readonly (não const) — o compilador
//  single-file trata warnings como erro.
////////////////////////////////////////////////////////////////////////////////

using System;
using System.Linq;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Globalization;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

namespace VMS.TPS
{
    public class Script
    {
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

        // ------------------------------------------------------------------
        //  ALIASES COMPARTILHADOS  —  fonte única (evita divergência entre
        //  BuildTimmerman/BuildAstro). Órgãos cujo literal é idêntico nos dois.
        //  Editar aqui atualiza todas as tabelas simultaneamente.
        // ------------------------------------------------------------------
        private static readonly string ALS_ESOFAGO = "Esophagus|Esôfago";
        private static readonly string ALS_HEART = "Heart|Coração";
        private static readonly string ALS_COSTELAS = "Ribs|Costelas|Rib_L|Rib_R";
        private static readonly string ALS_PELE = "Skin|Pele";
        private static readonly string ALS_ESTOMAGO = "Stomach|Estômago";
        private static readonly string ALS_DUODENO = "Duodenum|Duodeno";
        private static readonly string ALS_FEMUR_D = "Femur_D|FemurD|Femur D|Femur_Head_R|FemurHead_R|Femoral_Head_R|Cabeca_Femoral_D|Cabeça_Femoral_D";
        private static readonly string ALS_FEMUR_E = "Femur_E|FemurE|Femur E|Femur_Head_L|FemurHead_L|Femoral_Head_L|Cabeca_Femoral_E|Cabeça_Femoral_E";

        // ------------------------------------------------------------------
        //  MODELO DE DADOS
        // ------------------------------------------------------------------
        // Direcao do objetivo:
        //   MAX  -> valor atingido deve ser <= meta (OAR / dose maxima)
        //   MIN  -> valor atingido deve ser >= meta (cobertura de alvo / volume frio)
        private enum Dir { MAX, MIN }

        private class Constraint
        {
            public string Structure;       // ID canonico no Eclipse
            public string[] Aliases;       // IDs alternativos aceitos
            public string Metric;          // "Mean", "D0.035cc", "D95%", "V20Gy", "V100%", "CV19Gy"...
            public Dir Direction;
            public double Primary;          // meta primaria
            public double? Secondary;       // meta secundaria (variação aceitável); null se não houver
            public string Unit;             // unidade de COMPARACAO: "Gy", "%", "cc"
            public string Notes;
        }

        private class ConstraintTable
        {
            public string Publication;
            public string Site;             // ASTRO: sítio; Timmerman: "SBRT/SABR"
            public string Title;            // titulo curto exibido
            public string Regimen;          // descricao dose/fracionamento
            public int[] MatchFx;           // frações que "casam" (pré-seleção); null = qualquer
            public List<Constraint> Rows = new List<Constraint>();

            public Constraint Add(string st, string metric, Dir d, double primary,
                                  double? secondary, string unit, string notes = null, string aliases = null)
            {
                var c = new Constraint
                {
                    Structure = st,
                    Aliases = string.IsNullOrEmpty(aliases)
                                ? new string[0]
                                : aliases.Split('|').Select(a => a.Trim()).ToArray(),
                    Metric = metric,
                    Direction = d,
                    Primary = primary,
                    Secondary = secondary,
                    Unit = unit,
                    Notes = notes ?? ""
                };
                Rows.Add(c);
                return c;
            }
        }

        // resultado de uma linha avaliada
        private class Result
        {
            public Constraint C;
            public string FoundStructure;   // ID realmente usado (ou "" se não achou)
            public double Achieved;         // valor calculado na unidade de comparacao
            public string AchievedText;     // texto formatado (com unidade)
            public string Status;           // OK / ATN(variação) / FAIL / NA / CHK
        }

        // Um GRUPO DE ALVO dentro de uma soma de planos: um ou mais componentes que somam
        // SEQUENCIALMENTE para o MESMO alvo (ex.: mama+boost). Planos de alvo/região DIFERENTE
        // (ex.: linfonodos/FSC) NUNCA entram no mesmo grupo — cada alvo tem sua própria Prescrição,
        // que não é a soma entre eles (mama e FSC não compartilham "uma dose total").
        private class RxGroup
        {
            public List<PlanSetup> Members;
            public string Label;      // rótulo (IDs dos componentes unidos por "+")
            public double RxGy;       // Prescrição do grupo (Gy) — soma física ou EQD2, conforme UsedEqd2
            public int Fx;            // nº de frações do grupo (soma dos componentes, informativo)
            public bool UsedEqd2;     // true se a Prescrição veio de EQD2 (componentes do grupo com dose/fração diferente)
            public double AlphaBeta;  // alfa/beta assumido na conversão EQD2 (só relevante se UsedEqd2)
        }

        // ------------------------------------------------------------------
        //  RADIOBIOLOGIA — LQ / EQD2 (ICRU 83)
        //  Necessário porque somar Gy físico só é biologicamente válido quando
        //  os planos somados têm a MESMA dose por fração; senão, some em EQD2.
        // ------------------------------------------------------------------
        private static double DoseFxGy(PlanSetup p)
        {
            int n = p.NumberOfFractions ?? 0;
            double g = ToGy(p.TotalDose);
            return (n > 0 && !double.IsNaN(g)) ? g / n : double.NaN;
        }

        // true se as doses/fração dos planos informados são compatíveis (diferença
        // relativa <= tolRel); soma física direta só é válida nesse caso. Fracionamento
        // desconhecido de QUALQUER plano (NumberOfFractions ilegível) NUNCA é tratado como
        // compatível — não dá para afirmar igualdade sem o dado.
        private static bool FracionamentoCompativel(IEnumerable<PlanSetup> plans, double tolRel)
        {
            var vals = plans.Select(DoseFxGy).ToList();
            if (vals.Any(v => double.IsNaN(v))) return false;
            if (vals.Count <= 1) return true;
            double mn = vals.Min(), mx = vals.Max(), avg = vals.Average();
            if (avg <= 0) return true;
            return (mx - mn) / avg <= tolRel;
        }

        // EQD2 (dose equivalente em frações de 2 Gy) de uma dose total física, modelo
        // linear-quadrático: EQD2 = D x (d + alfa/beta) / (2 + alfa/beta), d = dose/fração.
        // Aproximação escalar sobre o TotalDose do componente — NÃO substitui conversão
        // voxel a voxel do grid de dose (fora do escopo deste script single-file).
        private static double Eqd2Gy(double totalGy, int nFrac, double alphaBeta)
        {
            if (nFrac <= 0 || double.IsNaN(totalGy)) return double.NaN;
            double d = totalGy / nFrac;
            return totalGy * (d + alphaBeta) / (2.0 + alphaBeta);
        }

        // ==================================================================
        //  EXECUCAO
        // ==================================================================
        public void Execute(ScriptContext context)
        {
            // ---- validacao de contexto ----
            if (context.Patient == null) { MessageBox.Show("Carregue um paciente."); return; }

            // ---- resolve o item a avaliar: PlanSetup ativo e/ou PlanSum(s) no escopo ----
            var candidates = new List<PlanningItem>();
            var candLabels = new List<string>();
            if (context.PlanSetup != null)
            {
                candidates.Add(context.PlanSetup);
                candLabels.Add("Plano: " + context.PlanSetup.Id +
                    (context.PlanSetup.Course != null ? "  (curso " + context.PlanSetup.Course.Id + ")" : ""));
            }
            if (context.PlanSumsInScope != null)
                foreach (var sum in context.PlanSumsInScope)
                {
                    candidates.Add(sum);
                    int nComp = sum.PlanSetups != null ? sum.PlanSetups.Count() : 0;
                    candLabels.Add("Soma de planos: " + sum.Id + "  [" + nComp + " componente(s)]");
                }
            if (candidates.Count == 0)
            {
                MessageBox.Show("Carregue um PLANO (PlanSetup) ativo ou abra uma SOMA DE PLANOS (Plan Sum) no escopo.");
                return;
            }

            PlanningItem item;
            if (candidates.Count == 1) item = candidates[0];
            else
            {
                int pick = PickFromList("Constraints Clinica 2026",
                        "Passo 0 - Escolha o plano ou a soma de planos a avaliar:", candLabels, 0);
                if (pick < 0) return;
                item = candidates[pick];
            }

            bool isSum = item is PlanSum;
            PlanSetup planSingle = isSum ? null : (PlanSetup)item;
            PlanSum planSum = isSum ? (PlanSum)item : null;

            if (!isSum && !planSingle.IsDoseValid)
            {
                MessageBox.Show("Calcule a dose do plano antes de rodar o script.");
                return;
            }
            // PlanSum não tem IsDoseValid (só PlanSetup) — usa Dose == null como equivalente disponível.
            if (isSum && planSum.Dose == null)
            {
                MessageBox.Show("A soma de planos não possui dose calculada.");
                return;
            }
            StructureSet ss = item.StructureSet;
            if (ss == null) { MessageBox.Show("O plano/soma não possui StructureSet associado."); return; }

            double rxGy = double.NaN;   // Prescrição do plano único (!isSum); p/ soma, cada grupo tem a sua (rxGroups)
            int planFx = 0;
            List<RxGroup> rxGroups = null;   // grupos de alvo da soma (null se não-soma)
            bool allFracOk = true;    // TODOS os componentes da soma (não só os de um grupo) têm o mesmo dose/fração
            if (!isSum)
            {
                planFx = planSingle.NumberOfFractions ?? 0;
                rxGy = ToGy(planSingle.TotalDose);
                if (double.IsNaN(rxGy) || rxGy <= 0)
                {
                    MessageBox.Show("Não foi possível ler a dose de prescrição (TotalDose) do plano.");
                    return;
                }
            }
            else
            {
                // AVALIAÇÃO CONJUNTA: a soma inteira é tratada como UM alvo só. Mama+FSC ou
                // mama+boost são tratados juntos e avaliados em conjunto — sem rótulos de grupo
                // nem loop. As métricas em Gy/cc (OARs inclusive) usam SEMPRE o DVH da soma
                // completa; a Prescrição abaixo serve às métricas em % (cobertura). Prescrição = Σ física (mesmo
                // fracionamento) ou Σ EQD2 (fracionamentos diferentes; ICRU 83), sempre editável.
                var comps = planSum.PlanSetups.ToList();
                allFracOk = FracionamentoCompativel(comps, 0.08);
                rxGroups = new List<RxGroup>();

                if (comps.Count == 1)
                {
                    var only = comps[0];
                    double onlyGy = ToGy(only.TotalDose);
                    if (double.IsNaN(onlyGy) || onlyGy <= 0)
                    {
                        MessageBox.Show("Não foi possível ler a dose de prescrição (TotalDose) do plano \"" + only.Id + "\".");
                        return;
                    }
                    rxGroups.Add(new RxGroup
                    {
                        Members = comps, Label = only.Id,
                        RxGy = onlyGy, Fx = only.NumberOfFractions ?? 0,
                        UsedEqd2 = false, AlphaBeta = 10.0
                    });
                }
                else
                {
                    // Alvos em PARALELO com a MESMA prescrição (ex.: mama + FSC) NÃO somam: são
                    // volumes distintos, cada um recebe a mesma dose — a prescrição do conjunto é
                    // essa dose COMUM (nenhum volume recebe a soma). Detecta pelo TotalDose igual.
                    // Só o boost SEQUENCIAL (mesmo volume, doses diferentes) soma.
                    var doses = comps.Select(c => ToGy(c.TotalDose)).ToList();
                    bool doseConhecida = doses.All(d => !double.IsNaN(d) && d > 0);
                    // "paralelo, mesma dose" (mama+FSC) só vale p/ componentes ADITIVOS de peso ~1;
                    // subtração ou pesos != 1 caem no ramo de soma (que trata sinal e peso).
                    bool soAditivoUnit = comps.All(c =>
                        planSum.GetPlanSumOperation(c) != PlanSumOperation.Subtraction &&
                        Math.Abs(planSum.GetPlanWeight(c) - 1.0) < 1e-3);
                    bool mesmaDose = doseConhecida && soAditivoUnit &&
                                     (doses.Max() - doses.Min()) / doses.Average() <= 0.10;

                    if (mesmaDose && allFracOk)
                    {
                        // mama + FSC (mesma dose/fracionamento): usa a dose comum, sem perguntar.
                        rxGroups.Add(new RxGroup
                        {
                            Members = comps, Label = "Soma",
                            RxGy = doses.Max(),
                            Fx = comps.Select(c => c.NumberOfFractions ?? 0).Max(),
                            UsedEqd2 = false, AlphaBeta = 10.0
                        });
                    }
                    else
                    {
                        // Doses diferentes -> boost sequencial (mesmo volume): a dose do alvo é a
                        // soma. Física se mesmo fracionamento; senão EQD2 (pede α/β). Confirma numa janela.
                        double alphaBeta = 10.0; bool usouEqd2 = false;
                        if (!allFracOk)
                        {
                            double? ab = AskDoseGy("α/β para EQD2 (soma conjunta)",
                                "Os planos da soma têm fracionamento diferente — a Prescrição do conjunto será por EQD2.\n" +
                                "Informe o α/β do alvo/tecido (padrão 10 para tumor/efeito agudo; ~3 para tecido tardio):",
                                10.0);
                            if (ab == null) return;   // cancelado
                            alphaBeta = ab.Value; usouEqd2 = true;
                        }

                        double sugGy = 0; int sugFx = 0;
                        bool algumDesconhecido = false;
                        foreach (var comp in comps)
                        {
                            PlanSumOperation op = planSum.GetPlanSumOperation(comp);
                            double w = planSum.GetPlanWeight(comp);
                            double sign = (op == PlanSumOperation.Subtraction) ? -1.0 : 1.0;
                            double compGy = !usouEqd2
                                ? ToGy(comp.TotalDose)
                                : Eqd2Gy(ToGy(comp.TotalDose), comp.NumberOfFractions ?? 0, alphaBeta);
                            if (double.IsNaN(compGy)) algumDesconhecido = true;
                            else sugGy += sign * w * compGy;
                            if (op != PlanSumOperation.Subtraction) sugFx += comp.NumberOfFractions ?? 0;
                        }
                        if (sugGy < 0) sugGy = 0;
                        if (algumDesconhecido)
                            MessageBox.Show("Não foi possível calcular a dose de ao menos um plano da soma " +
                                "(TotalDose ou nº de frações ilegível). A sugestão abaixo está incompleta — confira manualmente.");

                        string metodo = usouEqd2
                            ? "Σ EQD2(TotalDose) × peso, α/β=" + Fmt(alphaBeta) + " (doses/fracionamentos diferentes — boost sequencial; ICRU 83)."
                            : "Σ TotalDose × peso (doses diferentes, mesmo fracionamento — boost sequencial).";

                        double? edited = AskDoseGy("Dose de prescrição da soma (conjunta)",
                            "Prescrição sugerida para a soma (boost sequencial):\n" + metodo + "\n\n" +
                            Fmt(sugGy) + " Gy total, ~" + sugFx + " fx.\n\n" +
                            "Confirme ou ajuste:",
                            sugGy);
                        if (edited == null) return;   // cancelado
                        double rxg = edited.Value;
                        if (double.IsNaN(rxg) || rxg <= 0) { MessageBox.Show("Dose de prescrição inválida."); return; }

                        rxGroups.Add(new RxGroup
                        {
                            Members = comps, Label = "Soma", RxGy = rxg, Fx = sugFx,
                            UsedEqd2 = usouEqd2, AlphaBeta = alphaBeta
                        });
                    }
                }
            }

            // ---- monta todas as tabelas embarcadas ----
            var tables = new List<ConstraintTable>();
            tables.AddRange(BuildTimmerman());
            tables.AddRange(BuildAstro());
            tables.AddRange(BuildBrazilBreast());
            tables.AddRange(BuildCorsair());

            // ================= PASSO 1: escolher a tabela (publicação) =================
            // Avaliação CONJUNTA: uma única tabela para a soma inteira, usando a Prescrição do conjunto.
            // As listas ficam com 1 item (mantidas para compatibilidade do relatório).
            var chosenTables = new List<ConstraintTable>();
            var chosenRxGy = new List<double>();
            var chosenFx = new List<int>();
            var chosenGroupLabel = new List<string>();
            bool askMore = true;
            while (askMore)
            {
                double rxForDefault; int fxForDefault; string groupLabel = null;
                if (!isSum) { rxForDefault = rxGy; fxForDefault = planFx; }
                else { rxForDefault = rxGroups[0].RxGy; fxForDefault = rxGroups[0].Fx; groupLabel = rxGroups[0].Label; }

                var pubs = tables.Select(t => t.Publication).Distinct().ToList();
                int pi = PickFromList("Constraints por publicação",
                                      "Escolha a publicação de referência:",
                                      pubs, DefaultPubIndex(pubs, fxForDefault, ss));
                if (pi < 0) { if (chosenTables.Count == 0) return; else break; }
                string pub = pubs[pi];

                ConstraintTable chosen = null;
                if (pub.StartsWith("Timmerman"))
                {
                    var fxTables = tables.Where(t => t.Publication == pub)
                                         .OrderBy(t => t.MatchFx[0]).ToList();
                    var labels = fxTables.Select(t =>
                            string.Format("{0} fração(oes)   [{1}]", t.MatchFx[0], t.Regimen)).ToList();
                    int def = fxTables.FindIndex(t => t.MatchFx.Contains(fxForDefault));
                    int fi = PickFromList("Timmerman 8-2021",
                            string.Format("Número de frações  (referência = {0} fx):", fxForDefault),
                            labels, def);
                    if (fi < 0) { if (chosenTables.Count == 0) return; else break; }
                    chosen = fxTables[fi];
                }
                else
                {
                    var sites = tables.Where(t => t.Publication == pub)
                                      .Select(t => t.Site).Distinct().ToList();
                    // Sítio único (ex.: Consenso de Mama -> só "Mama"): não abre janela.
                    string site;
                    if (sites.Count == 1) site = sites[0];
                    else
                    {
                        int siteDef = SuggestSite(sites, ss);
                        int sidx = PickFromList(pub, "Escolha o sítio anatômico:", sites, siteDef);
                        if (sidx < 0) { if (chosenTables.Count == 0) return; else break; }
                        site = sites[sidx];
                    }

                    var siteTables = tables.Where(t => t.Publication == pub && t.Site == site).ToList();
                    var labels = siteTables.Select(t => t.Title + "   [" + t.Regimen + "]").ToList();
                    int tdef = siteTables.FindIndex(t => t.MatchFx != null && t.MatchFx.Contains(fxForDefault));
                    int tidx = PickFromList(pub + " - " + site,
                            string.Format("Escolha o regime  (referência = {0} fx, {1:0.#} Gy):",
                                          fxForDefault, rxForDefault),
                            labels, tdef);
                    if (tidx < 0) { if (chosenTables.Count == 0) return; else break; }
                    chosen = siteTables[tidx];
                }

                chosenTables.Add(chosen);
                chosenRxGy.Add(rxForDefault);
                chosenFx.Add(fxForDefault);
                chosenGroupLabel.Add(groupLabel);

                askMore = false;   // avaliação conjunta: uma tabela para a soma inteira
            }

            // ================= avaliar cada tabela escolhida =================
            var perTable = new List<List<Result>>();
            for (int t = 0; t < chosenTables.Count; t++)
            {
                var res = new List<Result>();
                foreach (var c in chosenTables[t].Rows)
                    res.AddRange(EvaluateConstraint(item, ss, chosenRxGy[t], c));
                perTable.Add(res);
            }

            // ================= relatório =================
            string html = BuildHtml(context, item, isSum, rxGroups, allFracOk, ss,
                                     chosenTables, chosenRxGy, chosenFx, chosenGroupLabel, perTable);
            WriteAndOpen(context.Patient.Id, "Constraints", html);
        }

        // ------------------------------------------------------------------
        //  PRE-SELEÇÃO INTELIGENTE
        // ------------------------------------------------------------------
        private int DefaultPubIndex(List<string> pubs, int planFx, StructureSet ss)
        {
            // estruturas de mama presentes -> sugere o Consenso Brasileiro de Mama.
            if (ss != null)
            {
                var ids = ss.Structures.Select(s => s.Id.ToLowerInvariant());
                if (ids.Any(i => i.Contains("mama") || i.Contains("breast")))
                {
                    int bi = pubs.FindIndex(p => p.StartsWith("Consenso"));
                    if (bi >= 0) return bi;
                }
            }
            // senao: fracionamento tipico de SBRT -> sugere Timmerman; senao ASTRO.
            bool sbrt = (planFx >= 1 && planFx <= 8);
            int idx = pubs.FindIndex(p => sbrt ? p.StartsWith("Timmerman") : p.StartsWith("ASTRO"));
            return idx < 0 ? 0 : idx;
        }

        private int SuggestSite(List<string> sites, StructureSet ss)
        {
            // heurística simples por estruturas presentes.
            // marcadores ESPECÍFICOS primeiro (mama, C&P, reto) antes dos ambíguos.
            var ids = ss.Structures.Select(s => s.Id.ToLowerInvariant()).ToList();
            Func<string, bool> has = k => ids.Any(i => i.Contains(k));
            Func<string, int> idx = key => Math.Max(0, sites.FindIndex(s => s.StartsWith(key)));

            if (has("mama") || has("breast") || has("mamaria") || has("sclav") || has("supraclav"))
                return idx("Mama");
            if (has("parotid") || has("parotida") || has("mandibul") || has("constrict") ||
                has("carotid") || has("submand") || has("laringe") || has("larynx") || has("cavity_oral"))
                return idx("Cabeça");
            if (has("mesorret") || has("mesorect") || has("vagina") || has("genital"))
                return idx("Reto");
            if (has("prostat") || has("penilebulb") || has("bulbo_pen"))
                return idx("Próstata");
            if (has("liver") || has("figad") || has("hepat"))
                return idx("Fígado");
            if (has("lung") || has("pulm") || has("bronch"))
                return idx("Pulmão");
            if (has("bexiga") || has("reto") || has("bladder") || has("rectum"))
                return idx("Próstata");   // pelve genérica -> próstata (usuário pode trocar p/ Reto)
            return 0;
        }

        // ------------------------------------------------------------------
        //  UI - seletor simples (WPF, sem XAML)
        //  Retorna indice escolhido, ou -1 se cancelado.
        // ------------------------------------------------------------------
        private int PickFromList(string title, string prompt, List<string> items, int defaultIndex)
        {
            var win = new Window
            {
                Title = title,
                Width = 560,
                SizeToContent = SizeToContent.Height,
                WindowStartupLocation = WindowStartupLocation.CenterScreen,
                ResizeMode = ResizeMode.NoResize,
                Background = System.Windows.Media.Brushes.White
            };

            var root = new StackPanel { Margin = new Thickness(16) };

            root.Children.Add(new TextBlock
            {
                Text = prompt,
                FontSize = 13,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 0, 0, 10),
                TextWrapping = TextWrapping.Wrap
            });

            var list = new ListBox { Height = Math.Min(360, 34 * items.Count + 8), FontSize = 13 };
            foreach (var it in items) list.Items.Add(it);
            if (defaultIndex >= 0 && defaultIndex < items.Count) list.SelectedIndex = defaultIndex;
            else if (items.Count > 0) list.SelectedIndex = 0;
            root.Children.Add(list);

            var btnRow = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right,
                Margin = new Thickness(0, 14, 0, 0)
            };
            var ok = new Button { Content = "OK", Width = 90, Height = 30, Margin = new Thickness(0, 0, 8, 0), IsDefault = true };
            var cancel = new Button { Content = "Cancelar", Width = 90, Height = 30, IsCancel = true };
            btnRow.Children.Add(ok);
            btnRow.Children.Add(cancel);
            root.Children.Add(btnRow);

            int result = -1;
            ok.Click += (s, e) => { result = list.SelectedIndex; win.DialogResult = true; };
            list.MouseDoubleClick += (s, e) => { if (list.SelectedIndex >= 0) { result = list.SelectedIndex; win.DialogResult = true; } };

            win.Content = root;
            bool? dr = win.ShowDialog();
            return (dr == true) ? result : -1;
        }

        // ------------------------------------------------------------------
        //  UI - confirmação/edição de uma dose (Gy) — usado para a Prescrição da soma
        //  de planos, que o físico deve conferir (não é lida de TotalDose).
        //  Retorna o valor confirmado, ou null se cancelado.
        // ------------------------------------------------------------------
        private double? AskDoseGy(string title, string prompt, double suggestedGy)
        {
            var win = new Window
            {
                Title = title,
                Width = 560,
                SizeToContent = SizeToContent.Height,
                WindowStartupLocation = WindowStartupLocation.CenterScreen,
                ResizeMode = ResizeMode.NoResize,
                Background = System.Windows.Media.Brushes.White
            };

            var root = new StackPanel { Margin = new Thickness(16) };

            root.Children.Add(new TextBlock
            {
                Text = prompt,
                FontSize = 13,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 0, 0, 10),
                TextWrapping = TextWrapping.Wrap
            });

            var box = new TextBox
            {
                Text = suggestedGy.ToString("0.##", CultureInfo.InvariantCulture),
                FontSize = 14,
                Padding = new Thickness(6)
            };
            root.Children.Add(box);

            var btnRow = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right,
                Margin = new Thickness(0, 14, 0, 0)
            };
            var ok = new Button { Content = "OK", Width = 90, Height = 30, Margin = new Thickness(0, 0, 8, 0), IsDefault = true };
            var cancel = new Button { Content = "Cancelar", Width = 90, Height = 30, IsCancel = true };
            btnRow.Children.Add(ok);
            btnRow.Children.Add(cancel);
            root.Children.Add(btnRow);

            double? result = null;
            ok.Click += (s, e) =>
            {
                double v;
                string txt = (box.Text ?? "").Trim().Replace(",", ".");   // aceita vírgula (pt-BR) ou ponto
                if (double.TryParse(txt, NumberStyles.Float, CultureInfo.InvariantCulture, out v) && v > 0)
                {
                    result = v; win.DialogResult = true;
                }
                else
                {
                    MessageBox.Show("Informe um valor numérico de dose (Gy) maior que zero.");
                }
            };

            win.Content = root;
            box.Focus(); box.SelectAll();
            win.ShowDialog();
            return result;
        }

        // ==================================================================
        //  MOTOR DE AVALIAÇÃO DE MÉTRICAS
        // ==================================================================
        // aliases dos lados p/ compostos bilaterais (usados quando nao ha estrutura combinada)
        private static readonly string[] LUNG_D = { "Pulmao D", "Pulmao_D", "PulmaoD", "Lung_R", "Pulmao Direito", "Pulmao_Direito" };
        private static readonly string[] LUNG_E = { "Pulmao E", "Pulmao_E", "PulmaoE", "Lung_L", "Pulmao Esquerdo", "Pulmao_Esquerdo" };
        private static readonly string[] KID_D = { "Rim D", "Rim_D", "RimD", "Kidney_R", "Rim Direito" };
        private static readonly string[] KID_E = { "Rim E", "Rim_E", "RimE", "Kidney_L", "Rim Esquerdo" };
        // parótidas: constraint POR LADO (cada glândula isolada) — avaliadas separadamente,
        // NÃO agregadas (ao contrário de Pulmões/Rins). _R = Direita (D), _L = Esquerda (E).
        private static readonly string[] PAROT_D = { "Parotida D", "Parotida_D", "ParotidaD", "Parotid_R", "Parotid_D", "Parotid D", "Glnd_Parotid_R" };
        private static readonly string[] PAROT_E = { "Parotida E", "Parotida_E", "ParotidaE", "Parotid_L", "Parotid_E", "Parotid E", "Glnd_Parotid_L" };

        private static bool Valid(Structure s) { return s != null && !s.IsEmpty && s.Volume > 0.0; }

        // Avalia um constraint podendo gerar MAIS DE UMA linha: OARs pareados com objetivo
        // POR LADO (parótida) são avaliados em cada glândula separadamente, uma linha por
        // lado presente (Parótida D / Parótida E), cada uma com seu próprio status. Precede
        // a busca direta de EvaluateRow porque os aliases da parótida incluem os DOIS lados —
        // sem isto, a 1ª estrutura casada resolveria só UM lado (bug: avaliava uma só). Demais
        // estruturas seguem o fluxo normal (um único resultado).
        private List<Result> EvaluateConstraint(PlanningItem plan, StructureSet ss, double rxGy, Constraint c)
        {
            if (Norm(c.Structure).StartsWith("parotida"))
            {
                Structure pd = FindStructure(ss, PAROT_D[0], PAROT_D);
                Structure pe = FindStructure(ss, PAROT_E[0], PAROT_E);
                if (Valid(pd) || Valid(pe))
                {
                    var outp = new List<Result>();
                    if (Valid(pd))
                    {
                        var cd = WithStructureLabel(c, c.Structure + " D");
                        outp.Add(EvalSingle(plan, pd, rxGy, cd, new Result { C = cd }));
                    }
                    if (Valid(pe))
                    {
                        var ce = WithStructureLabel(c, c.Structure + " E");
                        outp.Add(EvalSingle(plan, pe, rxGy, ce, new Result { C = ce }));
                    }
                    return outp;
                }
                // nenhum lado contornado -> cai no fluxo padrão (linha única "Parótida" = N/A)
            }
            return new List<Result> { EvaluateRow(plan, ss, rxGy, c) };
        }

        // cópia rasa de um constraint com rótulo de estrutura próprio (gera uma linha por
        // lado em OARs pareados avaliados individualmente, ex.: parótidas D/E).
        private static Constraint WithStructureLabel(Constraint c, string label)
        {
            return new Constraint
            {
                Structure = label,
                Aliases = c.Aliases,
                Metric = c.Metric,
                Direction = c.Direction,
                Primary = c.Primary,
                Secondary = c.Secondary,
                Unit = c.Unit,
                Notes = c.Notes
            };
        }

        private Result EvaluateRow(PlanningItem plan, StructureSet ss, double rxGy, Constraint c)
        {
            var r = new Result { C = c };
            string ncan = Norm(c.Structure);

            // ---------- PTV: alvo de PRESCRICAO (nunca CTV/GTV) ----------
            if (ncan.StartsWith("ptv"))
            {
                bool generic = (c.Structure == "PTV");
                Structure ptv = ResolveTarget(plan, ss, c.Aliases, generic);
                if (ptv == null)
                {
                    r.FoundStructure = "";
                    r.Status = "NA";
                    r.AchievedText = generic ? "PTV de prescrição não identificado" : "PTV não encontrado";
                    return r;
                }
                return EvalSingle(plan, ptv, rxGy, c, r);
            }

            // ---------- Pulmão IPSILATERAL: escolhe o pulmão do LADO do alvo ----------
            // (senão o alias casaria o primeiro pulmão achado, que pode ser o contralateral —
            //  ex.: mama direita avaliando o pulmão esquerdo)
            if ((ncan.Contains("ipsilateral") || ncan.Contains("homolateral")) &&
                (ncan.Contains("pulmao") || ncan.Contains("lung")))
            {
                Structure lung = ResolveIpsiLung(plan, ss);
                if (Valid(lung)) return EvalSingle(plan, lung, rxGy, c, r);
                r.FoundStructure = "";
                r.Status = "NA";
                r.AchievedText = "pulmão ipsilateral não resolvido (lado do alvo indeterminado)";
                return r;
            }

            // ---------- Mama CONTRALATERAL: escolhe a mama do lado OPOSTO ao alvo ----------
            if ((ncan.Contains("mama") || ncan.Contains("breast")) &&
                (ncan.Contains("contralateral") || ncan.Contains("oposta")))
            {
                Structure br = ResolveContraBreast(plan, ss);
                if (Valid(br)) return EvalSingle(plan, br, rxGy, c, r);
                r.FoundStructure = "";
                r.Status = "NA";
                r.AchievedText = "mama contralateral não resolvida (lado indeterminado)";
                return r;
            }

            // ---------- estrutura direta ----------
            Structure s = FindStructure(ss, c.Structure, c.Aliases);
            if (Valid(s)) return EvalSingle(plan, s, rxGy, c, r);

            // ---------- composto bilateral (Pulmões / Rins) ----------
            if (ncan.StartsWith("pulmoes"))
            {
                Structure d = FindStructure(ss, LUNG_D[0], LUNG_D);
                Structure e = FindStructure(ss, LUNG_E[0], LUNG_E);
                if (Valid(d) && Valid(e)) return EvalCombined(plan, d, e, rxGy, c, r, "Pulmão D + Pulmão E");
                if (Valid(d)) return EvalSingle(plan, d, rxGy, c, r);   // só um lado presente
                if (Valid(e)) return EvalSingle(plan, e, rxGy, c, r);
            }
            else if (ncan == "rins")
            {
                Structure d = FindStructure(ss, KID_D[0], KID_D);
                Structure e = FindStructure(ss, KID_E[0], KID_E);
                if (Valid(d) && Valid(e)) return EvalCombined(plan, d, e, rxGy, c, r, "Rim D + Rim E");
                if (Valid(d)) return EvalSingle(plan, d, rxGy, c, r);
                if (Valid(e)) return EvalSingle(plan, e, rxGy, c, r);
            }

            // ---------- não encontrada ----------
            r.FoundStructure = "";
            r.Status = "NA";
            r.AchievedText = (s == null) ? "estrutura não encontrada" : "estrutura vazia";
            return r;
        }

        // avalia uma unica estrutura
        private Result EvalSingle(PlanningItem plan, Structure s, double rxGy, Constraint c, Result r)
        {
            r.FoundStructure = s.Id;
            try
            {
                double val; string disp;
                bool ok = ComputeMetric(plan, s, rxGy, c.Metric, c.Unit, out val, out disp);
                if (!ok) { r.Status = "CHK"; r.AchievedText = "métrica não reconhecida"; return r; }
                r.Achieved = val; r.AchievedText = disp; r.Status = Classify(c, val);
            }
            catch (Exception ex) { r.Status = "CHK"; r.AchievedText = "erro: " + ex.Message; }
            return r;
        }

        // avalia o composto de dois lados (Pulmões = D+E, Rins = D+E)
        private Result EvalCombined(PlanningItem plan, Structure sD, Structure sE,
                                    double rxGy, Constraint c, Result r, string label)
        {
            r.FoundStructure = label;
            try
            {
                double val; string disp;
                bool ok = ComputeMetricCombined(plan, sD, sE, rxGy, c.Metric, c.Unit, out val, out disp);
                if (!ok) { r.Status = "CHK"; r.AchievedText = "métrica não combinável (só Mean/V/CV)"; return r; }
                r.Achieved = val; r.AchievedText = disp; r.Status = Classify(c, val);
            }
            catch (Exception ex) { r.Status = "CHK"; r.AchievedText = "erro: " + ex.Message; }
            return r;
        }

        // memo: uma resolução por execução (plan/ss são constantes dentro de um run)
        private Structure _ipsiLungMemo; private bool _ipsiLungMemoSet;
        private Structure _contraBreastMemo; private bool _contraBreastMemoSet;

        // X (paciente) do centro de uma estrutura, à prova de exceção do ESAPI (NaN se falhar).
        private static double CenterX(Structure s)
        {
            try { return s.CenterPoint.x; } catch { return double.NaN; }
        }

        // Resolve o pulmão IPSILATERAL pelo LADO do alvo (X do sistema do paciente).
        // Ignora a estrutura combinada "ambos os pulmões". Um único pulmão de um lado -> usa-o.
        // Dois lados -> escolhe o do mesmo lado do alvo. Sem alvo/só combinado -> null (não
        // arrisca). Lógica RELATIVA (sinais em torno do ponto médio), independe do DICOM.
        private Structure ResolveIpsiLung(PlanningItem plan, StructureSet ss)
        {
            if (_ipsiLungMemoSet) return _ipsiLungMemo;
            _ipsiLungMemoSet = true;
            _ipsiLungMemo = ResolveIpsiLungCore(plan, ss);
            return _ipsiLungMemo;
        }
        private Structure ResolveIpsiLungCore(PlanningItem plan, StructureSet ss)
        {
            var lungs = ss.Structures
                .Where(x => Valid(x) && EhPulmao(x.Id) && !EhAmbosPulmoes(x.Id) && !double.IsNaN(CenterX(x)))
                .ToList();
            if (lungs.Count == 0) return null;
            if (lungs.Count == 1) return lungs[0];

            double tx = TargetRefX(plan, ss);
            if (double.IsNaN(tx)) return null;

            double midX = lungs.Average(x => CenterX(x));
            Structure best = null; double bestScore = double.NegativeInfinity;
            foreach (var x in lungs)
            {
                double score = (CenterX(x) - midX) * (tx - midX);   // > 0 = mesmo lado do alvo
                if (score > bestScore) { bestScore = score; best = x; }
            }
            return best;
        }

        // true se o nome sugere pulmão (qualquer lado ou combinado).
        private static bool EhPulmao(string id)
        {
            string n = Norm(id);
            return n.Contains("lung") || n.Contains("pulmao") || n.Contains("pulmoes");
        }

        // true se o nome sugere "ambos os pulmões" (combinado, SEM marca de lado).
        private static bool EhAmbosPulmoes(string id)
        {
            string n = Norm(id);
            bool plural = n.Contains("pulmoes") || n.Contains("lungs") || n.Contains("ambos") || n.Contains("both");
            if (!plural) return false;
            bool temLado = n.Contains("ipsi") || n.Contains("contra") || n.Contains("homo") ||
                           n.Contains("_d") || n.Contains("_e") || n.Contains("_l") || n.Contains("_r") ||
                           n.Contains("dir") || n.Contains("esq") || n.Contains("left") || n.Contains("right");
            return !temLado;
        }

        // Resolve a mama CONTRALATERAL. (1) rótulo explícito; (2) geometria (lado oposto ao alvo).
        private Structure ResolveContraBreast(PlanningItem plan, StructureSet ss)
        {
            if (_contraBreastMemoSet) return _contraBreastMemo;
            _contraBreastMemoSet = true;
            _contraBreastMemo = ResolveContraBreastCore(plan, ss);
            return _contraBreastMemo;
        }
        private Structure ResolveContraBreastCore(PlanningItem plan, StructureSet ss)
        {
            var breasts = ss.Structures.Where(x => Valid(x) && EhMamaOar(x.Id) && !double.IsNaN(CenterX(x))).ToList();
            if (breasts.Count == 0) return null;

            // (1) rótulo explícito de contralateral tem prioridade (nome é autoritativo)
            var rotulada = breasts.FirstOrDefault(x =>
            {
                string n = Norm(x.Id);
                return n.Contains("contralateral") || n.Contains("contra") || n.Contains("_cl") || n.Contains(" cl");
            });
            if (Valid(rotulada)) return rotulada;

            // (2) geometria: mama do lado OPOSTO ao alvo (relativo à linha média do corpo)
            double tx = TargetRefX(plan, ss);
            double mid = BodyMidX(ss);
            if (double.IsNaN(tx) || double.IsNaN(mid)) return null;
            double tside = tx - mid;
            Structure best = null; double bestScore = double.NegativeInfinity;
            foreach (var b in breasts)
            {
                double score = -(CenterX(b) - mid) * tside;   // > 0 = lado oposto ao alvo
                if (score > bestScore) { bestScore = score; best = b; }
            }
            return bestScore > 0 ? best : null;   // só devolve se realmente há mama do lado oposto
        }

        // true se o nome sugere uma MAMA como OAR (exclui alvos PTV/CTV/GTV e cadeias nodais
        // — "Cadeia Mamária Interna"/IMN contêm "mama" mas são alvos, não a mama-órgão).
        private static bool EhMamaOar(string id)
        {
            string n = Norm(id);
            if (n.StartsWith("ptv") || n.StartsWith("ctv") || n.StartsWith("gtv")) return false;
            if (!(n.Contains("mama") || n.Contains("breast"))) return false;
            if (n.Contains("cadeia") || n.Contains("mamaria") || n.Contains("imn") ||
                n.Contains("linfonodo") || n.Contains("node") || n.Contains("fsc") ||
                n.Contains("supracla") || n.Contains("cln")) return false;
            return true;
        }

        // X (paciente) da LINHA MÉDIA do corpo. Body/External -> ponto médio dos pulmões. NaN se nada.
        private double BodyMidX(StructureSet ss)
        {
            var body = ss.Structures.FirstOrDefault(x =>
            {
                if (!Valid(x)) return false;
                string n = Norm(x.Id);
                return n.Contains("body") || n.Contains("external") || n.Contains("externo") || n.Contains("paciente");
            });
            if (Valid(body) && !double.IsNaN(CenterX(body))) return CenterX(body);
            var lungs = ss.Structures.Where(x => Valid(x) && EhPulmao(x.Id) && !double.IsNaN(CenterX(x))).ToList();
            if (lungs.Count >= 1) return lungs.Average(x => CenterX(x));
            return double.NaN;
        }

        // X (paciente) de um ponto do ALVO, p/ descobrir o lado tratado. Prioridade:
        // alvo do plano (PlanSetup) -> maior PTV -> maior mama-órgão (não contra/não-alvo/nodal).
        private double TargetRefX(PlanningItem plan, StructureSet ss)
        {
            var ps = plan as PlanSetup;
            if (ps != null)
            {
                string tgt = null; try { tgt = ps.TargetVolumeID; } catch { }
                if (!string.IsNullOrEmpty(tgt))
                {
                    var t = ss.Structures.FirstOrDefault(x => x.Id == tgt);
                    if (Valid(t) && !double.IsNaN(CenterX(t))) return CenterX(t);
                }
            }
            var ptv = ss.Structures.Where(x => Valid(x) && Norm(x.Id).StartsWith("ptv") && !double.IsNaN(CenterX(x)))
                                   .OrderByDescending(x => x.Volume).FirstOrDefault();
            if (Valid(ptv)) return CenterX(ptv);
            var mama = ss.Structures.Where(x =>
            {
                if (!Valid(x) || !EhMamaOar(x.Id) || double.IsNaN(CenterX(x))) return false;
                string n = Norm(x.Id);
                return !(n.Contains("contralateral") || n.Contains("contra") || n.Contains("nao-alvo") ||
                         n.Contains("uninvolved") || n.Contains("_cl"));
            }).OrderByDescending(x => x.Volume).FirstOrDefault();
            if (Valid(mama)) return CenterX(mama);
            return double.NaN;
        }

        // Resolve o PTV de prescrição. NUNCA retorna CTV/GTV (só estruturas cujo
        // ID normalizado começa com "ptv"). Para PTV genérico prioriza o alvo do plano.
        private Structure ResolveTarget(PlanningItem plan, StructureSet ss, string[] aliases, bool generic)
        {
            Func<Structure, bool> isPtv = x => Valid(x) && Norm(x.Id).StartsWith("ptv");

            if (generic)
            {
                // TargetVolumeID só existe em PlanSetup — PlanSum não tem alvo de prescrição
                // próprio; nesse caso cai direto para o fallback "PTV único" mais abaixo.
                string tgt = null;
                PlanSetup asPs = plan as PlanSetup;
                if (asPs != null) { try { tgt = asPs.TargetVolumeID; } catch { } }
                if (!string.IsNullOrEmpty(tgt))
                {
                    string nt = Norm(tgt);
                    var t = ss.Structures.FirstOrDefault(x => isPtv(x) && Norm(x.Id) == nt);
                    if (t != null) return t;   // alvo de prescrição do plano (é um PTV)
                }
            }

            // casa por alias, mas SOMENTE estruturas PTV
            var wanted = new List<string>();
            foreach (var a in aliases) { string w = Norm(a); if (w.Length > 0) wanted.Add(w); }
            foreach (var x in ss.Structures)
                if (isPtv(x) && wanted.Contains(Norm(x.Id))) return x;

            // genérico: se existe exatamente um PTV, usa-o
            if (generic)
            {
                var ptvs = ss.Structures.Where(isPtv).ToList();
                if (ptvs.Count == 1) return ptvs[0];
            }
            return null;
        }

        private string Classify(Constraint c, double val)
        {
            if (c.Direction == Dir.MAX)
            {
                if (val <= c.Primary + 1e-6) return "OK";
                if (c.Secondary.HasValue && val <= c.Secondary.Value + 1e-6) return "ATN";
                return "FAIL";
            }
            else // MIN
            {
                if (val >= c.Primary - 1e-6) return "OK";
                if (c.Secondary.HasValue && val >= c.Secondary.Value - 1e-6) return "ATN";
                return "FAIL";
            }
        }

        // Calcula o valor atingido na unidade de comparacao definida em c.Unit.
        private bool ComputeMetric(PlanningItem plan, Structure s, double rxGy,
                                   string metric, string unit, out double value, out string display)
        {
            value = double.NaN; display = "";
            metric = metric.Trim();

            // ----- Mean -----
            if (metric.Equals("Mean", StringComparison.OrdinalIgnoreCase))
            {
                double dGy = MeanDoseGy(plan, s);
                if (unit == "%") { value = dGy / rxGy * 100.0; display = F(value) + "%"; }
                else { value = dGy; display = F(value) + " Gy"; }
                return true;
            }

            // ----- D<vol>(% | cc)  -> dose numa fração de volume -----
            var mD = Regex.Match(metric, @"^D([0-9]+(?:\.[0-9]+)?)(%|cc)$", RegexOptions.IgnoreCase);
            if (mD.Success)
            {
                double arg = double.Parse(mD.Groups[1].Value, CultureInfo.InvariantCulture);
                bool rel = mD.Groups[2].Value == "%";
                var vp = rel ? VolumePresentation.Relative : VolumePresentation.AbsoluteCm3;
                double dGy = DoseGyAtVol(plan, s, arg, vp);
                if (unit == "%") { value = dGy / rxGy * 100.0; display = F(value) + "% Prescrição"; }
                else { value = dGy; display = F(value) + " Gy"; }
                return true;
            }

            // ----- V<dose>(Gy | %) -> volume acima de uma dose -----
            var mV = Regex.Match(metric, @"^V([0-9]+(?:\.[0-9]+)?)(Gy|%)$", RegexOptions.IgnoreCase);
            if (mV.Success)
            {
                double arg = double.Parse(mV.Groups[1].Value, CultureInfo.InvariantCulture);
                bool doseIsPct = mV.Groups[2].Value == "%";
                double dGy = doseIsPct ? (arg / 100.0 * rxGy) : arg;
                if (unit == "cc")
                {
                    value = VolAtDoseGy(plan, s, dGy, VolumePresentation.AbsoluteCm3);
                    display = F(value) + " cc";
                }
                else // %
                {
                    value = VolAtDoseGy(plan, s, dGy, VolumePresentation.Relative);
                    display = F(value) + "%";
                }
                return true;
            }

            // ----- CV<dose>Gy -> volume "frio" (recebe <= dose) em cc -----
            var mCV = Regex.Match(metric, @"^CV([0-9]+(?:\.[0-9]+)?)Gy$", RegexOptions.IgnoreCase);
            if (mCV.Success)
            {
                double dGy = double.Parse(mCV.Groups[1].Value, CultureInfo.InvariantCulture);
                double hotCc = VolAtDoseGy(plan, s, dGy, VolumePresentation.AbsoluteCm3);
                value = s.Volume - hotCc;               // volume que recebe <= dGy
                display = F(value) + " cc <" + F(dGy) + "Gy";
                return true;
            }

            return false;
        }

        // Combina duas estruturas (D + E) para OARs bilaterais (Pulmões, Rins).
        // Suporta Mean (média ponderada por volume), V (soma de volumes) e CV (volume frio total).
        // NAO suporta D-métricas (dose a volume) — nem são usadas nesses OARs.
        private bool ComputeMetricCombined(PlanningItem plan, Structure sD, Structure sE, double rxGy,
                                           string metric, string unit, out double value, out string display)
        {
            value = double.NaN; display = "";
            metric = metric.Trim();
            double volD = sD.Volume, volE = sE.Volume, volT = volD + volE;

            // ----- Mean (média ponderada por volume) -----
            if (metric.Equals("Mean", StringComparison.OrdinalIgnoreCase))
            {
                double dGy = (volD * MeanDoseGy(plan, sD) + volE * MeanDoseGy(plan, sE)) / volT;
                if (unit == "%") { value = dGy / rxGy * 100.0; display = F(value) + "%"; }
                else { value = dGy; display = F(value) + " Gy"; }
                return true;
            }

            // ----- V<dose>(Gy|%) — soma o volume dos dois lados -----
            var mV = Regex.Match(metric, @"^V([0-9]+(?:\.[0-9]+)?)(Gy|%)$", RegexOptions.IgnoreCase);
            if (mV.Success)
            {
                double arg = double.Parse(mV.Groups[1].Value, CultureInfo.InvariantCulture);
                bool doseIsPct = mV.Groups[2].Value == "%";
                double dGy = doseIsPct ? (arg / 100.0 * rxGy) : arg;
                double sumCc = VolAtDoseGy(plan, sD, dGy, VolumePresentation.AbsoluteCm3)
                             + VolAtDoseGy(plan, sE, dGy, VolumePresentation.AbsoluteCm3);
                if (unit == "cc") { value = sumCc; display = F(value) + " cc"; }
                else { value = sumCc / volT * 100.0; display = F(value) + "%"; }
                return true;
            }

            // ----- CV<dose>Gy — volume frio total (D+E) -----
            var mCV = Regex.Match(metric, @"^CV([0-9]+(?:\.[0-9]+)?)Gy$", RegexOptions.IgnoreCase);
            if (mCV.Success)
            {
                double dGy = double.Parse(mCV.Groups[1].Value, CultureInfo.InvariantCulture);
                double hotCc = VolAtDoseGy(plan, sD, dGy, VolumePresentation.AbsoluteCm3)
                             + VolAtDoseGy(plan, sE, dGy, VolumePresentation.AbsoluteCm3);
                value = volT - hotCc;
                display = F(value) + " cc <" + F(dGy) + "Gy";
                return true;
            }

            return false;   // D-métricas não são combináveis desta forma
        }

        // ---------------- Helpers de DVH (retornam sempre em Gy / unidade pedida) ----------------
        private double MeanDoseGy(PlanningItem plan, Structure s)
        {
            var d = plan.GetDVHCumulativeData(s, DoseValuePresentation.Absolute,
                                              VolumePresentation.Relative, 0.1);
            return (d == null) ? double.NaN : ToGy(d.MeanDose);
        }

        private double DoseGyAtVol(PlanningItem plan, Structure s, double vol, VolumePresentation vp)
        {
            DoseValue dv = plan.GetDoseAtVolume(s, vol, vp, DoseValuePresentation.Absolute);
            return ToGy(dv);
        }

        // Volume (na apresentacao pedida) que recebe >= doseGy. Robusto a Gy/cGy.
        private double VolAtDoseGy(PlanningItem plan, Structure s, double doseGy, VolumePresentation vp)
        {
            try
            {
                return plan.GetVolumeAtDose(s, new DoseValue(doseGy, DoseValue.DoseUnit.Gy), vp);
            }
            catch
            {
                return plan.GetVolumeAtDose(s, new DoseValue(doseGy * 100.0, DoseValue.DoseUnit.cGy), vp);
            }
        }

        private static double ToGy(DoseValue dv)
        {
            if (dv.Unit == DoseValue.DoseUnit.cGy) return dv.Dose / 100.0;
            if (dv.Unit == DoseValue.DoseUnit.Gy) return dv.Dose;
            return double.NaN;
        }

        private Structure FindStructure(StructureSet ss, string id, string[] aliases)
        {
            // casamento insensivel a ACENTO e CAIXA (robusto para IDs pt-BR do Eclipse)
            var wanted = new List<string> { Norm(id) };
            foreach (var a in aliases) wanted.Add(Norm(a));

            // 1a passada: correspondência exata (normalizada)
            foreach (var s in ss.Structures)
            {
                string ns = Norm(s.Id);
                if (wanted.Any(w => w.Length > 0 && w == ns)) return s;
            }
            return null;
        }

        // normaliza: remove diacriticos (acentos), caixa baixa e trim.
        // Ex.: "Fígado" == "Fígado" == "FÍGADO"; "Coração" == "Coração".
        private static string Norm(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            string d = s.Normalize(NormalizationForm.FormD);
            var sb = new StringBuilder();
            foreach (char ch in d)
                if (System.Globalization.CharUnicodeInfo.GetUnicodeCategory(ch)
                        != System.Globalization.UnicodeCategory.NonSpacingMark)
                    sb.Append(ch);
            return sb.ToString().Normalize(NormalizationForm.FormC).Trim().ToLowerInvariant();
        }

        private static string F(double v)
        {
            if (double.IsNaN(v)) return "-";
            return v.ToString("0.##", CultureInfo.InvariantCulture);
        }

        // ==================================================================
        //  DADOS: TIMMERMAN 8-2021  (tecidos seriais + paralelos)
        //  Serial : D{V}cc <= VolumeMax(Gy)  e  D0.035cc <= MaxPoint(Gy)
        //  Paralelo: CV{Dose}Gy >= volume crítico(cc)  (volume poupado)
        // ==================================================================
        private string Dcc(double v)
        {
            return "D" + v.ToString("0.###", CultureInfo.InvariantCulture) + "cc";
        }

        // serial: adiciona a linha de dose-a-volume e/ou a dose de ponto (near-max)
        private void TS(ConstraintTable t, string st, string al,
                        double volCc, double? volMaxGy, double? ptGy)
        {
            if (volMaxGy.HasValue)
                t.Add(st, Dcc(volCc), Dir.MAX, volMaxGy.Value, null, "Gy", "", al);
            if (ptGy.HasValue)
                t.Add(st, "D0.035cc", Dir.MAX, ptGy.Value, null, "Gy", "dose de ponto (near-max)", al);
        }

        // paralelo: volume crítico (cc) que deve ser poupado abaixo da dose
        private void TP(ConstraintTable t, string st, string al, double critCc, double doseGy)
        {
            t.Add(st, "CV" + doseGy.ToString("0.###", CultureInfo.InvariantCulture) + "Gy",
                  Dir.MIN, critCc, null, "cc",
                  "volume crítico poupado (M 1500 / F 950 cc quando aplicável)", al);
        }

        private ConstraintTable NewTimmerman(int fx, string regimen)
        {
            return new ConstraintTable
            {
                Publication = "Timmerman 8-2021 (SBRT/SABR)",
                Site = "SBRT/SABR",
                Title = fx + " frações",
                Regimen = regimen,
                MatchFx = new[] { fx }
            };
        }

        private List<ConstraintTable> BuildTimmerman()
        {
            var all = new List<ConstraintTable>();

            // aliases comuns (TG-263 + pt-BR)
            string aCord = "SpinalCord|Medula|SpinalCanal|Cord|Medula_Espinhal";
            string aEso = ALS_ESOFAGO;
            string aHeart = "Heart|Coração|Heart";
            string aGV = "GreatVes|GreatVessels|Grandes_Vasos|GreatVes|Grandes Vasos";
            string aTra = "Trachea|Traqueia|Trachea_Prox|Bronchus_Main";
            string aBr = "Bronchus|Brônquio|SmallBronchus";
            string aRib = ALS_COSTELAS;
            string aSkin = ALS_PELE;
            string aSto = ALS_ESTOMAGO;
            string aDuo = ALS_DUODENO;
            string aBowel = "SmallBowel|Bowel_Small|Intestino|Jejunum_Ileum|Bowel Small";
            string aColon = "Cólon|Bowel_Large|Colo|Bowel Large";
            string aRect = "Reto|Rectum";
            string aBlad = "Bexiga|Bladder|Bladder_Wall";
            string aLung = "Lungs|Pulmões|Lungs-GTV|Lung|Pulmão|Pulmao D|Pulmao E";
            string aLiver = "Liver|Fígado|Liver-GTV|Liver_GTV";
            string aKid = "Kidneys|Renal_Cortex|Rins|RenalCortex";
            string aBrain = "Brainstem|Tronco|BrainStem|Tronco Cerebral";
            string aOptic = "OpticNerves|Via_Optica|OpticChiasm";
            string aBrach = "BrachialPlex|BrachialPlexus|Plexo_Braquial|BrachialPlex|Plexo Braquial Dir|Plexo Braquial Esq";
            string aFemD = ALS_FEMUR_D;
            string aFemE = ALS_FEMUR_E;
            string aPen = "PenileBulb|Bulbo_Peniano|Bulbo";
            string aCauda = "CaudaEquina|Cauda_Equina|Cauda Equina";
            string aSac = "SacralPlexus|Plexo_Sacral";

            // ---- fábrica de uma tabela por fração ----
            // valores: (volMaxGy, ptGy) por órgão, indexados pela fração
            // 1,2,3,4,5,8 frações
            var fxList = new[] { 1, 2, 3, 4, 5, 8 };
            var regimens = new Dictionary<int, string>
            {
                {1,"1 fx (dose única)"},{2,"2 fx"},{3,"3 fx (clássico)"},
                {4,"4 fx"},{5,"5 fx (clássico)"},{8,"8 fx"}
            };

            // tabelas de valores [1fx,2fx,3fx,4fx,5fx,8fx]
            // Optic pathway <0.2
            AddSerialSet(all, fxList, regimens, aOptic, "Via óptica", 0.2,
                new double?[]{8,11.7,15.3,19.2,23,27.2}, new double?[]{10,13.7,17.4,21.2,25,29.6});
            // Brainstem <0.5
            AddSerialSet(all, fxList, regimens, aBrain, "Tronco cerebral", 0.5,
                new double?[]{10,13,15.9,20.8,23,27.2}, new double?[]{15,19.1,23.1,27.2,31,37.6});
            // Spinal cord/medulla <0.35
            AddSerialSet(all, fxList, regimens, aCord, "Medula espinhal", 0.35,
                new double?[]{10,13,15.9,18,22,26.4}, new double?[]{14,18.3,22.5,25.6,28,33.6});
            // Cauda equina <5
            AddSerialSet(all, fxList, regimens, aCauda, "Cauda equina", 5,
                new double?[]{14,18,21.9,26,30,34}, new double?[]{16,20.8,25.5,28.8,31.5,38.4});
            // Sacral plexus <5
            AddSerialSet(all, fxList, regimens, aSac, "Plexo sacral", 5,
                new double?[]{14.4,18.5,22.5,26,30,34}, new double?[]{16,20.8,25.5,28.8,32,38.4});
            // Esophagus <5
            AddSerialSet(all, fxList, regimens, aEso, "Esôfago", 5,
                new double?[]{20,24.3,27.9,30.4,32.5,36.8}, new double?[]{24,28.3,32.4,35.6,38,43.2});
            // Brachial plexus <3
            AddSerialSet(all, fxList, regimens, aBrach, "Plexo braquial", 3,
                new double?[]{13.6,17.8,22,24.8,27,32.8}, new double?[]{16.4,21.2,26,29.6,32.5,39.2});
            // Heart/pericardium <15
            AddSerialSet(all, fxList, regimens, aHeart, "Coração/pericárdio", 15,
                new double?[]{16,20,24,28,32,34.4}, new double?[]{22,26,30,34,38,40});
            // Great vessels <10
            AddSerialSet(all, fxList, regimens, aGV, "Grandes vasos", 10,
                new double?[]{31,35,39,43,47,55.2}, new double?[]{37,41,45,49,53,62});
            // Trachea/large bronchus (<4 em 1-2 fx, <5 depois)
            AddSerialSetVarVol(all, fxList, regimens, aTra, "Traqueia/brônquio principal",
                new double[]{4,4,5,5,5,5},
                new double?[]{27.5,34.5,39,42.4,45,50}, new double?[]{30,38,43,47,50,56});
            // Bronchus smaller airways <0.5
            AddSerialSet(all, fxList, regimens, aBr, "Brônquios menores", 0.5,
                new double?[]{17.4,21.6,25.8,28.8,32,38.4}, new double?[]{20.2,25.1,30,34.8,40,48.8});
            // Rib <5
            AddSerialSet(all, fxList, regimens, aRib, "Costela", 5,
                new double?[]{28,34,40,43,45,50}, new double?[]{33,41.5,50,54,57,63});
            // Skin <10
            AddSerialSet(all, fxList, regimens, aSkin, "Pele", 10,
                new double?[]{25.5,28.3,31,33.6,36.5,43.2}, new double?[]{27.5,30.3,33,36,38.5,45.6});
            // Stomach <5
            AddSerialSet(all, fxList, regimens, aSto, "Estômago", 5,
                new double?[]{17.4,20,22.5,25,26.5,31.2}, new double?[]{22,26,30,33.2,35,42});
            // Duodenum <5
            AddSerialSet(all, fxList, regimens, aDuo, "Duodeno", 5,
                new double?[]{17.4,20,22.5,25,26.5,31.2}, new double?[]{22,26,30,33.2,35,42});
            // Jejunum/ileum <30
            AddSerialSet(all, fxList, regimens, aBowel, "Jejuno/íleo", 30,
                new double?[]{17.6,19.2,20.7,22.4,24,28.8}, new double?[]{20,24,28.5,31.6,34.5,40});
            // Cólon <20
            AddSerialSet(all, fxList, regimens, aColon, "Cólon", 20,
                new double?[]{20.5,25.8,28.8,30.8,32.5,35.2}, new double?[]{31,39,45,48.5,52.5,57.5});
            // Bladder wall <15
            AddSerialSet(all, fxList, regimens, aBlad, "Parede vesical", 15,
                new double?[]{12,14.5,17,18.5,20,22.4}, new double?[]{25,29,33,35.6,38,44.8});
            // Femur (cada lado separadamente) <10cc (so volume max)
            AddSerialSet(all, fxList, regimens, aFemD, "Femur D", 10,
                new double?[]{15,19.5,24,27,30,35}, new double?[]{null,null,null,null,null,null});
            AddSerialSet(all, fxList, regimens, aFemE, "Femur E", 10,
                new double?[]{15,19.5,24,27,30,35}, new double?[]{null,null,null,null,null,null});
            // Penile bulb <3 (so volume max)
            AddSerialSet(all, fxList, regimens, aPen, "Bulbo peniano", 3,
                new double?[]{16,20.5,25,27,30,35}, new double?[]{null,null,null,null,null,null});
            // Rectum: DUAS colunas de volume (<3.5cc e <20cc) + ponto
            AddRectum(all, fxList, regimens, aRect,
                new double[]{30,38,43,47.2,50,56},      // D3.5cc
                new double[]{23,26.7,30.3,34,37.5,45},  // D20cc
                new double[]{33.7,41.3,47,51.6,55,61.5});// ponto

            // ---- paralelos ----
            var lungDose = new double[]{7.2,9.4,10.8,12,12.5,14.4};
            var lungV    = new double[]{8,10,11.4,12.8,13.5,15.2};
            var liverDose= new double[]{11.6,15.1,17.7,19.6,21.5,24.8};
            var kidDose  = new double[]{9.5,12.5,14.7,16,17.5,20};
            for (int i = 0; i < fxList.Length; i++)
            {
                var t = all.First(x => x.MatchFx[0] == fxList[i]);
                TP(t, "Pulmões-GTV", aLung, 1500, lungDose[i]);
                t.Add("Pulmões-GTV", "V" + lungV[i].ToString("0.###", CultureInfo.InvariantCulture) + "Gy",
                      Dir.MAX, 37, null, "%", "Lungs-GTV", aLung);
                TP(t, "Fígado-GTV", aLiver, 700, liverDose[i]);
                TP(t, "Córtex renal", aKid, 200, kidDose[i]);
            }

            // 10, 15 e 20 fracoes (formato estendido, so "Volume max (Gy)" + Mean; sem dose de ponto)
            BuildTimmermanHi(all, aOptic, aBrain, aCord, aCauda, aSac, aEso, aBrach, aHeart,
                             aGV, aTra, aSkin, aSto, aDuo, aBowel, aColon, aRect, aBlad,
                             aFemD, aFemE, aPen, aLung, aLiver, aKid);

            return all;
        }

        // Tabelas Timmerman 10/15/20 fracoes (Tab. 8, 9, 10 do artigo).
        // Conjunto de OARs ampliado e limiares de volume diferentes das tabelas 1-8 fx.
        private void BuildTimmermanHi(List<ConstraintTable> all,
            string aOptic, string aBrain, string aCord, string aCauda, string aSac, string aEso,
            string aBrach, string aHeart, string aGV, string aTra, string aSkin, string aSto,
            string aDuo, string aBowel, string aColon, string aRect, string aBlad, string aFemD,
            string aFemE, string aPen, string aLung, string aLiver, string aKid)
        {
            string aRetina = "Retina|Eye_Retina|Eye_L|Eye_R|Olho";
            string aLacrim = "Lacrimal|Glandula_Lacrimal|LacrimalGland";
            string aCochlea = "Cochlea|Coclea|Coclea D|Coclea E";
            string aParotid = "Parotid|Parotida|Parotid_L|Parotid_R|Glnd_Submand|Parotida D|Parotida E";
            string aLarynx = "Larynx|Laringe";
            string aTMJ = "TMJoint|ATM|TM_Joint|ATM D|ATM E";
            string aRenalH = "RenalHilum|Hilo_Renal|Renal_Hilum";
            string aBladSup = "Bladder_Suprapubic|Bexiga_Suprapubica|Bladder_Wall";

            int[] fxs = { 10, 15, 20 };
            string[] regs = { "10 fx", "15 fx", "20 fx" };
            for (int i = 0; i < fxs.Length; i++)
            {
                var t = new ConstraintTable
                {
                    Publication = "Timmerman 8-2021 (SBRT/SABR)",
                    Site = "SBRT/SABR",
                    Title = fxs[i] + " fracoes",
                    Regimen = regs[i] + " (hipofracionamento moderado)",
                    MatchFx = new[] { fxs[i] }
                };

                // helper local via lambdas nao suportado no ambiente; uso t.Add direto.
                double[] optic = { 30.6, 39, 42 };      t.Add("Via óptica", "D0.5cc", Dir.MAX, optic[i], null, "Gy", "", aOptic);
                double[] retina = { 26, 33, 36 };        t.Add("Retina", "Mean", Dir.MAX, retina[i], null, "Gy", "cada lado", aRetina);
                double[] lacr = { 14.1, 18, 18 };        t.Add("Gl. lacrimal", "D1cc", Dir.MAX, lacr[i], null, "Gy", "cada lado", aLacrim);
                double[] coch = { 25, 30, 32 };          t.Add("Cóclea", "D0.5cc", Dir.MAX, coch[i], null, "Gy", "cada lado", aCochlea);
                double[] brain = { 32, 40, 44 };         t.Add("Tronco cerebral", "D5cc", Dir.MAX, brain[i], null, "Gy", "", aBrain);
                double[] cord = { 31, 39, 42 };          t.Add("Medula espinhal", "D5cc", Dir.MAX, cord[i], null, "Gy", "", aCord);
                double[] parVol = { 14.1, 18, 18 };      t.Add("Parótida", "D7cc", Dir.MAX, parVol[i], null, "Gy", "cada lado", aParotid);
                double[] parMean = { 17.7, 22.5, 24 };   t.Add("Parótida", "Mean", Dir.MAX, parMean[i], null, "Gy", "cada lado", aParotid);
                double[] lar = { 30, 34.5, 36 };         t.Add("Laringe", "D3cc", Dir.MAX, lar[i], null, "Gy", "", aLarynx);
                double[] tmj = { 37.7, 48, 52 };         t.Add("ATM", "D1cc", Dir.MAX, tmj[i], null, "Gy", "cada lado", aTMJ);
                double[] cauda = { 35, 40.5, 44 };       t.Add("Cauda equina", "D5cc", Dir.MAX, cauda[i], null, "Gy", "", aCauda);
                double[] sac = { 35, 40.5, 44 };         t.Add("Plexo sacral", "D5cc", Dir.MAX, sac[i], null, "Gy", "", aSac);
                double[] eso = { 40, 45, 48 };           t.Add("Esôfago", "D5cc", Dir.MAX, eso[i], null, "Gy", "", aEso);
                double[] brac = { 37, 48, 54 };          t.Add("Plexo braquial", "D3cc", Dir.MAX, brac[i], null, "Gy", "", aBrach);
                double[] heart = { 36.6, 42, 46 };       t.Add("Coração/pericárdio", "D15cc", Dir.MAX, heart[i], null, "Gy", "", aHeart);
                double[] gv = { 55.7, 57, 60 };          t.Add("Grandes vasos", "D10cc", Dir.MAX, gv[i], null, "Gy", "", aGV);
                double[] trach = { 52, 55.5, 58 };       t.Add("Traqueia/brônquio", "D5cc", Dir.MAX, trach[i], null, "Gy", "", aTra);
                double[] skin = { 46.3, 54, 60 };        t.Add("Pele", "D10cc", Dir.MAX, skin[i], null, "Gy", "", aSkin);
                double[] sto = { 33.9, 39, 42 };         t.Add("Estômago", "D50cc", Dir.MAX, sto[i], null, "Gy", "", aSto);
                double[] duo = { 33.9, 39, 42 };         t.Add("Duodeno", "D5cc", Dir.MAX, duo[i], null, "Gy", "", aDuo);
                double[] jej = { 33.9, 39, 42 };         t.Add("Jejuno/íleo", "D120cc", Dir.MAX, jej[i], null, "Gy", "", aBowel);
                double[] rh = { 30.7, 37.5, 40 };        t.Add("Hilo renal", "D15cc", Dir.MAX, rh[i], null, "Gy", "cada lado", aRenalH);
                double[] col = { 47, 47, 50 };           t.Add("Cólon", "D20cc", Dir.MAX, col[i], null, "Gy", "", aColon);
                double[] r10 = { 52, 60, 66 };           t.Add("Reto", "D10cc", Dir.MAX, r10[i], null, "Gy", "inclui fezes", aRect);
                double[] r20 = { 49, 57, 62 };           t.Add("Reto", "D20cc", Dir.MAX, r20[i], null, "Gy", "", aRect);
                double[] r30 = { 46, 52.5, 58 };         t.Add("Reto", "D30cc", Dir.MAX, r30[i], null, "Gy", "", aRect);
                double[] r40 = { 43, 49.5, 54 };         t.Add("Reto", "D40cc", Dir.MAX, r40[i], null, "Gy", "", aRect);
                double[] b90 = { 48, 55.5, 60 };         t.Add("Bexiga", "D90cc", Dir.MAX, b90[i], null, "Gy", "com urina", aBlad);
                double[] b125 = { 45, 52.5, 56 };        t.Add("Bexiga", "D125cc", Dir.MAX, b125[i], null, "Gy", "com urina", aBlad);
                double[] bsup = { 23, 26, 28 };          t.Add("Bexiga suprapúbica", "D5cc", Dir.MAX, bsup[i], null, "Gy", "parede suprapúbica", aBladSup);
                double[] pen = { 38, 42, 44 };           t.Add("Bulbo peniano", "D3cc", Dir.MAX, pen[i], null, "Gy", "", aPen);
                double[] fem = { 38, 40, 44 };
                t.Add("Femur D", "D10cc", Dir.MAX, fem[i], null, "Gy", "", aFemD);
                t.Add("Femur E", "D10cc", Dir.MAX, fem[i], null, "Gy", "", aFemE);

                // paralelos
                double[] lung = { 15, 16.5, 18 };        TP(t, "Pulmões-GTV", aLung, 1500, lung[i]);
                double[] liver = { 27, 30, 32 };         TP(t, "Fígado-GTV", aLiver, 700, liver[i]);
                double[] kid = { 21, 24, 26 };           TP(t, "Córtex renal", aKid, 200, kid[i]);

                all.Add(t);
            }
        }

        // cria (se preciso) as 6 tabelas e adiciona um órgão serial de volume fixo
        private void AddSerialSet(List<ConstraintTable> all, int[] fxList,
            Dictionary<int,string> regimens, string aliases, string st, double volCc,
            double?[] volMax, double?[] pt)
        {
            for (int i = 0; i < fxList.Length; i++)
            {
                var t = GetOrCreate(all, fxList[i], regimens[fxList[i]]);
                TS(t, st, aliases, volCc, volMax[i], pt[i]);
            }
        }

        // idem, porém com volume que varia por fração (ex.: traqueia <4 vs <5)
        private void AddSerialSetVarVol(List<ConstraintTable> all, int[] fxList,
            Dictionary<int,string> regimens, string aliases, string st, double[] volCc,
            double?[] volMax, double?[] pt)
        {
            for (int i = 0; i < fxList.Length; i++)
            {
                var t = GetOrCreate(all, fxList[i], regimens[fxList[i]]);
                TS(t, st, aliases, volCc[i], volMax[i], pt[i]);
            }
        }

        private void AddRectum(List<ConstraintTable> all, int[] fxList,
            Dictionary<int,string> regimens, string aliases,
            double[] d35, double[] d20, double[] pt)
        {
            for (int i = 0; i < fxList.Length; i++)
            {
                var t = GetOrCreate(all, fxList[i], regimens[fxList[i]]);
                t.Add("Reto", "D3.5cc", Dir.MAX, d35[i], null, "Gy", "", aliases);
                t.Add("Reto", "D20cc", Dir.MAX, d20[i], null, "Gy", "", aliases);
                t.Add("Reto", "D0.035cc", Dir.MAX, pt[i], null, "Gy", "dose de ponto", aliases);
            }
        }

        private ConstraintTable GetOrCreate(List<ConstraintTable> all, int fx, string regimen)
        {
            var t = all.FirstOrDefault(x => x.Publication.StartsWith("Timmerman") && x.MatchFx[0] == fx);
            if (t == null) { t = NewTimmerman(fx, regimen); all.Add(t); }
            return t;
        }

        // ==================================================================
        //  DADOS: ASTRO Consensus 2025 (Puckett et al.)
        //  Cobertura v1.0: Próstata (19-23), Pulmão (11-18), Fígado (8-10).
        // ==================================================================
        private ConstraintTable NewAstro(string site, string title, string regimen, int[] matchFx)
        {
            return new ConstraintTable
            {
                Publication = "ASTRO Consensus 2025",
                Site = site,
                Title = title,
                Regimen = regimen,
                MatchFx = matchFx
            };
        }

        private List<ConstraintTable> BuildAstro()
        {
            var L = new List<ConstraintTable>();

            // aliases comuns
            string aBladder = "Bladder|Bexiga|Bladder_Wall|Bladder-CTVp";
            string aRectum  = "Rectum|Reto|Rectum_Wall";
            string aBowelL  = "Bowel_Large|Cólon|Colo|LargeBowel|Intestino_Grosso|Bowel_Lg|Bowel Large";
            string aBowelS  = "Bowel_Small|SmallBowel|Intestino_Delgado|BowelBag|Bowel_Sm|Bowel_Bag|Bowel Small";
            string aFemurD = ALS_FEMUR_D;
            string aFemurE = ALS_FEMUR_E;
            string aPenile  = "Bulbo_Peniano|PenileBulb|Bulbo";
            string aUrethra = "Uretra|Urethra";
            string aPTV     = "PTV|PTV_EVAL|PTVtotal|PTV_7920|PTVprost|PTV High Risk|PTV Primary|PTV Low Risk|PTV Intermediate|PTV_High|PTVp|PTV_Low|PTV_Intermed|PTV_Intermediate";
            string aBrach   = "BrachialPlex|BrachialPlexus|BrachialPlex_L|BrachialPlex_R|Plexo_Braquial|Plexo Braquial Dir|Plexo Braquial Esq";
            string aEso = ALS_ESOFAGO;
            string aHeart   = ALS_HEART;
            string aLungs   = "Lungs|Lungs-GTV|Pulmões|Pulmoes|Pulmoes-GTV|Lungs_GTV|Lung-GTV|Lungs-iGTV";
            string aCanal   = "SpinalCanal|Canal_Medular|Medula|SpinalCord";
            string aGV      = "GreatVes|GreatVessels|Grandes_Vasos|GreatVessel|Grandes Vasos";
            string aTrach   = "Trachea|Bronchus_Main|Traqueia|Trach_Bronch";
            string aBronch  = "Bronchus|Brônquio|ProxBronchTree|Bronchial_Tree";
            string aCW      = "Chestwall|Parede_Toracica|Chest_Wall";
            string aRibs = ALS_COSTELAS;
            string aSkin = ALS_PELE;
            string aDuo = ALS_DUODENO;
            string aSto = ALS_ESTOMAGO;
            string aKid     = "Kidneys|Rins";
            string aLiver   = "Liver|Fígado|Liver_GTV|Liver-iGTV";

            // =============== PRÓSTATA ===============
            {   // Tabela 19 - convencional 74-81 Gy
                var t = NewAstro("Próstata", "Tab.19 Próstata convencional", "1.8-2 Gy/fx -> 74-81 Gy", new[]{37,39,40,41,42,44,45});
                t.Add("Bexiga","V75Gy",Dir.MAX,25,null,"%",null,aBladder);
                t.Add("Bexiga","V70Gy",Dir.MAX,35,null,"%",null,aBladder);
                t.Add("Bexiga","V50Gy",Dir.MAX,50,null,"%",null,aBladder);
                t.Add("Intestino grosso","D0.035cc",Dir.MAX,62.5,null,"Gy",null,aBowelL);
                t.Add("Intestino grosso","V60Gy",Dir.MAX,1,null,"%",null,aBowelL);
                t.Add("Intestino delgado","D0.035cc",Dir.MAX,52.5,54,"Gy",null,aBowelS);
                t.Add("Intestino delgado","V45Gy",Dir.MAX,150,200,"cc",null,aBowelS);
                t.Add("Femur D","V50Gy",Dir.MAX,10,null,"%",null,aFemurD);
                t.Add("Femur E","V50Gy",Dir.MAX,10,null,"%",null,aFemurE);
                t.Add("Bulbo peniano","Mean",Dir.MAX,52.5,null,"Gy","Não comprometer cobertura do PTV",aPenile);
                t.Add("Reto","V75Gy",Dir.MAX,10,15,"%",null,aRectum);
                t.Add("Reto","V70Gy",Dir.MAX,15,25,"%",null,aRectum);
                t.Add("Reto","V40Gy",Dir.MAX,40,65,"%",null,aRectum);
                t.Add("PTV","V100%",Dir.MIN,95,90,"%",null,aPTV);
                t.Add("PTV","D2%",Dir.MAX,110,115,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 20 - 20 fx / 60 Gy
                var t = NewAstro("Próstata", "Tab.20 Próstata 20 fx", "3 Gy/fx -> 60 Gy", new[]{20});
                t.Add("Bexiga","V60Gy",Dir.MAX,5,15,"%",null,aBladder);
                t.Add("Bexiga","V48Gy",Dir.MAX,25,null,"%",null,aBladder);
                t.Add("Bexiga","V40Gy",Dir.MAX,50,null,"%",null,aBladder);
                t.Add("Intestino grosso","D0.035cc",Dir.MAX,50,null,"Gy",null,aBowelL);
                t.Add("Intestino delgado","D0.035cc",Dir.MAX,50,null,"Gy",null,aBowelS);
                t.Add("Intestino delgado","V40Gy",Dir.MAX,17,195,"cc",null,aBowelS);
                t.Add("Femur D","V40Gy",Dir.MAX,5,50,"%",null,aFemurD);
                t.Add("Femur E","V40Gy",Dir.MAX,5,50,"%",null,aFemurE);
                t.Add("Bulbo peniano","V48Gy",Dir.MAX,10,null,"%","Não comprometer cobertura do PTV",aPenile);
                t.Add("Reto","V60Gy",Dir.MAX,0.01,8,"%",null,aRectum);
                t.Add("Reto","V50Gy",Dir.MAX,22,null,"%",null,aRectum);
                t.Add("Reto","V30Gy",Dir.MAX,57,null,"%",null,aRectum);
                t.Add("PTV","V100%",Dir.MIN,95,90,"%",null,aPTV);
                t.Add("PTV","D2%",Dir.MAX,110,115,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 21 - 28 fx / 70 Gy
                var t = NewAstro("Próstata", "Tab.21 Próstata 28 fx", "2.5 Gy/fx -> 70 Gy", new[]{28});
                t.Add("Bexiga","V70Gy",Dir.MAX,10,15,"%",null,aBladder);
                t.Add("Bexiga","V65Gy",Dir.MAX,15,25,"%",null,aBladder);
                t.Add("Bexiga","V40Gy",Dir.MAX,35,65,"%",null,aBladder);
                t.Add("Intestino grosso","D0.035cc",Dir.MAX,55,60,"Gy",null,aBowelL);
                t.Add("Intestino grosso","V50Gy",Dir.MAX,1,null,"%",null,aBowelL);
                t.Add("Intestino delgado","D0.035cc",Dir.MAX,52.5,54,"Gy",null,aBowelS);
                t.Add("Intestino delgado","V40Gy",Dir.MAX,1,null,"%",null,aBowelS);
                t.Add("Femur D","V40Gy",Dir.MAX,0,null,"%",null,aFemurD);
                t.Add("Femur E","V40Gy",Dir.MAX,0,null,"%",null,aFemurE);
                t.Add("Bulbo peniano","Mean",Dir.MAX,50,null,"Gy","Não comprometer cobertura do PTV",aPenile);
                t.Add("Reto","V70Gy",Dir.MAX,5,10,"%",null,aRectum);
                t.Add("Reto","V65Gy",Dir.MAX,10,null,"%",null,aRectum);
                t.Add("Reto","V40Gy",Dir.MAX,35,null,"%",null,aRectum);
                t.Add("PTV","V100%",Dir.MIN,95,90,"%",null,aPTV);
                t.Add("PTV","D2%",Dir.MAX,110,115,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 22 - pos-operatorio convencional 64-72 Gy
                var t = NewAstro("Próstata", "Tab.22 Próstata pos-op", "1.8-2 Gy/fx -> 64-72 Gy (leito)", new[]{33,34,35,36});
                t.Add("Bexiga","V65Gy",Dir.MAX,50,57.5,"%","Bladder-CTVp",aBladder);
                t.Add("Bexiga","V40Gy",Dir.MAX,70,77,"%",null,aBladder);
                t.Add("Intestino grosso","D0.035cc",Dir.MAX,62.5,null,"Gy",null,aBowelL);
                t.Add("Intestino grosso","V60Gy",Dir.MAX,1,null,"%",null,aBowelL);
                t.Add("Intestino delgado","V60Gy",Dir.MAX,0.1,null,"cc",null,aBowelS);
                t.Add("Intestino delgado","V45Gy",Dir.MAX,150,200,"cc",null,aBowelS);
                t.Add("Femur D","V50Gy",Dir.MAX,10,15,"%",null,aFemurD);
                t.Add("Femur E","V50Gy",Dir.MAX,10,15,"%",null,aFemurE);
                t.Add("Bulbo peniano","Mean",Dir.MAX,52.5,null,"Gy",null,aPenile);
                t.Add("Reto","V65Gy",Dir.MAX,35,45,"%",null,aRectum);
                t.Add("Reto","V40Gy",Dir.MAX,55,65,"%",null,aRectum);
                t.Add("PTV","V100%",Dir.MIN,95,90,"%","Leito prostático",aPTV);
                t.Add("PTV","D2%",Dir.MAX,110,115,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 23 - SBRT 5 fx / 36.25-40 Gy
                var t = NewAstro("Próstata", "Tab.23 Próstata SBRT 5 fx", "7.25-8 Gy/fx -> 36.25-40 Gy", new[]{5});
                t.Add("Bexiga","V37Gy",Dir.MAX,5,20,"cc",null,aBladder);
                t.Add("Bexiga","V18.1Gy",Dir.MAX,40,null,"%",null,aBladder);
                t.Add("Intestino grosso","D0.035cc",Dir.MAX,30,null,"Gy",null,aBowelL);
                t.Add("Intestino delgado","V30Gy",Dir.MAX,0.03,1,"cc",null,aBowelS);
                t.Add("Intestino delgado","V18.1Gy",Dir.MAX,5,null,"cc",null,aBowelS);
                t.Add("Femur D","V14.5Gy",Dir.MAX,5,null,"%",null,aFemurD);
                t.Add("Femur E","V14.5Gy",Dir.MAX,5,null,"%",null,aFemurE);
                t.Add("Bulbo peniano","D0.035cc",Dir.MAX,36.25,null,"Gy","Não comprometer cobertura do PTV",aPenile);
                t.Add("Bulbo peniano","V29.5Gy",Dir.MAX,50,null,"%",null,aPenile);
                t.Add("Reto","V36Gy",Dir.MAX,1,3,"cc",null,aRectum);
                t.Add("Reto","V29Gy",Dir.MAX,20,null,"%",null,aRectum);
                t.Add("Reto","V18.1Gy",Dir.MAX,50,null,"%",null,aRectum);
                t.Add("Uretra","V42Gy",Dir.MAX,50,null,"%",null,aUrethra);
                t.Add("PTV","V100%",Dir.MIN,95,null,"%",null,aPTV);
                t.Add("PTV","D0.035cc",Dir.MAX,120,null,"%","Robótico/ablativo",aPTV);
                t.Add("PTV","D0.035cc",Dir.MAX,107,null,"%","Linac",aPTV);
                L.Add(t);
            }

            // =============== PULMÃO ===============
            {   // Tabela 11 - convencional 60-70 Gy
                var t = NewAstro("Pulmão", "Tab.11 Pulmão convencional", "1.8-2 Gy/fx -> 60-70 Gy", new[]{30,33,35});
                t.Add("Plexo braquial","D0.035cc",Dir.MAX,66,70,"Gy",null,aBrach);
                t.Add("Esôfago","D0.035cc",Dir.MAX,74,null,"Gy",null,aEso);
                t.Add("Esôfago","V60Gy",Dir.MAX,15.3,17,"%",null,aEso);
                t.Add("Esôfago","Mean",Dir.MAX,30.6,34,"Gy",null,aEso);
                t.Add("Coração","V45Gy",Dir.MAX,35,40,"%",null,aHeart);
                t.Add("Pulmões","V20Gy",Dir.MAX,33,37,"%","Lungs-GTV/iGTV",aLungs);
                t.Add("Pulmões","V5Gy",Dir.MAX,60,70,"%",null,aLungs);
                t.Add("Pulmões","Mean",Dir.MAX,18,22,"Gy",null,aLungs);
                t.Add("Canal medular","D0.035cc",Dir.MAX,50.5,52,"Gy",null,aCanal);
                t.Add("PTV","D95%",Dir.MIN,100,95,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 12 - SBRT 1 fx 27-34 Gy
                var t = NewAstro("Pulmão", "Tab.12 Pulmão SBRT 1 fx", "27-34 Gy em 1 fx", new[]{1});
                t.Add("Plexo braquial","D0.035cc",Dir.MAX,16.4,null,"Gy",null,aBrach);
                t.Add("Brônquio","D0.035cc",Dir.MAX,20.2,null,"Gy",null,aBronch);
                t.Add("Brônquio","D0.5cc",Dir.MAX,17.4,null,"Gy",null,aBronch);
                t.Add("Parede torácica","D1cc",Dir.MAX,30.2,null,"Gy",null,aCW);
                t.Add("Parede torácica","D5cc",Dir.MAX,27.2,null,"Gy",null,aCW);
                t.Add("Esôfago","D0.035cc",Dir.MAX,15.4,null,"Gy",null,aEso);
                t.Add("Esôfago","D5cc",Dir.MAX,11.9,null,"Gy",null,aEso);
                t.Add("Grandes vasos","D0.035cc",Dir.MAX,37,null,"Gy",null,aGV);
                t.Add("Coração","D0.035cc",Dir.MAX,22,null,"Gy",null,aHeart);
                t.Add("Coração","D15cc",Dir.MAX,16,null,"Gy",null,aHeart);
                t.Add("Pulmões","V8Gy",Dir.MAX,37,null,"%","Lungs-GTV/iGTV",aLungs);
                t.Add("Costelas","D0.035cc",Dir.MAX,30,null,"Gy",null,aRibs);
                t.Add("Costelas","D1cc",Dir.MAX,22,null,"Gy",null,aRibs);
                t.Add("Pele","D0.035cc",Dir.MAX,26,null,"Gy",null,aSkin);
                t.Add("Pele","D10cc",Dir.MAX,23,null,"Gy",null,aSkin);
                t.Add("Canal medular","D0.035cc",Dir.MAX,12.4,14,"Gy",null,aCanal);
                t.Add("Traqueia","D0.035cc",Dir.MAX,20.2,null,"Gy",null,aTrach);
                t.Add("Traqueia","D4cc",Dir.MAX,10.5,null,"Gy",null,aTrach);
                t.Add("PTV","D95%",Dir.MIN,100,99,"%","Lesões periféricas",aPTV);
                t.Add("PTV","D99%",Dir.MIN,90,85,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 13 - SBRT 3 fx 54 Gy
                var t = NewAstro("Pulmão", "Tab.13 Pulmão SBRT 3 fx", "18 Gy/fx -> 54 Gy", new[]{3});
                t.Add("Plexo braquial","D0.035cc",Dir.MAX,24,null,"Gy",null,aBrach);
                t.Add("Brônquio","D0.035cc",Dir.MAX,30,null,"Gy",null,aBronch);
                t.Add("Brônquio","D0.5cc",Dir.MAX,25.8,null,"Gy",null,aBronch);
                t.Add("Parede torácica","D0.035cc",Dir.MAX,50,null,"Gy",null,aCW);
                t.Add("Parede torácica","V30Gy",Dir.MAX,30,35,"cc",null,aCW);
                t.Add("Esôfago","D0.035cc",Dir.MAX,27,null,"Gy",null,aEso);
                t.Add("Esôfago","D5cc",Dir.MAX,17.7,null,"Gy",null,aEso);
                t.Add("Grandes vasos","D0.035cc",Dir.MAX,45,null,"Gy",null,aGV);
                t.Add("Coração","D0.035cc",Dir.MAX,30,null,"Gy",null,aHeart);
                t.Add("Coração","D15cc",Dir.MAX,24,null,"Gy",null,aHeart);
                t.Add("Pulmões","V20Gy",Dir.MAX,10,15,"%","Lungs-GTV/iGTV",aLungs);
                t.Add("Pulmões","CV11.6Gy",Dir.MIN,1500,null,"cc","volume frio",aLungs);
                t.Add("Pulmões","CV12.4Gy",Dir.MIN,1000,null,"cc","volume frio",aLungs);
                t.Add("Pulmões","Mean",Dir.MAX,8,null,"Gy",null,aLungs);
                t.Add("Costelas","D0.035cc",Dir.MAX,50,null,"Gy",null,aRibs);
                t.Add("Costelas","D5cc",Dir.MAX,40,null,"Gy",null,aRibs);
                t.Add("Pele","D0.035cc",Dir.MAX,33,null,"Gy",null,aSkin);
                t.Add("Pele","D10cc",Dir.MAX,31,null,"Gy",null,aSkin);
                t.Add("Canal medular","D0.035cc",Dir.MAX,20.3,null,"Gy",null,aCanal);
                t.Add("Traqueia","D0.035cc",Dir.MAX,30,null,"Gy",null,aTrach);
                t.Add("Traqueia","D4cc",Dir.MAX,15,null,"Gy",null,aTrach);
                t.Add("PTV","D95%",Dir.MIN,100,99,"%","Lesões periféricas",aPTV);
                t.Add("PTV","D99%",Dir.MIN,90,85,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 14 - SBRT 4 fx 48-50 Gy
                var t = NewAstro("Pulmão", "Tab.14 Pulmão SBRT 4 fx", "12-12.5 Gy/fx -> 48-50 Gy", new[]{4});
                t.Add("Plexo braquial","D0.035cc",Dir.MAX,27.2,null,"Gy",null,aBrach);
                t.Add("Brônquio","D0.035cc",Dir.MAX,34.8,null,"Gy",null,aBronch);
                t.Add("Brônquio","D0.5cc",Dir.MAX,28.8,null,"Gy",null,aBronch);
                t.Add("Parede torácica","D0.035cc",Dir.MAX,50,54,"Gy",null,aCW);
                t.Add("Parede torácica","V30Gy",Dir.MAX,30,35,"cc",null,aCW);
                t.Add("Esôfago","D0.035cc",Dir.MAX,30,null,"Gy",null,aEso);
                t.Add("Esôfago","D5cc",Dir.MAX,18.8,null,"Gy",null,aEso);
                t.Add("Grandes vasos","D0.035cc",Dir.MAX,43,49,"Gy",null,aGV);
                t.Add("Coração","D0.035cc",Dir.MAX,34,null,"Gy",null,aHeart);
                t.Add("Coração","D15cc",Dir.MAX,28,null,"Gy",null,aHeart);
                t.Add("Pulmões","V20Gy",Dir.MAX,10,15,"%","Lungs-GTV/iGTV",aLungs);
                t.Add("Pulmões","Mean",Dir.MAX,8,null,"Gy",null,aLungs);
                t.Add("Costelas","D0.035cc",Dir.MAX,40,null,"Gy",null,aRibs);
                t.Add("Costelas","D1cc",Dir.MAX,32,null,"Gy",null,aRibs);
                t.Add("Pele","D0.035cc",Dir.MAX,36,null,"Gy",null,aSkin);
                t.Add("Pele","D10cc",Dir.MAX,33.2,null,"Gy",null,aSkin);
                t.Add("Canal medular","D0.035cc",Dir.MAX,24,null,"Gy",null,aCanal);
                t.Add("Traqueia","D0.035cc",Dir.MAX,34.8,null,"Gy",null,aTrach);
                t.Add("Traqueia","D4cc",Dir.MAX,15.6,null,"Gy",null,aTrach);
                t.Add("PTV","D95%",Dir.MIN,100,99,"%","Lesões periféricas/centrais",aPTV);
                t.Add("PTV","D99%",Dir.MIN,90,85,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 15 - SBRT 5 fx 50-60 Gy
                var t = NewAstro("Pulmão", "Tab.15 Pulmão SBRT 5 fx", "10-12 Gy/fx -> 50-60 Gy", new[]{5});
                t.Add("Plexo braquial","D0.035cc",Dir.MAX,32,null,"Gy",null,aBrach);
                t.Add("Brônquio","D0.035cc",Dir.MAX,40,null,"Gy",null,aBronch);
                t.Add("Brônquio","D0.5cc",Dir.MAX,21,null,"Gy",null,aBronch);
                t.Add("Parede torácica","D0.035cc",Dir.MAX,50,57,"Gy",null,aCW);
                t.Add("Parede torácica","V30Gy",Dir.MAX,30,70,"cc",null,aCW);
                t.Add("Esôfago","D0.035cc",Dir.MAX,38,null,"Gy",null,aEso);
                t.Add("Esôfago","D5cc",Dir.MAX,19.5,null,"Gy",null,aEso);
                t.Add("Grandes vasos","D0.035cc",Dir.MAX,105,null,"%",null,aGV);
                t.Add("Coração","D0.035cc",Dir.MAX,38,null,"Gy",null,aHeart);
                t.Add("Coração","D15cc",Dir.MAX,32,null,"Gy",null,aHeart);
                t.Add("Pulmões","V20Gy",Dir.MAX,10,15,"%","Lungs-GTV/iGTV",aLungs);
                t.Add("Pulmões","CV12.5Gy",Dir.MIN,1500,null,"cc","volume frio",aLungs);
                t.Add("Pulmões","CV13.5Gy",Dir.MIN,1000,null,"cc","volume frio",aLungs);
                t.Add("Pulmões","Mean",Dir.MAX,8,null,"Gy",null,aLungs);
                t.Add("Costelas","D0.035cc",Dir.MAX,43,null,"Gy",null,aRibs);
                t.Add("Costelas","D1cc",Dir.MAX,35,null,"Gy",null,aRibs);
                t.Add("Pele","D0.035cc",Dir.MAX,32,null,"Gy",null,aSkin);
                t.Add("Pele","D10cc",Dir.MAX,30,null,"Gy",null,aSkin);
                t.Add("Canal medular","D0.035cc",Dir.MAX,28,null,"Gy",null,aCanal);
                t.Add("Traqueia","D0.035cc",Dir.MAX,40,null,"Gy",null,aTrach);
                t.Add("Traqueia","D4cc",Dir.MAX,18,null,"Gy",null,aTrach);
                t.Add("PTV","D95%",Dir.MIN,100,99,"%","Lesões periféricas/centrais",aPTV);
                t.Add("PTV","D99%",Dir.MIN,90,85,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 16 - 8 fx 60 Gy
                var t = NewAstro("Pulmão", "Tab.16 Pulmão 8 fx", "7.5 Gy/fx -> 60 Gy", new[]{8});
                t.Add("Plexo braquial","D0.035cc",Dir.MAX,38,null,"Gy",null,aBrach);
                t.Add("Parede torácica","D0.035cc",Dir.MAX,63,null,"Gy",null,aCW);
                t.Add("Parede torácica","V45Gy",Dir.MAX,30,null,"cc",null,aCW);
                t.Add("Esôfago","D0.035cc",Dir.MAX,40,52.5,"Gy",null,aEso);
                t.Add("Esôfago","D5cc",Dir.MAX,22,null,"Gy",null,aEso);
                t.Add("Grandes vasos","D0.035cc",Dir.MAX,62,null,"Gy",null,aGV);
                t.Add("Coração","D0.035cc",Dir.MAX,46,60,"Gy",null,aHeart);
                t.Add("Coração","D15cc",Dir.MAX,34.4,null,"Gy",null,aHeart);
                t.Add("Pulmões","V26Gy",Dir.MAX,10,null,"%","Lungs-GTV/iGTV",aLungs);
                t.Add("Pulmões","Mean",Dir.MAX,10,null,"Gy",null,aLungs);
                t.Add("Costelas","D0.035cc",Dir.MAX,63,null,"Gy",null,aRibs);
                t.Add("Costelas","D5cc",Dir.MAX,50,null,"Gy",null,aRibs);
                t.Add("Canal medular","D0.035cc",Dir.MAX,32,null,"Gy",null,aCanal);
                t.Add("Traqueia","D0.035cc",Dir.MAX,46.3,56,"Gy",null,aTrach);
                t.Add("Traqueia","D5cc",Dir.MAX,50,null,"Gy",null,aTrach);
                t.Add("PTV","D95%",Dir.MIN,100,99,"%",null,aPTV);
                t.Add("PTV","D99%",Dir.MIN,90,85,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 17 - 10 fx 70 Gy
                var t = NewAstro("Pulmão", "Tab.17 Pulmão 10 fx", "7 Gy/fx -> 70 Gy", new[]{10});
                t.Add("Plexo braquial","D0.035cc",Dir.MAX,43,null,"Gy",null,aBrach);
                t.Add("Parede torácica","V50Gy",Dir.MAX,60,null,"cc",null,aCW);
                t.Add("Esôfago","D0.035cc",Dir.MAX,48,52.5,"Gy",null,aEso);
                t.Add("Esôfago","D5cc",Dir.MAX,24,null,"Gy",null,aEso);
                t.Add("Grandes vasos","D0.035cc",Dir.MAX,62.9,null,"Gy",null,aGV);
                t.Add("Grandes vasos","D10cc",Dir.MAX,55.7,null,"Gy",null,aGV);
                t.Add("Coração","D0.035cc",Dir.MAX,42.5,60,"Gy",null,aHeart);
                t.Add("Coração","D15cc",Dir.MAX,36.6,null,"Gy",null,aHeart);
                t.Add("Pulmões","V16Gy",Dir.MAX,30,32,"%","Lungs-GTV/iGTV",aLungs);
                t.Add("Pulmões","Mean",Dir.MAX,12,null,"Gy",null,aLungs);
                t.Add("Canal medular","D0.035cc",Dir.MAX,33.3,36,"Gy",null,aCanal);
                t.Add("Traqueia","D0.035cc",Dir.MAX,59,null,"Gy",null,aTrach);
                t.Add("Traqueia","D5cc",Dir.MAX,52,null,"Gy",null,aTrach);
                t.Add("PTV","D95%",Dir.MIN,100,99,"%",null,aPTV);
                t.Add("PTV","D99%",Dir.MIN,90,85,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 18 - 15 fx 60 Gy
                var t = NewAstro("Pulmão", "Tab.18 Pulmão 15 fx", "4 Gy/fx -> 60 Gy", new[]{15});
                t.Add("Plexo braquial","D0.035cc",Dir.MAX,49.8,52,"Gy",null,aBrach);
                t.Add("Parede torácica","V40Gy",Dir.MAX,150,null,"cc",null,aCW);
                t.Add("Esôfago","D0.035cc",Dir.MAX,58.9,61.3,"Gy",null,aEso);
                t.Add("Esôfago","Mean",Dir.MAX,25,32,"Gy",null,aEso);
                t.Add("Grandes vasos","D0.035cc",Dir.MAX,60,66,"Gy",null,aGV);
                t.Add("Coração","D0.035cc",Dir.MAX,60,66,"Gy",null,aHeart);
                t.Add("Coração","Mean",Dir.MAX,16.5,18.5,"Gy",null,aHeart);
                t.Add("Pulmões","V16.5Gy",Dir.MAX,37,40,"%","Lungs-GTV/iGTV",aLungs);
                t.Add("Pulmões","V5Gy",Dir.MAX,65,70,"%",null,aLungs);
                t.Add("Pulmões","Mean",Dir.MAX,16.5,18.5,"Gy",null,aLungs);
                t.Add("Canal medular","D0.035cc",Dir.MAX,36.5,40.2,"Gy",null,aCanal);
                t.Add("Traqueia","D0.035cc",Dir.MAX,60,66,"Gy",null,aTrach);
                t.Add("PTV","D95%",Dir.MIN,100,null,"%",null,aPTV);
                t.Add("PTV","D0.035cc",Dir.MAX,110,115,"%",null,aPTV);
                L.Add(t);
            }

            // =============== FÍGADO ===============
            {   // Tabela 8 - SBRT 3 fx 36-60 Gy
                var t = NewAstro("Fígado", "Tab.8 Fígado SBRT 3 fx", "12-20 Gy/fx -> 36-60 Gy", new[]{3});
                t.Add("Intestino grosso","D0.035cc",Dir.MAX,28,null,"Gy",null,aBowelL);
                t.Add("Intestino grosso","D20cc",Dir.MAX,24,null,"Gy",null,aBowelL);
                t.Add("Intestino delgado","D0.035cc",Dir.MAX,25,null,"Gy",null,aBowelS);
                t.Add("Intestino delgado","D5cc",Dir.MAX,18,null,"Gy",null,aBowelS);
                t.Add("Parede torácica","D0.035cc",Dir.MAX,50,null,"Gy",null,aCW);
                t.Add("Parede torácica","D5cc",Dir.MAX,40,null,"Gy",null,aCW);
                t.Add("Parede torácica","D30cc",Dir.MAX,30,null,"Gy",null,aCW);
                t.Add("Duodeno","D0.035cc",Dir.MAX,22,null,"Gy",null,aDuo);
                t.Add("Duodeno","D5cc",Dir.MAX,16.5,null,"Gy",null,aDuo);
                t.Add("Esôfago","D0.035cc",Dir.MAX,27,null,"Gy",null,aEso);
                t.Add("Coração","D0.035cc",Dir.MAX,30,null,"Gy",null,aHeart);
                t.Add("Coração","D15cc",Dir.MAX,24,null,"Gy",null,aHeart);
                t.Add("Rins","Mean",Dir.MAX,8,null,"Gy",null,aKid);
                t.Add("Fígado","CV19Gy",Dir.MIN,700,null,"cc","Liver-GTV (não-cirrótico)",aLiver);
                t.Add("Fígado","Mean",Dir.MAX,12,15,"Gy","Liver-GTV não-cirrótico (CP-A: <=10/12)",aLiver);
                t.Add("Canal medular","D0.035cc",Dir.MAX,22.5,null,"Gy",null,aCanal);
                t.Add("Estômago","D0.035cc",Dir.MAX,22,null,"Gy",null,aSto);
                t.Add("Estômago","D10cc",Dir.MAX,16.5,null,"Gy",null,aSto);
                t.Add("PTV","V100%",Dir.MIN,95,null,"%","OAR tem prioridade se próximo",aPTV);
                t.Add("PTV","V90%",Dir.MIN,100,null,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 9 - SBRT 5 fx 40-60 Gy
                var t = NewAstro("Fígado", "Tab.9 Fígado SBRT 5 fx", "8-12 Gy/fx -> 40-60 Gy", new[]{5});
                t.Add("Intestino grosso","D0.5cc",Dir.MAX,32,34,"Gy",null,aBowelL);
                t.Add("Intestino delgado","D0.5cc",Dir.MAX,30,null,"Gy",null,aBowelS);
                t.Add("Intestino delgado","D5cc",Dir.MAX,25,null,"Gy",null,aBowelS);
                t.Add("Parede torácica","D0.035cc",Dir.MAX,57,null,"Gy",null,aCW);
                t.Add("Parede torácica","V30Gy",Dir.MAX,30,70,"cc",null,aCW);
                t.Add("Duodeno","D0.5cc",Dir.MAX,30,null,"Gy",null,aDuo);
                t.Add("Duodeno","D5cc",Dir.MAX,25,null,"Gy",null,aDuo);
                t.Add("Esôfago","D0.5cc",Dir.MAX,32,null,"Gy",null,aEso);
                t.Add("Coração","D0.035cc",Dir.MAX,52.5,null,"Gy",null,aHeart);
                t.Add("Coração","D30cc",Dir.MAX,30,null,"Gy",null,aHeart);
                t.Add("Rins","Mean",Dir.MAX,10,null,"Gy","Se 1 rim Mean>10, outro V10Gy<10%",aKid);
                t.Add("Fígado","CV21Gy",Dir.MIN,700,null,"cc","Liver-GTV (não-cirrótico)",aLiver);
                t.Add("Fígado","Mean",Dir.MAX,15,18,"Gy","Liver-GTV não-cirrótico (CP-A: <=13/15)",aLiver);
                t.Add("Canal medular","D0.5cc",Dir.MAX,25,null,"Gy",null,aCanal);
                t.Add("Estômago","D0.5cc",Dir.MAX,30,null,"Gy",null,aSto);
                t.Add("Estômago","D5cc",Dir.MAX,25,null,"Gy",null,aSto);
                t.Add("PTV","V100%",Dir.MIN,95,null,"%","OAR tem prioridade se próximo",aPTV);
                t.Add("PTV","V90%",Dir.MIN,100,null,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 10 - 15 fx 45-67.5 Gy
                var t = NewAstro("Fígado", "Tab.10 Fígado 15 fx", "3-4.5 Gy/fx -> 45-67.5 Gy", new[]{15});
                t.Add("Intestino grosso","D0.035cc",Dir.MAX,45,null,"Gy",null,aBowelL);
                t.Add("Intestino delgado","D0.035cc",Dir.MAX,45,null,"Gy",null,aBowelS);
                t.Add("Parede torácica","D10cc",Dir.MAX,60,null,"Gy",null,aCW);
                t.Add("Parede torácica","D20cc",Dir.MAX,45,null,"Gy",null,aCW);
                t.Add("Parede torácica","D150cc",Dir.MAX,40,null,"Gy",null,aCW);
                t.Add("Duodeno","D0.035cc",Dir.MAX,45,null,"Gy",null,aDuo);
                t.Add("Esôfago","D0.5cc",Dir.MAX,40,45,"Gy",null,aEso);
                t.Add("Coração","D30cc",Dir.MAX,45,null,"Gy","conv. EQD2 de 8Gyx5, a/b=3",aHeart);
                t.Add("Rins","V18Gy",Dir.MAX,30,32,"%",null,aKid);
                t.Add("Fígado","Mean",Dir.MAX,24,null,"Gy","Liver-GTV não-cirrótico (CP-A:<=20 / CP-B:<=16)",aLiver);
                t.Add("Canal medular","D0.5cc",Dir.MAX,30,35,"Gy",null,aCanal);
                t.Add("Estômago","D0.035cc",Dir.MAX,42,45,"Gy",null,aSto);
                t.Add("PTV","V100%",Dir.MIN,95,null,"%","OAR tem prioridade se próximo",aPTV);
                t.Add("PTV","V90%",Dir.MIN,100,null,"%",null,aPTV);
                L.Add(t);
            }

            // aliases adicionais (Mama / C&P / Reto)
            string aBreastCL = "Breast_Contralateral|Mama_Contralateral|Mama_CL|Mama_Contra|Breast_CL|Female Breast Left|Female Breast Right";
            string aLungIL   = "Lung_Ipsilateral|Pulmao_Ipsi|Pulmao_IL|Lung_IL|Pulmao_Ipsilateral|Pulmao D|Pulmao E";
            string aLungCL   = "Lung_Contralateral|Pulmao_Contra|Pulmao_CL|Lung_CL|Pulmao_Contralateral|Pulmao D|Pulmao E";
            string aSpCord   = "SpinalCord|Medula|SpinalCanal|Medula_Espinhal";
            string aBreastCW = "Breast_CW|Mama|PTV_Mama|PTV Mama|PTV Mama D|PTV Mama E|PTV_Mama_D|PTV_Mama_E|CTV_Mama|Breast|ChestWall|Parede_Toracica|PTV|Female Breast Left|Female Breast Right|PTV High Risk|PTV Primary|PTVp|PTV_High";
            string aSclav    = "LN_Sclav|LN_Supraclav|Fossa_SC|Supraclavicular";
            string aAx       = "LN_Ax|LN_Axila|Axila|Axilla";
            string aIMN      = "LN_IMN|LN_CMI|Cadeia_Mamaria_Interna|IMN|Mamaria_Interna";
            string aMand     = "Bone_Mandible|Mandibula|Mandible";
            string aBstem    = "Brainstem|Tronco|BrainStem|Tronco_Cerebral|Tronco Cerebral";
            string aOral     = "Cavity_Oral|Cavidade_Oral|Oral_Cavity";
            string aCochlea2 = "Cochlea_L|Cochlea_R|Coclea|Cochlea|Coclea D|Coclea E";
            string aSubmand  = "Glnd_Submand_L|Glnd_Submand_R|Submandibular|Glandula_Submandibular|Glnd_Submand|Submandibular D|Submandibular E";
            string aLarynx2  = "Larynx|Laringe";
            string aConstr   = "Musc_Constrict|Constritores|Musculos_Constritores|Constrictor";
            string aParot    = "Parotid_L|Parotid_R|Parotida|Parotid|Parotida D|Parotida E";
            string aCarot    = "A_Carotid|A_Carotid_L|A_Carotid_R|Carotida|A_Carotida|Carotid|Carotid Artery";
            string aPTVhi    = "PTV_high|PTV_High|PTV_HighRisk|PTV_alto|PTV_70|PTV High Risk|PTV_High";
            string aPTVlo    = "PTV_low|PTV_Low|PTV_LowRisk|PTV_baixo|PTV_56|PTV_54|PTV Low Risk|PTV_Low";
            string aVagina   = "Vagina|Canal_Vaginal";
            string aGenit    = "Genitals|Genitalia|Genitais";

            // ============================ MAMA ============================
            {   // Tabela 1 - Mama/parede com linfonodos, convencional 50-50.4 Gy
                var t = NewAstro("Mama", "Tab.1 Mama c/ linfonodos (convencional)", "1.8-2 Gy/fx -> 50-50.4 Gy", new[]{25,28});
                t.Add("Mama contralateral","D10%",Dir.MAX,3,5,"Gy",null,aBreastCL);
                t.Add("Coração","Mean",Dir.MAX,4,5,"Gy","mama esquerda",aHeart);
                t.Add("Coração","Mean",Dir.MAX,2,3,"Gy","mama direita",aHeart);
                t.Add("Pulmão contralateral","V5Gy",Dir.MAX,15,null,"%",null,aLungCL);
                t.Add("Pulmão ipsilateral","V20Gy",Dir.MAX,35,40,"%",null,aLungIL);
                t.Add("Pulmão ipsilateral","V10Gy",Dir.MAX,65,null,"%",null,aLungIL);
                t.Add("Medula espinhal","D0.035cc",Dir.MAX,45,50,"Gy",null,aSpCord);
                t.Add("PTV","V95%",Dir.MIN,95,90,"%","alvo mama/parede",aBreastCW);
                t.Add("PTV","D0.035cc",Dir.MAX,110,115,"%",null,aBreastCW);
                t.Add("Linfonodos supraclav.","V95%",Dir.MIN,95,90,"%",null,aSclav);
                t.Add("Linfonodos supraclav.","D0.035cc",Dir.MAX,110,115,"%",null,aSclav);
                t.Add("Linfonodos axilares","V95%",Dir.MIN,95,90,"%",null,aAx);
                t.Add("Linfonodos axilares","D0.035cc",Dir.MAX,110,115,"%",null,aAx);
                t.Add("Linfonodos mamária int.","V90%",Dir.MIN,95,80,"%",null,aIMN);
                t.Add("Linfonodos mamária int.","D0.035cc",Dir.MAX,110,115,"%",null,aIMN);
                L.Add(t);
            }
            {   // Tabela 2 - Mama/parede SEM linfonodos, hipofx moderado 15-16 fx
                var t = NewAstro("Mama", "Tab.2 Mama s/ linfonodos (hipofx 15-16 fx)", "2.66-2.67 Gy/fx -> 40.05-42.56 Gy", new[]{15,16});
                t.Add("Mama contralateral","D5%",Dir.MAX,1.44,2.4,"Gy",null,aBreastCL);
                t.Add("Coração","Mean",Dir.MAX,1.6,2.4,"Gy","mama esquerda",aHeart);
                t.Add("Coração","Mean",Dir.MAX,0.8,1.6,"Gy","mama direita",aHeart);
                t.Add("Pulmão contralateral","V4Gy",Dir.MAX,10,15,"%",null,aLungCL);
                t.Add("Pulmão ipsilateral","V16Gy",Dir.MAX,15,20,"%",null,aLungIL);
                t.Add("PTV","V95%",Dir.MIN,95,90,"%","alvo mama/parede",aBreastCW);
                t.Add("PTV","D0.035cc",Dir.MAX,110,115,"%",null,aBreastCW);
                t.Add("PTV","V107%",Dir.MAX,10,null,"cc",null,aBreastCW);
                L.Add(t);
            }
            {   // Tabela 3 - Mama/parede COM linfonodos, hipofx moderado 15-16 fx
                var t = NewAstro("Mama", "Tab.3 Mama c/ linfonodos (hipofx 15-16 fx)", "2.66-2.67 Gy/fx -> 40.05-42.56 Gy", new[]{15,16});
                t.Add("Mama contralateral","D10%",Dir.MAX,3,5,"Gy",null,aBreastCL);
                t.Add("Coração","Mean",Dir.MAX,3,5,"Gy","mama esquerda",aHeart);
                t.Add("Coração","Mean",Dir.MAX,1.6,2.4,"Gy","mama direita",aHeart);
                t.Add("Pulmão contralateral","V4.3Gy",Dir.MAX,15,null,"%",null,aLungCL);
                t.Add("Pulmão ipsilateral","V18Gy",Dir.MAX,35,40,"%",null,aLungIL);
                t.Add("Pulmão ipsilateral","V10Gy",Dir.MAX,60,null,"%",null,aLungIL);
                t.Add("Medula espinhal","D0.035cc",Dir.MAX,37.8,42,"Gy",null,aSpCord);
                t.Add("PTV","V95%",Dir.MIN,95,90,"%","alvo mama/parede",aBreastCW);
                t.Add("PTV","D0.035cc",Dir.MAX,110,115,"%",null,aBreastCW);
                t.Add("PTV","V107%",Dir.MAX,10,null,"cc",null,aBreastCW);
                t.Add("Linfonodos supraclav.","V95%",Dir.MIN,95,90,"%",null,aSclav);
                t.Add("Linfonodos supraclav.","D0.035cc",Dir.MAX,110,115,"%",null,aSclav);
                t.Add("Linfonodos axilares","V95%",Dir.MIN,95,90,"%",null,aAx);
                t.Add("Linfonodos axilares","D0.035cc",Dir.MAX,110,115,"%",null,aAx);
                t.Add("Linfonodos mamária int.","V90%",Dir.MIN,90,80,"%",null,aIMN);
                t.Add("Linfonodos mamária int.","D0.035cc",Dir.MAX,110,115,"%",null,aIMN);
                L.Add(t);
            }
            {   // Tabela 4 - Mama parcial, ultra-hipofx 5 fx (6 Gy -> 30 Gy)
                var t = NewAstro("Mama", "Tab.4 Mama parcial (5 fx)", "6 Gy/fx -> 30 Gy", new[]{5});
                t.Add("Mama contralateral","D0.035cc",Dir.MAX,3,5,"%","contralateral",aBreastCL);
                t.Add("Mama contralateral","V50%",Dir.MAX,50,60,"%","ipsilateral",aBreastCL);
                t.Add("Mama contralateral","V95%",Dir.MAX,25,40,"%","ipsilateral",aBreastCL);
                t.Add("Coração","V15%",Dir.MAX,5,10,"%","mama esquerda",aHeart);
                t.Add("Coração","Mean",Dir.MAX,1.5,2,"Gy","mama esquerda",aHeart);
                t.Add("Coração","V5%",Dir.MAX,5,10,"%","mama direita",aHeart);
                t.Add("Coração","Mean",Dir.MAX,0.7,1,"Gy","mama direita",aHeart);
                t.Add("Pulmão contralateral","V10%",Dir.MAX,5,15,"%",null,aLungCL);
                t.Add("Pulmão ipsilateral","V30%",Dir.MAX,10,15,"%",null,aLungIL);
                t.Add("PTV","V95%",Dir.MIN,95,90,"%","PTV mama parcial",aPTV);
                t.Add("PTV","V105%",Dir.MAX,5,7,"%",null,aPTV);
                t.Add("PTV","D0.035cc",Dir.MAX,110,null,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 5 - Mama inteira/parede, ultra-hipofx 5 fx (5.2 Gy -> 26 Gy)
                var t = NewAstro("Mama", "Tab.5 Mama inteira/parede (5 fx)", "5.2 Gy/fx -> 26 Gy", new[]{5});
                t.Add("Coração","V1.5Gy",Dir.MAX,30,null,"%",null,aHeart);
                t.Add("Coração","V7Gy",Dir.MAX,5,null,"%",null,aHeart);
                t.Add("Pulmão ipsilateral","V8Gy",Dir.MAX,15,null,"%",null,aLungIL);
                t.Add("PTV","V95%",Dir.MIN,95,null,"%","alvo mama/parede",aBreastCW);
                t.Add("PTV","V105%",Dir.MAX,5,null,"%",null,aBreastCW);
                t.Add("PTV","V107%",Dir.MAX,2,null,"%",null,aBreastCW);
                t.Add("PTV","D0.035cc",Dir.MAX,110,null,"%",null,aBreastCW);
                L.Add(t);
            }

            // ==================== CABEÇA E PESCOÇO ====================
            {   // Tabela 6 - C&P (exceto laringe inicial), convencional 70 Gy
                var t = NewAstro("Cabeça e Pescoço", "Tab.6 C&P convencional", "2.0-2.12 Gy/fx -> 70 Gy", new[]{33,35});
                t.Add("Mandíbula","D0.035cc",Dir.MAX,70,73.5,"Gy",null,aMand);
                t.Add("Plexo braquial","D0.035cc",Dir.MAX,66,72,"Gy",null,aBrach);
                t.Add("Tronco cerebral","D0.035cc",Dir.MAX,50,52,"Gy",null,aBstem);
                t.Add("Cavidade oral","D0.035cc",Dir.MAX,60,null,"Gy","exceto casos de cav. oral",aOral);
                t.Add("Cavidade oral","Mean",Dir.MAX,30,null,"Gy","pescoço bilateral",aOral);
                t.Add("Cavidade oral","Mean",Dir.MAX,20,null,"Gy","pescoço unilateral",aOral);
                t.Add("Cóclea","D0.035cc",Dir.MAX,35,null,"Gy","orofaringe",aCochlea2);
                t.Add("Esôfago","Mean",Dir.MAX,45,null,"Gy","laringe",aEso);
                t.Add("Esôfago","Mean",Dir.MAX,35,null,"Gy","orofaringe",aEso);
                t.Add("Gl. submandibular","Mean",Dir.MAX,39,null,"Gy","contralateral, pescoço bilateral",aSubmand);
                t.Add("Gl. submandibular","Mean",Dir.MAX,10,null,"Gy","pescoço unilateral",aSubmand);
                t.Add("Laringe","Mean",Dir.MAX,35,null,"Gy","orofaringe",aLarynx2);
                t.Add("M. constritores","Mean",Dir.MAX,50,60,"Gy","Musc_Constrict - CTV",aConstr);
                t.Add("Parótida","Mean",Dir.MAX,26,null,"Gy","contralateral, pescoço bilateral",aParot);
                t.Add("Parótida","Mean",Dir.MAX,7,null,"Gy","pescoço unilateral",aParot);
                t.Add("Medula espinhal","D0.035cc",Dir.MAX,45,50,"Gy",null,aSpCord);
                t.Add("PTV alto risco","D95%",Dir.MIN,100,95,"%","alto risco",aPTVhi);
                t.Add("PTV alto risco","D99%",Dir.MIN,95,90,"%",null,aPTVhi);
                t.Add("PTV alto risco","D0.035cc",Dir.MAX,108,112,"%",null,aPTVhi);
                t.Add("PTV baixo risco","D95%",Dir.MIN,100,95,"%","baixo risco",aPTVlo);
                t.Add("PTV baixo risco","D99%",Dir.MIN,95,90,"%",null,aPTVlo);
                L.Add(t);
            }
            {   // Tabela 7 - C&P laringe inicial (T1/T2 glotico) poupando carotida, 28-29 fx
                var t = NewAstro("Cabeça e Pescoço", "Tab.7 Laringe inicial (poupa carotida)", "2.25 Gy/fx -> 63-65.25 Gy", new[]{28,29});
                t.Add("A. carótida","D2%",Dir.MAX,35,null,"Gy","todo comprimento do PTV",aCarot);
                t.Add("A. carótida","Mean",Dir.MAX,20,50,"Gy",null,aCarot);
                t.Add("Esôfago","D0.035cc",Dir.MAX,100,null,"%",null,aEso);
                t.Add("Gl. submandibular","Mean",Dir.MAX,15,null,"Gy",null,aSubmand);
                t.Add("M. constritores","D0.035cc",Dir.MAX,100,null,"%","Musc_Constrict - CTV",aConstr);
                t.Add("Medula espinhal","D0.035cc",Dir.MAX,20,45,"Gy",null,aSpCord);
                t.Add("PTV","D95%",Dir.MIN,100,95,"%",null,aPTV);
                t.Add("PTV","D99%",Dir.MIN,95,90,"%",null,aPTV);
                t.Add("PTV","D0.035cc",Dir.MAX,108,110,"%",null,aPTV);
                L.Add(t);
            }

            // ============================ RETO ============================
            {   // Tabela 24 - Reto convencional 50-56 Gy
                var t = NewAstro("Reto", "Tab.24 Reto convencional", "1.8-2 Gy/fx -> 50-56 Gy", new[]{25,28});
                t.Add("Bexiga","V45Gy",Dir.MAX,15,30,"%",null,aBladder);
                t.Add("Bexiga","Mean",Dir.MAX,40,44,"Gy",null,aBladder);
                t.Add("Intestino delgado","D0.035cc",Dir.MAX,56,60,"Gy","saco intestinal (Bag)",aBowelS);
                t.Add("Intestino delgado","D100cc",Dir.MAX,45,49.5,"Gy","saco intestinal (Bag)",aBowelS);
                t.Add("Intestino delgado","D180cc",Dir.MAX,35,38.5,"Gy","saco intestinal (Bag)",aBowelS);
                t.Add("Intestino delgado","V50Gy",Dir.MAX,30,null,"cc","alças individuais",aBowelS);
                t.Add("Intestino delgado","V45Gy",Dir.MAX,150,null,"cc","alças individuais",aBowelS);
                t.Add("Femur D","D5%",Dir.MAX,45,49.5,"Gy",null,aFemurD);
                t.Add("Femur E","D5%",Dir.MAX,45,49.5,"Gy",null,aFemurE);
                t.Add("Femur D","D50%",Dir.MAX,30,33,"Gy",null,aFemurD);
                t.Add("Femur E","D50%",Dir.MAX,30,33,"Gy",null,aFemurE);
                t.Add("Genitália","V40Gy",Dir.MAX,5,10,"%","vulva ou testículo/pênis",aGenit);
                t.Add("Genitália","V30Gy",Dir.MAX,35,null,"%",null,aGenit);
                t.Add("Genitália","V20Gy",Dir.MAX,50,null,"%",null,aGenit);
                t.Add("Vagina","V45Gy",Dir.MAX,50,null,"%","canal vaginal",aVagina);
                t.Add("PTV","D95%",Dir.MIN,95,90,"%",null,aPTV);
                t.Add("PTV","D10%",Dir.MAX,110,120,"%",null,aPTV);
                L.Add(t);
            }
            {   // Tabela 25 - Reto short-course 25 Gy/5 fx
                var t = NewAstro("Reto", "Tab.25 Reto short-course (5 fx)", "5 Gy/fx -> 25 Gy", new[]{5});
                t.Add("Bexiga","V25Gy",Dir.MAX,20,null,"%",null,aBladder);
                t.Add("Bexiga","V15Gy",Dir.MAX,50,null,"%",null,aBladder);
                t.Add("Bexiga","Mean",Dir.MAX,20,null,"Gy",null,aBladder);
                t.Add("Intestino delgado","D0.035cc",Dir.MAX,26.5,28.75,"Gy","saco intestinal (Bag)",aBowelS);
                t.Add("Intestino delgado","V20Gy",Dir.MAX,200,null,"cc","saco intestinal (Bag)",aBowelS);
                t.Add("Intestino delgado","V20Gy",Dir.MAX,50,null,"cc","alças individuais",aBowelS);
                t.Add("Femur D","D5%",Dir.MAX,25,null,"Gy",null,aFemurD);
                t.Add("Femur E","D5%",Dir.MAX,25,null,"Gy",null,aFemurE);
                t.Add("PTV","D95%",Dir.MIN,95,null,"%",null,aPTV);
                t.Add("PTV","D0.035cc",Dir.MAX,115,null,"%",null,aPTV);
                L.Add(t);
            }

            return L;
        }

        private ConstraintTable NewBreast(string title, string regimen, int[] matchFx)
        {
            return new ConstraintTable
            {
                Publication = "Consenso Brasileiro de Mama 2025",
                Site = "Mama",
                Title = title,
                Regimen = regimen,
                MatchFx = matchFx
            };
        }

        // ==================================================================
        //  DADOS: CONSENSO BRASILEIRO DE MAMA (hipofracionamento) - Tabela 2
        //  Cada trial = uma tabela (Site "Mama"). Valores TRANSCRITOS da tabela
        //  do consenso (Tabela 2), transcritos e CONFIRMADOS campo a campo
        //  com o físico. ESTADO: 8 trials completos. Notas CONFERIR residuais:
        //  faixas de dose do coração ("V16-20Gy < 5%" -> codificado V16Gy) e o
        //  esquema do MDACC (aparenta ser boost). Nomes de estruturas (pulmão
        //  ipsi, mama contra/não-alvo) dependem do template do Eclipse local.
        //  >>> VALIDAR cada constraint contra a publicação antes do uso clínico.
        // ==================================================================
        private List<ConstraintTable> BuildBrazilBreast()
        {
            var L = new List<ConstraintTable>();

            // aliases (o lado ipsi/contralateral depende da mama tratada -
            // conferir os nomes reais das estruturas no template do Eclipse)
            string aPTV     = "PTV|PTV_Mama|PTV Mama|PTVp|PTV_Boost|PTV Boost|PTV_SIB|PTVsib|PTV_Eval";
            // Pulmão IPSILATERAL: NÃO resolvido por estes aliases e sim por GEOMETRIA
            // (ResolveIpsiLung escolhe o pulmão do lado do alvo). Os aliases ficam só como
            // fallback/documentação. O relatório mostra a estrutura realmente usada.
            string aLungIps = "Lung_Ipsi|Pulmão Ipsilateral|Pulmao_Ipsi|Ipsi_Lung|Lung Ipsi|Pulmão_Ipsi|LungIpsi|Pulmão Ipsi|Lung_Ipsilateral|Pulmão_Ipsilateral|IpsilateralLung|Lung_L|Lung_R|Pulmão_D|Pulmão_E|Pulmão D|Pulmão E|Pulmao_D|Pulmao_E|Lung_Dir|Lung_Esq";
            string aHeart   = ALS_HEART;
            // Mama CONTRALATERAL: só variantes ROTULADAS como contralateral - NUNCA
            // nomes de lado puros (Mama D/E), que casariam a mama TRATADA por engano.
            string aBreastC = "Mama_Contralateral|Mama Contralateral|Breast_Contra|Contralateral_Breast|Mama_CL|BreastContra|Mama Contra|Mama_ContraLat|Mama Contralat|ContraBreast|Breast_CL|Mama_Contra_Lat|Breast_Contralateral";

            // ---------------- START B (40.05 Gy / 15 fx) ------------------
            {
                var t = NewBreast("START B", "2.67 Gy/fx -> 40.05 Gy (15 fx)", new[]{15});
                t.Add("Pulmão ipsilateral","V16Gy",Dir.MAX,15,20,"%",null,aLungIps);
                t.Add("Pulmão ipsilateral","V8Gy",Dir.MAX,35,40,"%",null,aLungIps);
                t.Add("Pulmão ipsilateral","V4Gy",Dir.MAX,50,55,"%",null,aLungIps);
                t.Add("Coração","Mean",Dir.MAX,3.2,4,"Gy",null,aHeart);
                t.Add("Coração","V8Gy",Dir.MAX,30,35,"%",null,aHeart);
                t.Add("Coração","V16Gy",Dir.MAX,5,null,"%","CONFERIR: fonte diz faixa V16-20Gy < 5%",aHeart);
                L.Add(t);
            }

            // ---------------- FAST (28.5-30 Gy / 5 fx) --------------------
            {
                var t = NewBreast("FAST", "5.7-6 Gy/fx -> 28.5-30 Gy (5 fx)", new[]{5});
                // PTV vazio (NA) na fonte.
                t.Add("Pulmão ipsilateral","V8Gy",Dir.MAX,15,null,"%",null,aLungIps);
                t.Add("Pulmão ipsilateral","V10Gy",Dir.MAX,30,null,"%","alfa/beta=1.7",aLungIps);
                t.Add("Coração","V14Gy",Dir.MAX,5,null,"%",null,aHeart);
                t.Add("Coração","V7Gy",Dir.MAX,5,null,"%",null,aHeart);
                t.Add("Coração","V1.5Gy",Dir.MAX,30,null,"%",null,aHeart);
                L.Add(t);
            }

            // ---------------- FAST-Forward (26 Gy / 5 fx) ----------------
            {
                var t = NewBreast("FAST-Forward", "5.2 Gy/fx -> 26 Gy (5 fx)", new[]{5});
                t.Add("PTV","V95%",Dir.MIN,95,90,"%","cobertura alvo 90-95%",aPTV);
                t.Add("PTV","V105%",Dir.MAX,5,7,"%",null,aPTV);
                t.Add("PTV","V107%",Dir.MAX,2,null,"%",null,aPTV);
                t.Add("PTV","D0.03cc",Dir.MAX,110,null,"%","Dmax",aPTV);
                t.Add("Pulmão ipsilateral","V30%",Dir.MAX,15,null,"%","V(30% da Prescrição) = ~7.8 Gy",aLungIps);
                t.Add("Coração","V25Gy",Dir.MAX,5,null,"%",null,aHeart);
                t.Add("Coração","V5Gy",Dir.MAX,25,null,"%",null,aHeart);
                L.Add(t);
            }

            // ---------------- Florence (30 Gy / 5 fx, APBI) ----------------
            {
                var t = NewBreast("Florence", "6 Gy/fx -> 30 Gy (5 fx, APBI)", new[]{5});
                t.Add("PTV","V28.5Gy",Dir.MIN,100,95,"%","28.5 Gy = 95% da Prescrição; meta 100% de cobertura",aPTV);
                t.Add("PTV","D0.03cc",Dir.MAX,105,null,"%","Dmax < 105% (~31.5 Gy)",aPTV);
                t.Add("PTV","D98%",Dir.MIN,28,null,"Gy","Dmin ~ near-min D98% (ICRU; D100% = voxel frio, instável)",aPTV);
                t.Add("Pulmão ipsilateral","V10Gy",Dir.MAX,20,null,"%",null,aLungIps);
                t.Add("Coração","V3Gy",Dir.MAX,10,null,"%","fonte: 'V3 < 10%' (interpretado como V3Gy)",aHeart);
                t.Add("Mama não-alvo (uninvolved)","V15Gy",Dir.MAX,50,null,"%","mama ipsilateral fora do alvo (APBI) - CONFERIR nome da estrutura","Mama_NaoAlvo|Mama não-alvo|Uninvolved_Breast|Breast_Uninvolved|Mama Sadia|Mama_Ipsi_NaoAlvo");
                t.Add("Mama contralateral","D0.03cc",Dir.MAX,1,null,"Gy","Dmax",aBreastC);
                L.Add(t);
            }

            // ---------------- MDACC (10-12.5 Gy / 4-5 fx) ------------------
            {
                // Constraints idênticos aos do START B (40.05/15) -> são do CURSO COMPLETO,
                // não do boost isolado (a "10-12.5 Gy / 4-5 fx" é o boost adicional). MatchFx=15
                // p/ avaliar no plano completo, senão V16Gy nunca dispara. CONFERIR na publicação.
                var t = NewBreast("MDACC", "curso completo ~40 Gy/15 fx (+ boost 10-12.5 Gy/4-5 fx) - CONFERIR", new[]{15});
                t.Add("Pulmão ipsilateral","V16Gy",Dir.MAX,15,20,"%",null,aLungIps);
                t.Add("Pulmão ipsilateral","V8Gy",Dir.MAX,35,40,"%",null,aLungIps);
                t.Add("Pulmão ipsilateral","V4Gy",Dir.MAX,50,55,"%",null,aLungIps);
                t.Add("Coração","Mean",Dir.MAX,3.2,4,"Gy",null,aHeart);
                t.Add("Coração","V8Gy",Dir.MAX,30,35,"%",null,aHeart);
                t.Add("Coração","V16Gy",Dir.MAX,5,null,"%","CONFERIR: fonte diz faixa V16-20Gy < 5%",aHeart);
                L.Add(t);
            }

            // ---------------- RTOG SIB (40.05 + 48 Gy SIB / 15 fx) --------
            {
                var t = NewBreast("RTOG SIB", "40.05 Gy (mama) + 48 Gy SIB (leito) em 15 fx", new[]{15});
                // SIB tem 2 Prescrições (40.05 mama + 48 boost); %-da-Prescrição seria ambíguo -> usa dose
                // absoluta: V38Gy = 95% de 40.05 Gy (cobertura da mama). *Vboost < 20% PTV = nota.
                t.Add("PTV","V38Gy",Dir.MIN,90,null,"%","cobertura mama: 95% de 40.05 Gy; *Vboost < 20% do PTV é constraint à parte (conferir)",aPTV);
                t.Add("Pulmão ipsilateral","Mean",Dir.MAX,10,null,"Gy","Dm",aLungIps);
                t.Add("Coração","Mean",Dir.MAX,5,null,"Gy","Dm",aHeart);
                t.Add("Coração","D0.03cc",Dir.MAX,40,null,"Gy","Dmax",aHeart);
                t.Add("Mama contralateral","D0.03cc",Dir.MAX,3,3.3,"Gy","Dmax 300 cGy; aceitável 330 cGy",aBreastC);
                L.Add(t);
            }

            // ---------------- Chinese Mastectomy (43.5 Gy / 15 fx) --------
            {
                var t = NewBreast("Chinese Mastectomy", "2.9 Gy/fx -> 43.5 Gy (15 fx)", new[]{15});
                t.Add("Pulmão ipsilateral","V20Gy",Dir.MAX,13,25,"%",null,aLungIps);
                t.Add("Pulmão ipsilateral","Mean",Dir.MAX,6.5,11,"Gy","Dm",aLungIps);
                t.Add("Coração","Mean",Dir.MAX,0.5,1.5,"Gy",null,aHeart);
                L.Add(t);
            }

            // ---------------- Half Moon (40.05 Gy / 15 fx) ----------------
            {
                var t = NewBreast("Half Moon", "2.67 Gy/fx -> 40.05 Gy (15 fx)", new[]{15});
                t.Add("Pulmão ipsilateral","V31Gy",Dir.MAX,15,null,"%",null,aLungIps);
                t.Add("Pulmão ipsilateral","V26.4Gy",Dir.MAX,20,null,"%",null,aLungIps);
                t.Add("Pulmão ipsilateral","V17.6Gy",Dir.MAX,30,null,"%",null,aLungIps);
                t.Add("Pulmão ipsilateral","Mean",Dir.MAX,13,null,"Gy","Dm",aLungIps);
                t.Add("Coração","V8Gy",Dir.MAX,15,null,"%",null,aHeart);
                t.Add("Coração","V6Gy",Dir.MAX,20,null,"%",null,aHeart);
                t.Add("Coração","Mean",Dir.MAX,5,null,"Gy",null,aHeart);
                L.Add(t);
            }

            return L;
        }

        private ConstraintTable NewCorsair(string title)
        {
            return new ConstraintTable
            {
                Publication = "CORSAIR 2022 (convencional)",
                Site = "OARs",
                Title = title,
                Regimen = "fracionamento convencional (~1.8-2 Gy/fx)",
                MatchFx = null
            };
        }

        // ==================================================================
        //  DADOS: CORSAIR — "Dose-Volume Constraints fOr oRganS At risk In
        //  Radiotherapy" (resumo prático multicêntrico; PMC9600677, 2022).
        //  Compilação que AGREGA QUANTEC + HyTEC + ESTRO + protocolos, com
        //  nível de evidência por constraint. Aqui usa-se a coluna de
        //  FRACIONAMENTO CONVENCIONAL (~1.8-2 Gy/fx), por REGIÃO anatômica
        //  (Site único "OARs"; cada região = uma tabela). SBRT/hipo ficam com
        //  Timmerman/ASTRO. VALIDE contra a tabela do CORSAIR antes do uso.
        // ==================================================================
        private List<ConstraintTable> BuildCorsair()
        {
            var L = new List<ConstraintTable>();

            string aCord   = "Spinal_Cord|Medula|Medula Espinhal|SpinalCord|Cord|Canal Medular|Medula_Espinhal";
            string aStem   = "Brainstem|Tronco|Tronco Cerebral|Brain_Stem|Tronco_Cerebral|BrainStem";
            string aChiasm = "Optic_Chiasm|Quiasma|Quiasma Optico|Chiasm|OpticChiasm|Quiasma_Optico";
            string aOptND  = "Optic_Nerve_R|Nervo_Optico_D|Optic_Nerve_D|N_Optico_D|Nervo Optico D";
            string aOptNE  = "Optic_Nerve_L|Nervo_Optico_E|Optic_Nerve_E|N_Optico_E|Nervo Optico E";
            string aBrain  = "Brain|Cerebro|Encefalo|Encéfalo|Cérebro";
            string aCochlea= "Cochlea|Coclea|Cóclea";
            string aLens   = "Lens|Cristalino|Lens_D|Lens_E|Lens_L|Lens_R|Cristalino_D|Cristalino_E";
            string aRetina = "Retina|Retina_D|Retina_E|Retina_L|Retina_R";
            string aMacula = "Macula|Mácula|Macula_D|Macula_E";
            string aParotD = "Parotid_R|Parotida_D|Parotid_D|Parotida Dir|Parótida D|Parotida_Dir";
            string aParotE = "Parotid_L|Parotida_E|Parotid_E|Parotida Esq|Parótida E|Parotida_Esq";
            string aLarynx = "Larynx|Laringe|Glottic_Larynx|Laringe_Glote";
            string aPCM    = "Constrictors|Constritores|Pharyngeal_Constrictors|Musculos Constritores|PCM|Constritores_Faringeos";
            string aMand   = "Mandible|Mandibula|Mandíbula";
            string aOral   = "Oral_Cavity|Cavidade Oral|OralCavity|Cavidade_Oral|Mucosa Oral|Boca";
            string aPlexus = "Brachial_Plexus|Plexo Braquial|BrachialPlexus|Plexo_Braquial";
            string aLiver  = "Liver|Figado|Fígado|Liver-GTV|Liver_GTV|Figado-GTV";
            string aBowel  = "Bowel|Small_Bowel|Intestino|Intestino Delgado|SmallBowel|Bowel_Bag|Bowel Bag|Intestino_Delgado|Alcas_Intestinais";
            string aRectum = "Rectum|Reto";
            string aBladder= "Bladder|Bexiga";
            string aBulb   = "PenileBulb|Bulbo_Peniano|Penile_Bulb|Bulbo Peniano";

            // ---------------- SNC ----------------
            {
                var t = NewCorsair("SNC (sistema nervoso central)");
                t.Add("Medula espinhal","D0.03cc",Dir.MAX,45,50,"Gy","Dmax (A)",aCord);
                t.Add("Tronco cerebral","D0.03cc",Dir.MAX,54,null,"Gy","Dmax; PRV (+ D1-10cc < 59 Gy) (A)",aStem);
                t.Add("Quiasma óptico","D0.03cc",Dir.MAX,55,null,"Gy","Dmax (A)",aChiasm);
                t.Add("Nervo óptico D","D0.03cc",Dir.MAX,55,null,"Gy","Dmax (A)",aOptND);
                t.Add("Nervo óptico E","D0.03cc",Dir.MAX,55,null,"Gy","Dmax (A)",aOptNE);
                t.Add("Cérebro","V60Gy",Dir.MAX,3,null,"cc","necrose; V60 <= 3 cc (A)",aBrain);
                t.Add("Cérebro","D0.03cc",Dir.MAX,72,null,"Gy","Dmax (A)",aBrain);
                t.Add("Cóclea","Mean",Dir.MAX,45,null,"Gy","idealmente ao menos 1 lado (A)",aCochlea);
                t.Add("Cristalino","D0.03cc",Dir.MAX,4,null,"Gy","Dmax; catarata (A)",aLens);
                t.Add("Retina","D0.03cc",Dir.MAX,45,50,"Gy","Dmax (A)",aRetina);
                t.Add("Mácula","D0.03cc",Dir.MAX,45,null,"Gy","Dmax (A)",aMacula);
                L.Add(t);
            }

            // ---------------- Cabeça e Pescoço ----------------
            {
                var t = NewCorsair("Cabeça e Pescoço");
                t.Add("Parótida D","Mean",Dir.MAX,25,null,"Gy","ambas <25 (ou uma poupada <20); contralat. V30<50%,V40<33% (A)",aParotD);
                t.Add("Parótida E","Mean",Dir.MAX,25,null,"Gy","ambas <25 (ou uma poupada <20); contralat. V30<50%,V40<33% (A)",aParotE);
                t.Add("Laringe","Mean",Dir.MAX,50,null,"Gy","+ V50 < 27% (A)",aLarynx);
                t.Add("Laringe","D0.03cc",Dir.MAX,66,null,"Gy","Dmax (A)",aLarynx);
                t.Add("Constritores faríngeos","Mean",Dir.MAX,50,null,"Gy","disfagia/aspiração (A)",aPCM);
                t.Add("Mandíbula","D0.03cc",Dir.MAX,70,73.5,"Gy","Dmax; ORN (+ V50 < 31% / 31cc, B)",aMand);
                t.Add("Cavidade oral","V30Gy",Dir.MAX,73,null,"%","limitar Dmean na cavidade oral não-alvo (B)",aOral);
                L.Add(t);
            }

            // ---------------- Tórax ----------------
            {
                var t = NewCorsair("Tórax");
                t.Add("Pulmões","V20Gy",Dir.MAX,20,null,"%","pneumonite (pulmões - GTV); + V5<50,V10<40,V30<15,V40<10 (A)","Pulmões|Pulmoes|Lungs|Lungs-GTV|Pulmoes-GTV");
                t.Add("Pulmões","Mean",Dir.MAX,20,null,"Gy","MLD (A)","Pulmões|Pulmoes|Lungs|Lungs-GTV|Pulmoes-GTV");
                t.Add("Coração","V25Gy",Dir.MAX,10,null,"%","mortalidade cardíaca <1% em 15 anos (A)",ALS_HEART);
                t.Add("Coração","V30Gy",Dir.MAX,30,null,"%","(A)",ALS_HEART);
                t.Add("Coração","Mean",Dir.MAX,26,30,"Gy","pericardite (A)",ALS_HEART);
                t.Add("Esôfago","Mean",Dir.MAX,34,null,"Gy","esofagite; + V35<50%,V50<40%,V70<20% (A)",ALS_ESOFAGO);
                t.Add("Plexo braquial","D0.1cc",Dir.MAX,60,66,"Gy","Dmax(0.1cc); ótimo 60 / mandatório 66 (A)",aPlexus);
                L.Add(t);
            }

            // ---------------- Abdome ----------------
            {
                var t = NewCorsair("Abdome");
                t.Add("Fígado","Mean",Dir.MAX,25,null,"Gy","fígado normal (-GTV); + V30 <= 33% (A)",aLiver);
                t.Add("Rins","Mean",Dir.MAX,18,null,"Gy","bilateral; + V20 <= 33% (A)","Rins|Kidneys|Rim_D|Rim_E|Rins_Bilateral");
                t.Add("Estômago","D0.03cc",Dir.MAX,54,null,"Gy","Dmax; + Mean<45, V45<15%, V50<10% (A)",ALS_ESTOMAGO);
                t.Add("Duodeno","D0.03cc",Dir.MAX,55,null,"Gy","Dmax; + V50<=10cc, V45<15% (A)",ALS_DUODENO);
                t.Add("Intestino delgado","V15Gy",Dir.MAX,120,null,"cc","alças; + Dmax<=55, V45<195cc (A)",aBowel);
                L.Add(t);
            }

            // ---------------- Pelve ----------------
            {
                var t = NewCorsair("Pelve");
                t.Add("Reto","V50Gy",Dir.MAX,50,null,"%","toxicidade tardia grau >=2/3 (A)",aRectum);
                t.Add("Reto","V60Gy",Dir.MAX,35,null,"%","(A)",aRectum);
                t.Add("Reto","V65Gy",Dir.MAX,25,null,"%","(A)",aRectum);
                t.Add("Reto","V70Gy",Dir.MAX,20,null,"%","(A)",aRectum);
                t.Add("Reto","V75Gy",Dir.MAX,15,null,"%","(A)",aRectum);
                t.Add("Bexiga","V65Gy",Dir.MAX,50,null,"%","próstata (A); ca bexiga: Dmax < 65",aBladder);
                t.Add("Bexiga","V70Gy",Dir.MAX,35,null,"%","(A)",aBladder);
                t.Add("Bexiga","V75Gy",Dir.MAX,25,null,"%","(A)",aBladder);
                t.Add("Bexiga","V80Gy",Dir.MAX,15,null,"%","(A)",aBladder);
                t.Add("Cabeça femoral D","V44Gy",Dir.MAX,5,null,"%","+ V40 < 35%, V30 < 50% (A)",ALS_FEMUR_D);
                t.Add("Cabeça femoral E","V44Gy",Dir.MAX,5,null,"%","+ V40 < 35%, V30 < 50% (A)",ALS_FEMUR_E);
                t.Add("Bulbo peniano","D90%",Dir.MAX,50,null,"Gy","disfunção erétil; + D70% < 70 Gy (A)",aBulb);
                L.Add(t);
            }

            return L;
        }

        // Adaptação LOCAL (fora da região PADRÃO CLINICA) do PatientCard() compartilhado:
        // PlanSum não é um PlanSetup, então não dá para reusar o PatientCard() da região
        // (que exige PlanSetup para ler Course/Id) sem editá-la. Mantém o mesmo HTML/CSS
        // ('card'/'grid'), só generaliza a leitura de Curso/Plano para os dois tipos.
        private static string PatientCardItem(Patient p, PlanningItem item, bool isSum, string extraCellsHtml)
        {
            var sb = new StringBuilder();
            sb.Append("<div class='card'><h2>Paciente &amp; plano</h2><div class='grid'>");
            sb.Append(Cell("Nome", p != null ? p.Name : "-"));
            sb.Append(Cell("ID", p != null ? p.Id : "-"));
            string nasc = (p != null && p.DateOfBirth.HasValue) ? p.DateOfBirth.Value.ToString("dd/MM/yyyy") : "-";
            sb.Append(Cell("Nascimento", nasc));
            string course, planLabel;
            if (isSum)
            {
                var sum = (PlanSum)item;
                course = sum.Course != null ? sum.Course.Id : "-";
                planLabel = sum.Id + " (soma)";
            }
            else
            {
                var ps = (PlanSetup)item;
                course = ps.Course != null ? ps.Course.Id : "-";
                planLabel = ps.Id;
            }
            sb.Append(Cell("Curso/Plano", course + " / " + planLabel));
            sb.Append(Cell("Emitido", DateTime.Now.ToString("dd/MM/yyyy HH:mm")));
            if (!string.IsNullOrEmpty(extraCellsHtml)) sb.Append(extraCellsHtml);
            sb.Append("</div></div>");
            return sb.ToString();
        }

        // ==================================================================
        //  RELATÓRIO HTML  (usa a região PADRÃO CLINICA — só a tabela detalhada
        //  é específica deste script)
        // ==================================================================
        private string BuildHtml(ScriptContext ctx, PlanningItem item, bool isSum, List<RxGroup> rxGroups,
                                 bool allFracOk, StructureSet ss, List<ConstraintTable> chosenTables,
                                 List<double> chosenRxGy, List<int> chosenFx, List<string> chosenGroupLabel,
                                 List<List<Result>> perTable)
        {
            var allResults = perTable.SelectMany(r => r).ToList();
            int nOk   = allResults.Count(r => r.Status == ST_OK);
            int nAtn  = allResults.Count(r => r.Status == ST_ATN);
            int nFail = allResults.Count(r => r.Status == ST_FAIL);
            int nNa   = allResults.Count(r => r.Status == ST_NA);
            int nChk  = allResults.Count(r => r.Status == ST_CHK);
            bool multi = chosenTables.Count > 1;

            var sb = new StringBuilder();
            sb.Append(HtmlOpen("Constraints — " + ctx.Patient.Id));
            sb.Append(Header("Verificação de constraints por publicação",
                             "Departamento de Radioterapia · avaliação de DVH do plano ativo"));

            // ---- cartão paciente/plano (+ células específicas) ----
            string extra = Cell("StructureSet", ss.Id);
            if (!isSum)
            {
                extra = Cell("Prescrição", Fmt(chosenRxGy[0]) + " Gy / " + chosenFx[0] + " fx") +
                        Cell("Dose/fx", Fmt(chosenRxGy[0] / Math.Max(1, chosenFx[0])) + " Gy") + extra;
            }
            else
            {
                var g = rxGroups[0];
                string metodo = g.Members.Count <= 1 ? "dose própria" : (g.UsedEqd2 ? "EQD2 α/β=" + Fmt(g.AlphaBeta) : "soma física");
                extra = Cell("Prescrição (soma)", Fmt(g.RxGy) + " Gy / " + g.Fx + " fx (" + metodo + ")") +
                        Cell("Dose/fx", Fmt(g.RxGy / Math.Max(1, g.Fx)) + " Gy") + extra;
            }
            sb.Append(PatientCardItem(ctx.Patient, item, isSum, extra));

            // ---- aviso: soma mistura fracionamentos diferentes (LQ/EQD2, ICRU 83) ----
            if (isSum && !allFracOk)
            {
                sb.Append("<div class='card' style='border-left-color:").Append(StatusFg(ST_ATN)).Append("'>");
                sb.Append("<h2>").Append(Badge(ST_ATN)).Append(" Fracionamento misto na soma</h2>");
                sb.Append("<div style='font-size:13px'>Os planos desta soma têm dose/fração DIFERENTES entre si. ");
                sb.Append("As métricas em Gy/cc (inclusive de OARs) vêm do DVH físico somado, SEM correção EQD2/BED ");
                sb.Append("&mdash; a soma física de doses com fracionamentos distintos não equivale à soma biológica ");
                sb.Append("(modelo linear-quadrático, ICRU 83). Interprete os valores em Gy/cc com cautela quando os ");
                sb.Append("planos envolvidos tiverem dose/fração muito diferente; a Prescrição do conjunto já foi ");
                sb.Append("ajustada por EQD2 quando necessário (ver observações no rodapé).</div>");
                sb.Append("</div>");
            }

            // ---- resumo (pílulas, agregado de todas as tabelas) ----
            sb.Append(SummaryPills(nFail, nAtn, nChk, nOk, nNa));

            // ---- ação necessária (agregada, FALHA primeiro, depois ATENÇÃO) ----
            var lines = new List<RptLine>();
            for (int t = 0; t < chosenTables.Count; t++)
                foreach (var r in perTable[t])
                {
                    if (r.Status != ST_FAIL && r.Status != ST_ATN) continue;
                    string prefix = multi ? "[" + chosenGroupLabel[t] + "] " : "";
                    string estr = prefix + (r.FoundStructure.Length > 0 ? r.FoundStructure : r.C.Structure);
                    string det = Esc(r.C.Metric) + ": atingido " + Esc(r.AchievedText) +
                                 " &mdash; objetivo " + Esc(ObjText(r.C));
                    lines.Add(new RptLine(r.Status, estr, det));
                }
            sb.Append(ActionBlock(lines));

            // ---- uma seção por tabela escolhida: referência + tabela detalhada ----
            for (int t = 0; t < chosenTables.Count; t++)
            {
                var tab = chosenTables[t];
                var results = perTable[t];

                sb.Append("<div class='card' style='border-left-color:").Append(BRAND_CYAN).Append("'>");
                sb.Append("<h2>Referência selecionada").Append(multi ? " — Grupo \"" + Esc(chosenGroupLabel[t]) + "\"" : "").Append("</h2>");
                sb.Append("<div style='font-size:14px'><b>").Append(Esc(tab.Publication)).Append("</b> &mdash; ")
                  .Append(Esc(tab.Title)).Append("</div>");
                sb.Append("<div class='sub'>Regime: ").Append(Esc(tab.Regimen)).Append(" &middot; Prescrição: ")
                  .Append(Fmt(chosenRxGy[t])).Append(" Gy / ").Append(chosenFx[t]).Append(" fx</div></div>");

                sb.Append("<table><thead><tr>");
                sb.Append("<th>Estrutura</th><th>Métrica</th><th>Objetivo</th><th>Atingido</th><th>Status</th><th>Observação</th>");
                sb.Append("</tr></thead><tbody>");

                string lastStruct = null;
                foreach (var r in results)
                {
                    if (r.C.Structure != lastStruct)
                    {
                        lastStruct = r.C.Structure;
                        string found = r.FoundStructure.Length > 0 &&
                                       !r.FoundStructure.Equals(r.C.Structure, StringComparison.OrdinalIgnoreCase)
                            ? " <span style='font-weight:400;color:#5A7480'>(&rarr; " + Esc(r.FoundStructure) + ")</span>"
                            : "";
                        sb.Append("<tr class='grp'><td colspan='6'>").Append(Esc(r.C.Structure)).Append(found).Append("</td></tr>");
                    }
                    sb.Append("<tr>");
                    sb.Append("<td></td>");
                    sb.Append("<td>").Append(Esc(r.C.Metric)).Append("</td>");
                    sb.Append("<td>").Append(Esc(ObjText(r.C))).Append("</td>");
                    sb.Append("<td>").Append(Esc(r.AchievedText)).Append("</td>");
                    sb.Append("<td>").Append(Badge(r.Status)).Append("</td>");
                    sb.Append("<td style='color:#5A7480;font-size:12px'>").Append(Esc(r.C.Notes)).Append("</td>");
                    sb.Append("</tr>");
                }
                sb.Append("</tbody></table>");
            }

            // ---- rodapé ----
            string sources =
                "ASTRO Consensus 2025 (Puckett LL et al., <i>Practical Radiation Oncology</i>, 2025) &middot; " +
                "Timmerman R, <i>Int J Radiat Oncol Biol Phys</i> 2022;112(1):4-21 (tabelas 8-2021) &middot; " +
                "Consenso Brasileiro de Mama 2025 (hipofracionamento, Tabela 2 — 8 trials) &middot; " +
                "CORSAIR (Dose-Volume Constraints for OARs, 2022; agrega QUANTEC/HyTEC/ESTRO).";
            string notes =
                "<b>Limitações:</b> valores transcritos das publicações &mdash; <u>valide contra o artigo original antes do uso clínico</u>. " +
                "Métricas volumétricas dependem de contorno correto (ex.: Lungs-GTV, Liver-GTV). " +
                "Pulmões/Rins: sem estrutura combinada, agregam-se os dois lados (Mean ponderado por volume; V/CV somam volumes). " +
                "PTV usa o alvo de prescrição do plano (TargetVolumeID); <b>CTV/GTV nunca são usados</b>. " +
                "As métricas em % usam a Prescrição indicada acima como 100%. " +
                "Fígado assume cenário não-cirrótico por padrão (ver observações p/ CP-A/CP-B).";
            if (isSum)
            {
                notes +=
                    " <b>Soma de planos:</b> PlanSum não tem TotalDose/TargetVolumeID próprios. A soma inteira é " +
                    "avaliada EM CONJUNTO (um alvo só): a Prescrição do conjunto foi confirmada pelo físico e serve " +
                    "de 100% nas métricas em %. Métricas em Gy/cc de qualquer estrutura (inclusive OARs) usam sempre " +
                    "o DVH da soma COMPLETA (dose física real de todos os componentes) &mdash; por isso a dose " +
                    "combinada nos OARs já aparece correta, sem precisar somar as prescrições. " +
                    "PTV genérico só é resolvido se houver exatamente um PTV no StructureSet da soma.";
                if (rxGroups.Any(g => g.UsedEqd2))
                    notes +=
                        " <b>EQD2:</b> os planos combinados têm dose/fração DIFERENTES entre si &mdash; a Prescrição " +
                        "do conjunto foi calculada por EQD2 (modelo linear-quadrático, ICRU 83) em vez de soma física " +
                        "direta, que seria biologicamente inválida nesse caso. Reavalie o α/β indicado se o " +
                        "alvo/endpoint pedir outro valor.";
                if (!allFracOk)
                    notes +=
                        " <b>Atenção:</b> esta soma mistura fracionamentos diferentes entre os planos combinados " +
                        "(ver aviso acima) &mdash; as métricas em Gy/cc (Mean, D0.035cc, V20Gy etc., inclusive de " +
                        "OARs) NÃO têm correção EQD2/BED; interprete-as com cautela.";
            }
            sb.Append(Footer(sources, notes));

            sb.Append(HtmlClose());
            return sb.ToString();
        }

        // objetivo formatado (≤/≥ em Unicode, não entidade HTML)
        private string ObjText(Constraint c)
        {
            string op = (c.Direction == Dir.MAX) ? "\u2264 " : "\u2265 ";
            string u = c.Unit == "%" ? "%" : (c.Unit == "cc" ? " cc" : " Gy");
            string s = op + Fmt(c.Primary) + u;
            if (c.Secondary.HasValue)
                s += " (sec " + op + Fmt(c.Secondary.Value) + u + ")";
            return s;
        }
    }
}
