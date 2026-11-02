// Plug-in ESAPI (DLL binária) — atribui o usuário logado como proprietário das
// atividades de Care Path do ARIA:
//     Documentação · Aprovação Física · Preparação PD · Execução PD · Análise PD
//
// NÃO altera plano, estruturas ou dose: só automatiza a interface do ARIA.
// O ESAPI é usado apenas para identificar o usuário logado (context.CurrentUser).
//
// Física Médica — Clinica/Rede.
// VALIDAR EM PACIENTE DE TESTE ANTES DE USO CLÍNICO.

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Interop;
using System.Windows.Threading;
using Clinica.Aria;
using VMS.TPS.Common.Model.API;

[assembly: AssemblyTitle("ARIA — proprietário de tarefas")]
[assembly: AssemblyCompany("Clinica / Rede — Física Médica")]
[assembly: AssemblyVersion("2.8.*")]

namespace VMS.TPS
{
    public class Script
    {
        // O ARIA roda no processo VMS.SF.Host, na mesma sessão do Eclipse. Casar por
        // processo é estável: as janelas se chamam "PACIENTE (ID) - <workspace>" e
        // nunca contêm "ARIA" no título.
        private static readonly string[] PROCESS_NAMES = new string[] { "VMS.SF.Host" };

        private static readonly int TIMEOUT_SEG = 10;
        // Profundidade do despejo: as atividades ficam ~15+ níveis abaixo da janela.
        private static readonly int DUMP_DEPTH  = 40;

        // Contêiner do Care Path na árvore do ARIA (visto no despejo de 17/09).
        private static readonly string CAREPATH_ROOT_ID = "VCarepathCtrlContainer";

        // Aba de lista do Care Path. A aba Visual desenha as atividades como ícones
        // sem nome (despejos de 18/09), então a leitura precisa desta.
        private static readonly string LIST_TAB_NAME = "Sequência de Tratamento";

        // Títulos EXATOS dos diálogos que o script abre e esconde (despejos de 18/09).
        // Qualquer outra janela do ARIA (ex.: mensagem de erro) continua visível.
        private static readonly string[] HIDDEN_DIALOG_TITLES = new string[]
        {
            "Caixa de diálogo Tarefa", "Seleção de Recurso e Equipe"
        };

        // Dois modos, SEM confirmação e SEM relatório (pedido do usuário, 18/09) —
        // mensagem só quando algo precisa de atenção; as conferências continuam:
        //  - diálogo aberto à mão → assume aquela atividade (validado no ARIA real, 18/09);
        //  - sem diálogo → lê a grade da aba de lista e
        //    abre e assume cada pendente (AutoAssigner), conferindo o diálogo aberto.

        public Script() { }

        public void Execute(ScriptContext context)
        {
            // Nenhum erro do script pode derrubar o Eclipse (trabalho de planejamento
            // não salvo). Qualquer exceção vira mensagem, com detalhe na área de transferência.
            try
            {
                ExecuteCore(context);
            }
            catch (Exception ex)
            {
                string msg = "Erro inesperado no script.\n\n" + ex.GetType().Name + ": " + ex.Message +
                    "\n\nConfira o ARIA: se houver Caixa de diálogo Tarefa ou Seleção de Recurso " +
                    "aberta, feche com Cancelar e verifique a atividade.";
                try
                {
                    Clipboard.SetText(ex.ToString());
                    msg += "\n\n(Detalhes copiados para a área de transferência — Ctrl+V para colar.)";
                }
                catch { }
                Box(msg, "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void ExecuteCore(ScriptContext context)
        {
            string[] owners = ResolveOwners(context);
            if (owners.Length == 0)
            {
                Box("Não foi possível identificar o usuário logado.",
                    "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // O paciente aberto no Eclipse é o dono das tarefas a assumir.
            string[] patientTokens = ResolvePatient(context);
            if (patientTokens.Length == 0)
            {
                Box(
                    "Nenhum paciente aberto no Eclipse.\n\n" +
                    "Abra o paciente cujas tarefas você quer assumir e rode o script de novo.",
                    "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Aviso discreto NA HORA: o usuário sabe que começou (e depois, que terminou).
            _toast = Toast.Show("ARIA — assumindo as tarefas do paciente…");

            // Daqui em diante nada usa o ESAPI: o Eclipse fica livre NA HORA e o trabalho
            // segue em segundo plano (pedido de 18/09: instantâneo, sem mostrar nada).
            // Só se o plug-in estiver no AppDomain padrão — se o Eclipse descarregasse
            // o domínio ao fim do Execute, a thread seria abortada no meio; aí roda
            // bloqueante, como antes.
            IntPtr eclipse = TaskDialogOwner.CurrentForeground();
            if (AppDomain.CurrentDomain.IsDefaultAppDomain())
            {
                Thread t = new Thread(delegate()
                {
                    try { Work(owners, patientTokens, eclipse); }
                    catch (Exception ex) { ShowError(ex); }
                });
                t.IsBackground = true;
                t.SetApartmentState(ApartmentState.MTA);
                t.Start();
                return;
            }
            Work(owners, patientTokens, eclipse);
        }

        private static void ShowError(Exception ex)
        {
            string msg = "Erro inesperado no script.\n\n" + ex.GetType().Name + ": " + ex.Message +
                "\n\nConfira o ARIA: se houver Caixa de diálogo Tarefa ou Seleção de Recurso " +
                "aberta, feche com Cancelar e verifique a atividade.";
            if (SetClipboard(ex.ToString()))
                msg += "\n\n(Detalhes copiados para a área de transferência — Ctrl+V para colar.)";
            Box(msg, "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Error);
        }

        private static void Work(string[] owners, string[] patientTokens, IntPtr eclipse)
        {
            // ARIA minimizado não expõe o Care Path: restaura para ler e, no fim,
            // minimiza de novo e devolve o foco ao Eclipse — fica como o usuário deixou.
            List<IntPtr> restored = TaskDialogOwner.RestoreMinimized(PROCESS_NAMES);
            try
            {
                WorkCore(owners, patientTokens, eclipse);
            }
            finally
            {
                ToastClose();   // se nada fechou o aviso (erro inesperado), fecha agora
                if (restored.Count > 0)
                {
                    TaskDialogOwner.Minimize(restored);
                    TaskDialogOwner.RestoreForeground(eclipse);
                }
            }
        }

        private static void WorkCore(string[] owners, string[] patientTokens, IntPtr eclipse)
        {
            // Modo diálogo: a atividade já está aberta na "Caixa de diálogo Tarefa"
            // (duplo clique manual) — assume só aquela atividade.
            TaskDialogOwner tdo = new TaskDialogOwner();
            tdo.ProcessNames  = PROCESS_NAMES;
            tdo.PatientTokens = patientTokens;
            tdo.HideDialogs   = true;
            AutomationElement taskDlg = tdo.FindOpenTaskDialog();
            if (taskDlg != null)
            {
                RunDialogMode(tdo, taskDlg, owners, eclipse);
                return;
            }

            OwnerAssigner assigner = new OwnerAssigner();
            assigner.ProcessNames        = PROCESS_NAMES;
            assigner.TimeoutSeconds      = TIMEOUT_SEG;
            assigner.PatientTokens       = patientTokens;
            assigner.RequirePatientMatch = true;
            assigner.ScopeAutomationId   = CAREPATH_ROOT_ID;
            assigner.TabToActivate       = LIST_TAB_NAME;

            // Sem diálogo aberto: lê a grade da aba de lista e monta o PLANO (só leitura);
            // se houver pendentes, RunAutoMode assume sem perguntar.
            OwnerResult plan = null;
            RunInBackground(delegate { plan = assigner.Run(owners, OwnerAssigner.DefaultTasks); });
            WriteLog(plan, "plano");

            // Nenhuma janela do ARIA na sessão: o diagnóstico é a informação que falta.
            if (!plan.WindowFound)
            {
                MessageBoxResult r = Box(
                    Join(plan) +
                    "\nO ARIA precisa estar aberto nesta mesma sessão do Eclipse.\n\n" +
                    "Listar as janelas visíveis agora?",
                    "ARIA — janela não encontrada",
                    MessageBoxButton.YesNo, MessageBoxImage.Warning);
                if (r == MessageBoxResult.Yes) ExportWindowList();
                return;
            }

            if (plan.CitrixBlocked || plan.PatientMismatch)
            {
                Box(Join(plan) + "\n\nNenhuma alteração foi feita.",
                    "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Modo automático: grade da aba de lista lida e há atividades prontas.
            if (plan.ListMode && plan.Ready.Count > 0)
            {
                RunAutoMode(plan, owners, patientTokens, eclipse);
                return;
            }

            // Nada a assumir: aviso discreto, ou mensagem se algo precisar de atenção.
            if (plan.ListMode)
            {
                string attention = PlanAttention(plan);
                if (attention.Length > 0)
                    Box("Nada foi alterado.\n\n" + attention + CopyToClipboard(plan.Log),
                        "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Warning);
                else
                    // Nada a assumir também é um fim sem problema: fecha a janela.
                    ToastDone(DoneSummary(new List<string>(), plan) + CloseAria(tdo, plan), true);
                return;
            }

            MessageBoxResult d = Box(
                Join(plan) +
                "\nA grade da aba de lista não foi reconhecida — nada foi alterado.\n\n" +
                "Exportar a árvore de controles (com valores das células) para diagnóstico?",
                "ARIA — plano de tarefas",
                MessageBoxButton.YesNo, MessageBoxImage.Information);
            if (d == MessageBoxResult.Yes) ExportTree(assigner, plan);
        }

        /// <summary>
        /// Fecha a janela do paciente no ARIA no fim de uma execução sem problema.
        /// Devolve "" se fechou, ou a linha a acrescentar no aviso se não deu.
        /// </summary>
        private static string CloseAria(TaskDialogOwner tdo, OwnerResult plan)
        {
            string why = tdo.CloseAriaWindow(plan.Grid);
            return why == null ? "" : "\n(A janela do ARIA continua aberta: " + why + ".)";
        }

        /// <summary>
        /// Itens do plano que o usuário precisa saber ("" = nada). Fica de fora o que
        /// é esperado: já é seu, nenhuma pendente, PD que não existe no fluxo.
        /// </summary>
        private static string PlanAttention(OwnerResult plan)
        {
            StringBuilder sb = new StringBuilder();
            foreach (string t in plan.Ambiguous)
                sb.AppendLine("• " + t + ": pendentes demais na lista — NÃO assumida; faça pelo duplo clique + script.");
            foreach (string t in plan.NotFoundTasks)
                sb.AppendLine("• " + t + ": obrigatória NÃO encontrada no Care Path.");
            foreach (string t in plan.NotChecked)
                sb.AppendLine("• " + t + ": não verificada (lista longa, leitura parcial).");
            return sb.ToString();
        }

        /// <summary>
        /// Assume as pendentes do plano, uma a uma, SEM perguntar e SEM relatório (pedido
        /// do usuário em 18/09): abre a linha, confere no diálogo (atividade, data,
        /// paciente, status) e faz Adicionar → você → Proprietário → OK → OK. Para na
        /// primeira falha. Mensagem só se algo precisar de atenção.
        /// </summary>
        private static void RunAutoMode(OwnerResult plan, string[] owners, string[] patientTokens, IntPtr eclipse)
        {
            TaskDialogOwner tdo = new TaskDialogOwner();
            tdo.ProcessNames  = PROCESS_NAMES;
            tdo.PatientTokens = patientTokens;
            tdo.HideDialogs   = true;

            AutoResult ar = null;
            // Diálogos transparentes no instante em que aparecem (ver DialogHider).
            using (new DialogHider(PROCESS_NAMES, HIDDEN_DIALOG_TITLES))
                RunInBackground(delegate { ar = AutoAssigner.Run(plan.Grid, plan.Ready, tdo, owners); });

            string attention = PlanAttention(plan);
            bool tudoCerto = !ar.Stopped && attention.Length == 0;

            // Terminou sem problema: fecha a janela do paciente no ARIA (pedido de
            // 22/09). Parando no meio a janela FICA aberta, para o usuário conferir.
            string closeInfo = tudoCerto ? CloseAria(tdo, plan) : null;
            tdo.RestoreAriaWindow();                      // (não fez nada se fechou)
            TaskDialogOwner.RestoreForeground(eclipse);   // o ARIA veio à frente para os cliques
            WriteLogLines(ar.Log, "automatico");

            if (tudoCerto)   // só o aviso discreto
            {
                ToastDone(DoneSummary(ar.DoneTasks, plan, ar.SkippedTasks) + closeInfo, true);
                return;
            }

            StringBuilder msg = new StringBuilder();
            msg.AppendLine(string.Format("Assumidas: {0} de {1}.", ar.Done, plan.Ready.Count));
            if (ar.Stopped)
            {
                msg.AppendLine("PAROU antes do fim — as atividades seguintes NÃO foram assumidas.");
                msg.AppendLine();
                msg.Append(JoinLines(ar.Log));
            }
            if (attention.Length > 0)
            {
                msg.AppendLine();
                msg.Append(attention);
            }
            List<string> all = new List<string>(plan.Log);
            all.AddRange(ar.Log);
            Box(msg.ToString() + CopyToClipboard(all),
                "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Warning);
        }

        /// <summary>
        /// Caixa de diálogo Tarefa aberta à mão: confere atividade, paciente e status no
        /// próprio diálogo e assume, SEM perguntar e SEM relatório. Mensagem só se falhar.
        /// </summary>
        private static void RunDialogMode(TaskDialogOwner tdo, AutomationElement taskDlg, string[] owners, IntPtr eclipse)
        {
            DialogOwnerResult run = null;
            using (new DialogHider(PROCESS_NAMES, HIDDEN_DIALOG_TITLES))
                RunInBackground(delegate { run = tdo.Run(taskDlg, owners, true); });
            TaskDialogOwner.RestoreForeground(eclipse);
            WriteLogLines(run.Log, "dialogo");

            // Concluída/cancelada não é erro: o aviso diz o porquê, sem caixa de mensagem.
            if (run.Skipped)
            {
                ToastDone("'" + run.Activity + "' está " + run.Status.ToLowerInvariant() +
                          " — nada alterado (só pendentes são assumidas).", true);
                return;
            }
            if (!run.Failed)   // tudo certo: só o aviso discreto
            {
                ToastDone(run.AlreadyOwner
                    ? "Você já era o proprietário de '" + run.Activity + "'."
                    : "✓ '" + run.Activity + "' assumida.", true);
                return;
            }
            Box(JoinLines(run.Log) + CopyToClipboard(run.Log),
                "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Warning);
        }

        /// <summary>
        /// Copia o log para a área de transferência: o %TEMP% do servidor Citrix não
        /// é acessível ao usuário, colar o log é o jeito de trazê-lo para análise.
        /// </summary>
        private static string CopyToClipboard(List<string> lines)
        {
            return SetClipboard(JoinLines(lines))
                ? "\n\n(Log copiado para a área de transferência — Ctrl+V para colar.)"
                : "";
        }

        /// <summary>Executa numa thread STA (área de transferência e mensagens exigem STA).</summary>
        private static void OnSta(ThreadStart action)
        {
            if (Thread.CurrentThread.GetApartmentState() == ApartmentState.STA)
            {
                action();
                return;
            }
            Thread t = new Thread(action);
            t.SetApartmentState(ApartmentState.STA);
            t.Start();
            t.Join();
        }

        private static bool SetClipboard(string text)
        {
            bool ok = false;
            OnSta(delegate
            {
                try { Clipboard.SetText(text); ok = true; }
                catch { }
            });
            return ok;
        }

        /// <summary>
        /// MessageBox de qualquer thread. Fora da thread do Eclipse (execução em segundo
        /// plano) aparece por cima de tudo, sem janela dona.
        /// </summary>
        private static MessageBoxResult Box(string text, string caption, MessageBoxButton button, MessageBoxImage icon)
        {
            ToastClose();   // mensagem com botão substitui o aviso discreto
            if (Thread.CurrentThread.GetApartmentState() == ApartmentState.STA &&
                !Thread.CurrentThread.IsBackground)
                return MessageBox.Show(text, caption, button, icon);

            MessageBoxResult r = MessageBoxResult.None;
            OnSta(delegate
            {
                r = MessageBox.Show(text, caption, button, icon, MessageBoxResult.None,
                    MessageBoxOptions.DefaultDesktopOnly);
            });
            return r;
        }

        private static string JoinLines(List<string> lines)
        {
            StringBuilder sb = new StringBuilder();
            foreach (string line in lines) sb.AppendLine(line);
            return sb.ToString();
        }

        private static string WriteLogLines(List<string> lines, string tag)
        {
            string path = Path.Combine(Path.GetTempPath(),
                string.Format("aria-proprietario-{0}-{1}.log", tag, DateTime.Now.ToString("yyyyMMdd-HHmmss")));
            try { File.WriteAllText(path, JoinLines(lines), new UTF8Encoding(true)); }
            catch { return "(falha ao gravar log)"; }
            return path;
        }

        /// <summary>
        /// Usuário logado no Eclipse, em variantes: o Id vem como "DOMINIO\login",
        /// mas o ARIA normalmente exibe só o login ou o nome.
        /// </summary>
        private static string[] ResolveOwners(ScriptContext context)
        {
            string id = "", name = "";
            try
            {
                if (context != null && context.CurrentUser != null)
                {
                    id = context.CurrentUser.Id ?? "";
                    name = context.CurrentUser.Name ?? "";
                }
            }
            catch { }

            if (id.Length == 0 && name.Length == 0) id = Environment.UserName;
            return OwnerAssigner.OwnerVariants(id, name);
        }

        /// <summary>
        /// Paciente aberto no Eclipse — é dele que as tarefas serão assumidas.
        /// Serve de trava: a janela de atividades precisa exibir um destes tokens.
        /// </summary>
        private static string[] ResolvePatient(ScriptContext context)
        {
            List<string> tokens = new List<string>();
            try
            {
                if (context != null && context.Patient != null)
                {
                    Patient p = context.Patient;
                    if (!string.IsNullOrEmpty(p.Id)) tokens.Add(p.Id);

                    string last = p.LastName ?? "";
                    string first = p.FirstName ?? "";
                    if (last.Length > 0 && first.Length > 0) tokens.Add(last + ", " + first);
                    else if (last.Length > 0) tokens.Add(last);
                }
            }
            catch { }
            return tokens.ToArray();
        }

        /// <summary>Inventário das janelas da sessão: diz se o Care Path está ao alcance.</summary>
        private static void ExportWindowList()
        {
            string path = Path.Combine(Path.GetTempPath(), "aria-janelas.txt");
            try
            {
                File.WriteAllText(path, OwnerAssigner.ListTopLevelWindows(), new UTF8Encoding(true));
                System.Diagnostics.Process.Start(path);
            }
            catch (Exception ex)
            {
                Box("Falha ao listar janelas: " + ex.Message,
                    "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private static string Join(OwnerResult r)
        {
            StringBuilder sb = new StringBuilder();
            foreach (string line in r.Log) sb.AppendLine(line);
            return sb.ToString();
        }

        private static string WriteLog(OwnerResult r, string tag)
        {
            string path = Path.Combine(Path.GetTempPath(),
                string.Format("aria-proprietario-{0}-{1}.log", tag, DateTime.Now.ToString("yyyyMMdd-HHmmss")));
            try { File.WriteAllText(path, Join(r), new UTF8Encoding(true)); }
            catch { return "(falha ao gravar log)"; }
            return path;
        }

        /// <summary>
        /// Despeja a subárvore do Care Path (sem limite prático de profundidade) junto
        /// com o log da simulação — é o que mostra onde estão as atividades.
        /// </summary>
        private static void ExportTree(OwnerAssigner assigner, OwnerResult dry)
        {
            // Montagem pesada em segundo plano; gravar/abrir na thread do Eclipse.
            string text = null;
            RunInBackground(delegate { text = BuildTreeReport(assigner, dry); });
            if (text == null) return;

            string path = Path.Combine(Path.GetTempPath(), "aria-arvore-ui.txt");
            try
            {
                File.WriteAllText(path, text, new UTF8Encoding(true));
                System.Diagnostics.Process.Start(path);
            }
            catch (Exception ex)
            {
                Box("Falha ao exportar: " + ex.Message,
                    "ARIA — proprietário de tarefas", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private static string BuildTreeReport(OwnerAssigner assigner, OwnerResult dry)
        {
            AutomationElement window = assigner.FindAriaWindow();
            if (window == null) return null;

            // Raiz do Care Path; se não existir, a janela inteira.
            AutomationElement root = OwnerAssigner.FindByAutomationId(window, CAREPATH_ROOT_ID);
            string rootLabel = CAREPATH_ROOT_ID;
            if (root == null) { root = window; rootLabel = "(janela inteira)"; }

            StringBuilder sb = new StringBuilder();
            sb.AppendLine("# ===== LOG DA SIMULAÇÃO =====");
            sb.AppendLine(Join(dry));
            sb.AppendLine("# ===== ÁRVORE — raiz: " + rootLabel + " | profundidade máx.: " + DUMP_DEPTH + " =====");
            sb.Append(OwnerAssigner.DumpTree(root, DUMP_DEPTH));

            // Diálogos abertos (ex.: edição da atividade aberta à mão com duplo clique).
            // No WPF o diálogo pode ser filho da janela principal ou outra janela de topo
            // do mesmo processo — despeja os dois casos.
            int nDialogs = 0;
            try
            {
                AutomationElementCollection inner = window.FindAll(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Window));
                foreach (AutomationElement d in inner)
                {
                    nDialogs++;
                    sb.AppendLine();
                    sb.AppendLine("# ===== DIÁLOGO (filho da janela principal) #" + nDialogs + " =====");
                    sb.Append(OwnerAssigner.DumpTree(d, DUMP_DEPTH));
                }
            }
            catch { }

            foreach (AutomationElement w in assigner.FindCandidateWindows())
            {
                if (Automation.Compare(w, window)) continue;
                // Só diálogos (têm AutomationId, ex. VDlg*); janelas grandes como a
                // "Tela Inicial do Usuário" só inchariam o arquivo.
                string wid = "";
                try { wid = w.Current.AutomationId ?? ""; }
                catch { }
                if (wid.Length == 0) continue;
                nDialogs++;
                sb.AppendLine();
                sb.AppendLine("# ===== OUTRA JANELA DO ARIA #" + nDialogs + " =====");
                sb.Append(OwnerAssigner.DumpTree(w, DUMP_DEPTH));
            }

            if (nDialogs == 0)
            {
                sb.AppendLine();
                sb.AppendLine("# (nenhum diálogo aberto)");
            }
            return sb.ToString();
        }


        // ---------- aviso discreto ----------

        /// <summary>
        /// Cartão no canto inferior direito: aparece NA HORA ("Assumindo tarefas…"),
        /// vira o resultado no fim e some sozinho. Não rouba o foco e não precisa de
        /// clique. Pedido de 18/09: sem janelas, mas com retorno de que terminou.
        /// </summary>
        private sealed class Toast
        {
            [System.Runtime.InteropServices.DllImport("user32.dll")]
            private static extern int GetWindowLong(IntPtr hWnd, int index);
            [System.Runtime.InteropServices.DllImport("user32.dll")]
            private static extern int SetWindowLong(IntPtr hWnd, int index, int value);
            private const int GWL_EXSTYLE = -20;
            private const int WS_EX_TRANSPARENT = 0x20;     // não recebe clique nem hit-test
            private const int WS_EX_NOACTIVATE = 0x8000000;
            private const int WS_EX_TOOLWINDOW = 0x80;

            private Window _win;
            private System.Windows.Controls.TextBlock _text;
            private System.Windows.Controls.Border _card;
            private Dispatcher _disp;
            private bool _finished;
            private readonly ManualResetEvent _ready = new ManualResetEvent(false);

            private static readonly System.Windows.Media.Color Teal =
                System.Windows.Media.Color.FromRgb(0x00, 0x5E, 0x78);    // Teal escuro Clinica
            private static readonly System.Windows.Media.Color Amber =
                System.Windows.Media.Color.FromRgb(0x8A, 0x5A, 0x00);

            public static Toast Show(string message)
            {
                Toast t = new Toast();
                Thread th = new Thread(delegate()
                {
                    try
                    {
                        t._text = new System.Windows.Controls.TextBlock();
                        t._text.Text = message;
                        t._text.Foreground = System.Windows.Media.Brushes.White;
                        t._text.FontSize = 13;
                        t._text.TextWrapping = TextWrapping.Wrap;
                        t._text.MaxWidth = 380;

                        t._card = new System.Windows.Controls.Border();
                        t._card.Background = new System.Windows.Media.SolidColorBrush(Teal);
                        t._card.CornerRadius = new CornerRadius(6);
                        t._card.Padding = new Thickness(14, 10, 14, 10);
                        t._card.Child = t._text;

                        t._win = new Window();
                        t._win.WindowStyle = WindowStyle.None;
                        t._win.AllowsTransparency = true;
                        t._win.Background = System.Windows.Media.Brushes.Transparent;
                        t._win.Topmost = true;
                        t._win.ShowInTaskbar = false;
                        t._win.ShowActivated = false;          // não rouba o foco do Eclipse
                        t._win.Focusable = false;
                        t._win.ResizeMode = ResizeMode.NoResize;
                        t._win.SizeToContent = SizeToContent.WidthAndHeight;
                        t._win.Content = t._card;
                        t._win.SizeChanged += delegate
                        {
                            Rect wa = SystemParameters.WorkArea;
                            t._win.Left = wa.Right - t._win.ActualWidth - 16;
                            t._win.Top = wa.Bottom - t._win.ActualHeight - 16;
                        };
                        // Com uma tela só o cartão fica EM CIMA da janela do ARIA. Sem
                        // isto ele entra no caminho do FromPoint/WindowFromPoint que
                        // confere a linha antes do clique, e a atividade não abriria.
                        t._win.SourceInitialized += delegate
                        {
                            try
                            {
                                IntPtr h = new WindowInteropHelper(t._win).Handle;
                                int ex = GetWindowLong(h, GWL_EXSTYLE);
                                SetWindowLong(h, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW);
                            }
                            catch { }
                        };
                        t._disp = Dispatcher.CurrentDispatcher;
                        t._win.Show();
                    }
                    catch { t._disp = null; }
                    t._ready.Set();
                    if (t._disp != null) Dispatcher.Run();
                });
                th.SetApartmentState(ApartmentState.STA);
                th.IsBackground = true;
                th.Start();
                t._ready.WaitOne(2000);
                return t;
            }

            /// <summary>Mostra o resultado e fecha sozinho depois de closeAfterMs.</summary>
            public void Finish(string message, bool ok, int closeAfterMs)
            {
                if (_disp == null || _finished) return;
                _finished = true;
                _disp.BeginInvoke(new Action(delegate
                {
                    _text.Text = message;
                    _card.Background = new System.Windows.Media.SolidColorBrush(ok ? Teal : Amber);
                    DispatcherTimer tm = new DispatcherTimer();
                    tm.Interval = TimeSpan.FromMilliseconds(closeAfterMs);
                    tm.Tick += delegate
                    {
                        tm.Stop();
                        _win.Close();
                        _disp.BeginInvokeShutdown(DispatcherPriority.Normal);
                    };
                    tm.Start();
                }));
            }

            /// <summary>Fecha já (antes de uma mensagem com botão).</summary>
            public void Close()
            {
                if (_disp == null || _finished) return;
                _finished = true;
                _disp.BeginInvoke(new Action(delegate
                {
                    _win.Close();
                    _disp.BeginInvokeShutdown(DispatcherPriority.Normal);
                }));
            }
        }

        private static Toast _toast;

        private static void ToastDone(string message, bool ok)
        {
            if (_toast != null) _toast.Finish(message, ok, ok ? 4000 : 6000);
        }

        /// <summary>Texto do aviso final: o que foi assumido e o que já era seu.</summary>
        private static string DoneSummary(List<string> done, OwnerResult plan)
        {
            return DoneSummary(done, plan, null);
        }

        /// <summary>
        /// Idem, citando as que foram puladas por já estarem concluídas/canceladas
        /// (descoberto no diálogo) — senão o cartão diria "nenhuma pendente" sem
        /// explicar por quê.
        /// </summary>
        private static string DoneSummary(List<string> done, OwnerResult plan, List<string> skipped)
        {
            StringBuilder sb = new StringBuilder();
            if (done.Count > 0)
                sb.Append("✓ " + done.Count + (done.Count == 1 ? " tarefa assumida: " : " tarefas assumidas: ") +
                          string.Join(", ", done.ToArray()));
            else
                sb.Append("Nenhuma tarefa pendente para assumir.");
            if (plan.AlreadyMine.Count > 0)
            {
                List<string> mine = new List<string>();
                foreach (TaskCandidate c in plan.AlreadyMine) mine.Add(c.Task);
                sb.Append("\nJá eram suas: " + string.Join(", ", mine.ToArray()));
            }
            if (skipped != null && skipped.Count > 0)
                sb.Append("\nJá fechadas (concluída/cancelada): " + string.Join(", ", skipped.ToArray()));
            return sb.ToString();
        }

        private static void ToastClose()
        {
            if (_toast != null) _toast.Close();
        }

        /// <summary>
        /// Roda o trabalho de UI Automation numa thread de fundo enquanto a thread do
        /// Eclipse continua processando mensagens. Sem isso, leituras longas deixam o
        /// Eclipse "Não está respondendo" (V1.8 travou ~1 min e o Eclipse fechou).
        /// Exceção da thread de fundo é relançada aqui (cai no try/catch do Execute).
        /// </summary>
        private static void RunInBackground(Action work)
        {
            // Já em segundo plano (execução destacada): roda direto, nada a bombear.
            if (Thread.CurrentThread.GetApartmentState() != ApartmentState.STA)
            {
                work();
                return;
            }

            Exception error = null;
            Thread t = new Thread(delegate()
            {
                try { work(); }
                catch (Exception ex) { error = ex; }
            });
            t.IsBackground = true;
            t.SetApartmentState(ApartmentState.MTA);
            t.Start();
            while (!t.Join(20)) PumpMessages();
            if (error != null) throw new InvalidOperationException(error.Message, error);
        }

        private static void PumpMessages()
        {
            DispatcherFrame frame = new DispatcherFrame();
            Dispatcher.CurrentDispatcher.BeginInvoke(DispatcherPriority.Background,
                new DispatcherOperationCallback(delegate(object f)
                {
                    ((DispatcherFrame)f).Continue = false;
                    return null;
                }), frame);
            Dispatcher.PushFrame(frame);
        }
    }
}
