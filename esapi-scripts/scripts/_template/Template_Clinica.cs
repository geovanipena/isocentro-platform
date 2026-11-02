////////////////////////////////////////////////////////////////////////////////
//  _Template_Clinica.cs                    Clinica-Rede · Física Médica
//------------------------------------------------------------------------------
//  MODELO PADRÃO da biblioteca de scripts ESAPI (Eclipse 15.6+).
//  Copie este arquivo para iniciar um novo script e preencha apenas as áreas
//  marcadas "PREENCHER". A região "PADRÃO CLINICA" (identidade visual, status,
//  HTML e utilitários) deve ser mantida IDÊNTICA em todos os scripts.
//------------------------------------------------------------------------------
//  ORGANIZAÇÃO PADRÃO DE TODO SCRIPT
//    1. Banner (este cabeçalho)                 5. Execute(ScriptContext)
//    2. usings                                  6. Lógica específica (PREENCHER)
//    3. Config específica (PREENCHER)           7. BuildReport (monta o HTML)
//    4. #region PADRÃO CLINICA (não editar)      8. #endregion
//
//  CONVENÇÕES
//    · namespace VMS.TPS · public class Script · pt-BR com acentos UTF-8 reais
//    · single-file (read-only) => salvar em UTF-8; writable => compilar .esapi.dll
//    · status: OK / ATN / FAIL / CHK / NA  (chaves em ST_*)
//    · relatório: HtmlOpen · Header · PatientCard · SummaryPills · ActionBlock ·
//      <table> específica · Footer · HtmlClose  ->  WriteAndOpen
//    · todo config em static readonly (o compilador trata warning como erro)
////////////////////////////////////////////////////////////////////////////////

using System;
using System.Linq;
using System.Text;
using System.Windows;
using System.Globalization;
using System.Collections.Generic;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

namespace VMS.TPS
{
    public class Script
    {
        // ===================== CONFIG ESPECÍFICA (PREENCHER) =====================
        // Ex.: tolerâncias, títulos, aliases de estrutura, tabelas embarcadas...
        private static readonly string REPORT_TITLE = "Título do relatório";
        private static readonly string REPORT_SUB   = "Subtítulo / contexto do script";
        private static readonly string FILE_TAG     = "Relatorio"; // nome do arquivo de saída
        // ========================================================================

        // linha genérica do relatório (adapte ao seu domínio)
        private class Item
        {
            public string Category, Name, Status, Detail;
            public Item(string cat, string name, string status, string detail)
            { Category = cat; Name = name; Status = status; Detail = detail; }
        }
        private readonly List<Item> m_rows = new List<Item>();
        private void Add(string cat, string name, string status, string detail)
        { m_rows.Add(new Item(cat, name, status, detail)); }

        public Script() { }

        public void Execute(ScriptContext context)
        {
            if (context == null || context.Patient == null)
            { MessageBox.Show("Carregue um paciente."); return; }

            PlanSetup plan = context.PlanSetup;
            if (plan == null)
            { MessageBox.Show("Carregue um plano (PlanSetup) ativo."); return; }

            // ------------------- LÓGICA ESPECÍFICA (PREENCHER) -------------------
            // Popule m_rows com Add(categoria, item, ST_*, detalhe). Exemplo:
            try
            {
                Add("A. Exemplo", "Item avaliado automaticamente", ST_OK, "valor lido do plano = OK");
                Add("A. Exemplo", "Item com desvio aceitável", ST_ATN, "fora do primário, dentro do secundário");
                Add("B. Exemplo", "Item fora de tolerância", ST_FAIL, "excede o limite");
                Add("B. Exemplo", "Item de conferência manual", ST_CHK, "requer julgamento do físico");
            }
            catch (Exception ex) { Add("A. Exemplo", "Erro interno", ST_FAIL, ex.Message); }
            // ---------------------------------------------------------------------

            string html = BuildReport(context, plan);
            WriteAndOpen(context.Patient.Id, FILE_TAG, html);
        }

        // ==================================================================
        //  RELATÓRIO  (esqueleto padrão — só a <table> abaixo é específica)
        // ==================================================================
        private string BuildReport(ScriptContext ctx, PlanSetup plan)
        {
            int nOk   = m_rows.Count(r => r.Status == ST_OK);
            int nAtn  = m_rows.Count(r => r.Status == ST_ATN);
            int nFail = m_rows.Count(r => r.Status == ST_FAIL);
            int nChk  = m_rows.Count(r => r.Status == ST_CHK);
            int nNa   = m_rows.Count(r => r.Status == ST_NA);

            var sb = new StringBuilder();
            sb.Append(HtmlOpen(REPORT_TITLE + " — " + ctx.Patient.Id));
            sb.Append(Header(REPORT_TITLE, REPORT_SUB));
            sb.Append(PatientCard(ctx.Patient, plan, "")); // 3º arg: células extras (CellRaw/Cell) ou ""
            sb.Append(SummaryPills(nFail, nAtn, nChk + nNa, nOk, 0));

            var lines = new List<RptLine>();
            foreach (var r in m_rows)
                if (r.Status == ST_FAIL || r.Status == ST_ATN)
                    lines.Add(new RptLine(r.Status, r.Name, r.Detail));
            sb.Append(ActionBlock(lines));

            // ------ tabela específica do script (use classe 'grp' p/ grupos e Badge()) ------
            sb.Append("<table><thead><tr>");
            sb.Append("<th style='width:34%'>Item</th><th style='width:120px;text-align:center'>Status</th><th>Observação</th>");
            sb.Append("</tr></thead><tbody>");
            foreach (var cat in m_rows.Select(r => r.Category).Distinct())
            {
                sb.Append("<tr class='grp'><td colspan='3'>").Append(Esc(cat)).Append("</td></tr>");
                foreach (var r in m_rows.Where(r => r.Category == cat))
                {
                    sb.Append("<tr><td>").Append(Esc(r.Name)).Append("</td>");
                    sb.Append("<td style='text-align:center'>").Append(Badge(r.Status)).Append("</td>");
                    sb.Append("<td>").Append(r.Detail).Append("</td></tr>");
                }
            }
            sb.Append("</tbody></table>");
            // -------------------------------------------------------------------------------

            sb.Append(Footer("Referências do script (PREENCHER).",
                             "Observações/limitações específicas (PREENCHER)."));
            sb.Append(HtmlClose());
            return sb.ToString();
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
}
