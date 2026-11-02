// Núcleo de automação de interface para atribuição de proprietário de atividades
// de Care Path no ARIA. Sem dependência de ESAPI — compilável e testável fora do
// Eclipse (ver tools/Proprietario_Tarefas.ps1 para a versão PowerShell).
//
// Física Médica — Clinica/Rede.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Threading;
using System.Windows.Automation;

namespace Clinica.Aria
{
    /// <summary>Linha pendente de uma tarefa-alvo no Care Path.</summary>
    public class TaskCandidate
    {
        public string Task;
        public string Status;
        public AutomationElement Cell;   // célula com o nome da atividade
        public AutomationElement Row;    // linha (menor ancestral com o status)
        public ListRow ListRow;          // quando lido da grade da aba de lista
    }

    /// <summary>
    /// Linha da grade "m_dgTemplateViewer" (aba "Sequência de Tratamento"). Estrutura
    /// do despejo de 18/09: "RowN" com células "RowN_colX" cujo texto está no Value.
    /// </summary>
    public class ListRow
    {
        public int Index;
        public AutomationElement Row;
        public string Activity = "";   // RowN_colActivityCode
        public string Status = "";     // RowN_colStatus
        public string Date = "";       // RowN_colDate
        public string Owner = "";      // RowN_colOwner (Proprietário da Tarefa)
        public AutomationElement ClickCell;   // RowN_colDuration: célula SEM botão interno
    }

    /// <summary>Plano lido do Care Path (só leitura).</summary>
    public class OwnerResult
    {
        public int Assigned;        // = Ready.Count
        public int NotFound;        // obrigatória ausente — problema
        public int NotApplicable;   // opcional (PD) ausente — o fluxo não tem
        public int Failed;
        public readonly List<string> NotApplicableTasks = new List<string>();
        public bool WindowFound;
        public bool CitrixBlocked;
        public readonly List<string> Log = new List<string>();
        public readonly List<string> NotFoundTasks = new List<string>();

        public readonly List<TaskCandidate> Ready = new List<TaskCandidate>();   // 1 pendente
        public readonly List<TaskCandidate> AlreadyMine = new List<TaskCandidate>();   // pendente, já sou o dono

        // Leitura pela grade da aba de lista (caminho rápido).
        public bool ListMode;
        public AutomationElement Grid;
        public int TotalRows, RowsRead;
        public readonly List<string> Ambiguous = new List<string>();             // >1 pendente
        public readonly List<string> NothingPending = new List<string>();        // só fechadas/sem status

        // Leitura interrompida pelo orçamento de tempo: ausência ≠ inexistência.
        public bool ReadTruncated;
        public readonly List<string> NotChecked = new List<string>();

        public bool AnyProblem
        {
            get { return Failed > 0 || NotFound > 0 || Ambiguous.Count > 0 || ReadTruncated; }
        }

        /// <summary>Janela encontrada, mas sem confirmação de que é o paciente do Eclipse.</summary>
        public bool PatientMismatch;
        public string PatientEvidence = "";
    }

    /// <summary>
    /// Localiza as atividades pelo rótulo e define o proprietário via UI Automation.
    /// </summary>
    public class OwnerAssigner
    {
        // ---------- configuração ----------

        public static readonly string[] DefaultTasks = new string[]
        {
            "Documentação",
            "Aprovação Física",
            "Preparação PD",
            "Execução PD",
            "Análise PD"
        };

        /// <summary>
        /// Tarefas que só existem em fluxos com Portal Dosimetry. Ausentes no Care
        /// Path = "não se aplica", não problema.
        /// </summary>
        public static readonly string[] OptionalTasks = new string[]
        {
            "Preparação PD",
            "Execução PD",
            "Análise PD"
        };

        public static bool IsOptional(string task)
        {
            string k = TaskKey(task);
            for (int i = 0; i < OptionalTasks.Length; i++)
                if (TaskKey(OptionalTasks[i]) == k) return true;
            return false;
        }

        /// <summary>
        /// Chave de comparação de nome de tarefa: Norm() sem as preposições
        /// de/da/do/dos/das — "Preparação de PD" e "Preparação PD" são a mesma tarefa.
        /// </summary>
        public static string TaskKey(string text)
        {
            string s = " " + Norm(text) + " ";
            string[] preps = new string[] { " DE ", " DA ", " DO ", " DOS ", " DAS " };
            bool changed = true;
            while (changed)
            {
                changed = false;
                for (int i = 0; i < preps.Length; i++)
                {
                    if (s.Contains(preps[i])) { s = s.Replace(preps[i], " "); changed = true; }
                }
            }
            return s.Trim();
        }

        private static readonly string[] CitrixProcesses = new string[]
        {
            "wfica32", "CDViewer", "SelfServicePlugin", "concentr"
        };

        private static readonly string[] RowTypes = new string[] { "DataItem", "TreeItem", "ListItem" };

        // Name acima disso é bloco de texto (painel/log), não rótulo de tarefa.
        private const int MaxTaskNameLength = 200;

        /// <summary>
        /// Processos que hospedam o ARIA. Casar por processo é bem mais estável que
        /// por título: as janelas do ARIA se chamam "PACIENTE (ID) - <workspace>" e
        /// nunca contêm "ARIA" no nome.
        /// </summary>
        public string[] ProcessNames = new string[] { "VMS.SF.Host" };

        /// <summary>Títulos candidatos — complemento, usado além do processo.</summary>
        public string[] WindowTitles = new string[0];

        public int TimeoutSeconds = 20;

        // Grade de atividades, se conhecida ("" = contêiner inteiro do Care Path).
        public string GridAutomationId = "";

        /// <summary>
        /// Identificadores do paciente aberto no Eclipse (ID e nome). A janela do
        /// Care Path precisa exibir um deles: sem isso não há garantia de que as
        /// atividades na tela são as do paciente certo.
        /// </summary>
        public string[] PatientTokens = new string[0];

        /// <summary>Com true, não atribui nada se o paciente não for confirmado na tela.</summary>
        public bool RequirePatientMatch = true;

        /// <summary>
        /// AutomationId do contêiner onde as tarefas são procuradas (no ARIA:
        /// "VCarepathCtrlContainer"). Sem isso a busca varre a janela inteira — e
        /// casa com o combo de atividades de um diálogo aberto (falso positivo visto
        /// em 18/09). Se configurado e não encontrado, a janela é ignorada.
        /// </summary>
        public string ScopeAutomationId = "";

        /// <summary>
        /// Aba a ativar dentro do escopo antes de ler (ARIA: "Sequência de Tratamento",
        /// a lista). A aba Visual desenha as atividades como ícones sem nome, e a aba
        /// inativa não tem conteúdo carregado. Casamento EXATO do nome, para não
        /// confundir com "Sequência do Tratamento Visual". Só navegação: não altera dado.
        /// </summary>
        public string TabToActivate = "";
        public int TabWaitMs = 3000;

        /// <summary>TabControl do Care Path (despejo de 17/09): abas "Visual" e "Sequência de Tratamento".</summary>
        public string TabControlAutomationId = "vTabControl";

        private delegate bool EnumChildProc(IntPtr hWnd, IntPtr lParam);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool EnumChildWindows(IntPtr parent, EnumChildProc cb, IntPtr lParam);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool IsWindowVisible(IntPtr hWnd);
        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
        private static extern int GetClassName(IntPtr hWnd, StringBuilder name, int max);

        /// <summary>
        /// Acha um controle WinForms pelas JANELAS-FILHAS (AutomationId = Name do
        /// controle; ou Name acessível). Muito mais rápido que varrer a árvore de
        /// acessibilidade da janela do ARIA inteira (milhares de elementos a ~15 ms
        /// cada) — era a demora no início relatada em 18/09.
        /// </summary>
        public static AutomationElement FastFind(AutomationElement parent, string automationId, string name, bool mustBeVisible)
        {
            IntPtr ph;
            try { ph = new IntPtr(parent.Current.NativeWindowHandle); }
            catch { return null; }
            if (ph == IntPtr.Zero) return null;

            AutomationElement found = null;
            try
            {
                EnumChildWindows(ph, delegate(IntPtr h, IntPtr l)
                {
                    if (mustBeVisible && !IsWindowVisible(h)) return true;
                    StringBuilder cls = new StringBuilder(128);
                    GetClassName(h, cls, 128);
                    // Só contêineres WinForms (classe Window / TabControl): contêiner do Care Path,
                    // abas e grade são desses. Rótulos, botões e campos (STATIC, BUTTON, EDIT…)
                    // são pulados SEM consultar a UI Automation — eram a maior parte do custo.
                    string c = cls.ToString();
                    if (!c.StartsWith("WindowsForms10")) return true;
                    if (c.IndexOf(".Window.", StringComparison.Ordinal) < 0 &&
                        c.IndexOf("SysTabControl32", StringComparison.Ordinal) < 0) return true;
                    try
                    {
                        AutomationElement e = AutomationElement.FromHandle(h);
                        if ((automationId != null && SafeAutomationId(e) == automationId) ||
                            (name != null && SafeName(e) == name))
                        {
                            found = e;
                            return false;
                        }
                    }
                    catch { }
                    return true;
                }, IntPtr.Zero);
            }
            catch { }
            return found;
        }

        /// <summary>Tempo máximo de leitura do Care Path; estourou = plano parcial.</summary>
        public int SnapshotBudgetMs = 25000;

        /// <summary>
        /// Recorte da leitura da lista: para ao passar de atividades mais antigas que
        /// isso (o tratamento atual fica no fim da lista cronológica). 0 = sem recorte.
        /// </summary>
        public int RecentDays = 60;

        /// <summary>
        /// Quantas ocorrências pendentes da MESMA atividade o script assume sozinho.
        /// Acima disso a lista é atípica (retratamentos sobrepostos) e quem escolhe é
        /// o usuário, pelo duplo clique + script.
        /// </summary>
        public int MaxPendingPerTask = 3;

        private OwnerResult _result;

        private void Log(string level, string message)
        {
            string line = string.Format("{0} [{1}] {2}",
                DateTime.Now.ToString("HH:mm:ss", CultureInfo.InvariantCulture), level, message);
            _result.Log.Add(line);
        }

        // ---------- utilitários ----------

        /// <summary>Normalização acento- e caixa-insensível (mesma regra do Norm() dos demais scripts).</summary>
        public static string Norm(string text)
        {
            if (string.IsNullOrEmpty(text)) return "";
            string d = text.Normalize(NormalizationForm.FormD);
            StringBuilder sb = new StringBuilder(d.Length);
            for (int i = 0; i < d.Length; i++)
            {
                if (CharUnicodeInfo.GetUnicodeCategory(d[i]) != UnicodeCategory.NonSpacingMark)
                    sb.Append(d[i]);
            }
            string s = sb.ToString().ToUpperInvariant().Trim();
            while (s.Contains("  ")) s = s.Replace("  ", " ");
            return s;
        }

        private static string TypeName(AutomationElement e)
        {
            try { return e.Current.ControlType.ProgrammaticName.Replace("ControlType.", ""); }
            catch { return ""; }
        }

        private static string SafeName(AutomationElement e)
        {
            try { return e.Current.Name ?? ""; }
            catch { return ""; }
        }

        /// <summary>
        /// Value do ValuePattern ("" se não suportado). Nas grades Janus do ARIA é
        /// aqui que está o texto da célula (nome da atividade, participante, flag).
        /// </summary>
        private static string ReadValue(AutomationElement e, bool cached)
        {
            try
            {
                object v = cached
                    ? e.GetCachedPropertyValue(ValuePattern.ValueProperty, true)
                    : e.GetCurrentPropertyValue(ValuePattern.ValueProperty, true);
                if (v == null || v == AutomationElement.NotSupported) return "";
                return v as string ?? "";
            }
            catch
            {
                if (!cached) return "";
                return ReadValue(e, false);   // sem cache: tenta ao vivo
            }
        }

        private static string SafeAutomationId(AutomationElement e)
        {
            try { return e.Current.AutomationId ?? ""; }
            catch { return ""; }
        }

        private static string Shorten(string s, int max)
        {
            if (string.IsNullOrEmpty(s)) return "";
            s = s.Replace("\r", " ").Replace("\n", " ").Trim();
            return s.Length > max ? s.Substring(0, max) + "…" : s;
        }

        private static string JoinStatuses(List<TaskCandidate> cands)
        {
            string[] s = new string[cands.Count];
            for (int i = 0; i < cands.Count; i++) s[i] = cands[i].Status;
            return string.Join(", ", s);
        }

        private static bool Contains(string[] set, string value)
        {
            for (int i = 0; i < set.Length; i++)
                if (set[i] == value) return true;
            return false;
        }

        private static AutomationElementCollection AllDescendants(AutomationElement scope)
        {
            return scope.FindAll(TreeScope.Descendants, Condition.TrueCondition);
        }

        // Uma linha do Care Path tem poucas dezenas de elementos; acima disso é grade.
        private const int MaxRowElements = 80;

        /// <summary>
        /// Descendentes com teto: percorre com TreeWalker e desiste (null) assim que
        /// passar de 'max' — nunca lê uma subárvore grande inteira.
        /// </summary>
        private static List<AutomationElement> BoundedDescendants(AutomationElement root, int max)
        {
            List<AutomationElement> list = new List<AutomationElement>();
            TreeWalker walker = TreeWalker.ControlViewWalker;
            Stack<AutomationElement> stack = new Stack<AutomationElement>();
            stack.Push(root);
            try
            {
                while (stack.Count > 0)
                {
                    AutomationElement node = stack.Pop();
                    AutomationElement child = walker.GetFirstChild(node);
                    while (child != null)
                    {
                        list.Add(child);
                        if (list.Count > max) return null;
                        stack.Push(child);
                        child = walker.GetNextSibling(child);
                    }
                }
            }
            catch { return null; }
            return list;
        }

        // ---------- janela ----------

        public AutomationElement FindAriaWindow()
        {
            List<AutomationElement> c = FindCandidateWindows();
            if (c.Count == 0) return null;

            // Prefere a janela cujo título traz o paciente (ex.: "... (9000001CEL) - ...").
            foreach (AutomationElement w in c)
            {
                string t = Norm(SafeName(w));
                for (int i = 0; i < PatientTokens.Length; i++)
                    if (PatientTokens[i].Length > 0 && t.Contains(Norm(PatientTokens[i]))) return w;
            }
            return c[0];
        }

        /// <summary>
        /// Ativa a aba cujo nome casa EXATAMENTE (normalizado) com tabName.
        /// </summary>
        public static bool ActivateTab(AutomationElement root, string tabName, out string info)
        {
            return ActivateTab(root, tabName, TreeScope.Descendants, out info);
        }

        public static bool ActivateTab(AutomationElement root, string tabName, TreeScope scope, out string info)
        {
            info = "aba não encontrada";
            string target = Norm(tabName);
            try
            {
                AutomationElementCollection tabs = root.FindAll(scope,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.TabItem));
                foreach (AutomationElement t in tabs)
                {
                    if (Norm(SafeName(t)) != target) continue;

                    object p;
                    if (t.TryGetCurrentPattern(SelectionItemPattern.Pattern, out p))
                    {
                        ((SelectionItemPattern)p).Select();
                        info = "SelectionItem";
                        return true;
                    }
                    if (t.TryGetCurrentPattern(InvokePattern.Pattern, out p))
                    {
                        ((InvokePattern)p).Invoke();
                        info = "Invoke";
                        return true;
                    }
                    info = "aba sem padrão acionável";
                    return false;
                }
            }
            catch (Exception ex)
            {
                info = "erro ao ativar: " + ex.Message;
            }
            return false;
        }

        /// <summary>Primeiro descendente com o Name dado, ou null.</summary>
        public static AutomationElement FindByName(AutomationElement root, string name)
        {
            try
            {
                return root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.NameProperty, name));
            }
            catch { return null; }
        }

        /// <summary>Primeiro descendente com o AutomationId dado, ou null.</summary>
        public static AutomationElement FindByAutomationId(AutomationElement root, string automationId)
        {
            try
            {
                return root.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.AutomationIdProperty, automationId));
            }
            catch { return null; }
        }

        /// <summary>
        /// Todas as janelas do ARIA nesta sessão. O Care Path pode estar em qualquer
        /// uma delas (ex.: "Tela Inicial do Usuário" ou a janela do paciente), por isso
        /// devolve todas em vez de escolher uma.
        /// </summary>
        public List<AutomationElement> FindCandidateWindows()
        {
            DateTime limit = DateTime.Now.AddSeconds(TimeoutSeconds);

            while (true)
            {
                List<AutomationElement> found = new List<AutomationElement>();

                foreach (AutomationElement w in TopLevelWindows())
                {
                    bool match = false;

                    // 1) por processo (critério principal)
                    try
                    {
                        string proc = Process.GetProcessById(w.Current.ProcessId).ProcessName;
                        for (int i = 0; i < ProcessNames.Length && !match; i++)
                            if (string.Equals(proc, ProcessNames[i], StringComparison.OrdinalIgnoreCase))
                                match = true;
                    }
                    catch { }

                    // 2) por título (complemento)
                    if (!match)
                    {
                        string n = Norm(SafeName(w));
                        for (int i = 0; i < WindowTitles.Length && !match; i++)
                            if (n.Length > 0 && n.Contains(Norm(WindowTitles[i]))) match = true;
                    }

                    if (match) found.Add(w);
                }

                if (found.Count > 0) return found;
                if (DateTime.Now >= limit) return found;
                Thread.Sleep(500);
            }
        }

        private static AutomationElementCollection TopLevelWindows()
        {
            return AutomationElement.RootElement.FindAll(TreeScope.Children,
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Window));
        }

        /// <summary>
        /// Inventário das janelas de topo visíveis nesta sessão. É o que diz se o
        /// Care Path está ao alcance e com que título — sem isso não há como
        /// configurar WindowTitles.
        /// </summary>
        public static string ListTopLevelWindows()
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("# Janelas de topo visíveis na sessão — " +
                DateTime.Now.ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture));
            sb.AppendLine("# Sessão Windows: " + Process.GetCurrentProcess().SessionId +
                " | processo host: " + Process.GetCurrentProcess().ProcessName);
            sb.AppendLine();

            int n = 0;
            foreach (AutomationElement w in TopLevelWindows())
            {
                n++;
                string proc = "?";
                int sessionId = -1;
                try
                {
                    Process p = Process.GetProcessById(w.Current.ProcessId);
                    proc = p.ProcessName;
                    sessionId = p.SessionId;
                }
                catch { }

                string cls = "";
                try { cls = w.Current.ClassName ?? ""; }
                catch { }

                sb.AppendLine(string.Format("[{0:00}] Name=\"{1}\"", n, SafeName(w)));
                sb.AppendLine(string.Format("     Processo={0} | Sessão={1} | Class={2}", proc, sessionId, cls));
            }
            if (n == 0) sb.AppendLine("(nenhuma janela de topo encontrada)");
            return sb.ToString();
        }

        /// <summary>
        /// A janela do receiver Citrix é um bitmap remoto: UI Automation não alcança
        /// os controles do ARIA a partir do cliente.
        /// </summary>
        public static bool IsCitrixShell(AutomationElement window, out string processName)
        {
            processName = "";
            try
            {
                Process p = Process.GetProcessById(window.Current.ProcessId);
                processName = p.ProcessName;
                return Contains(CitrixProcesses, p.ProcessName);
            }
            catch { return false; }
        }

        // ---------- localização ----------

        private AutomationElement FindGrid(AutomationElement window)
        {
            if (!string.IsNullOrEmpty(GridAutomationId))
            {
                AutomationElement g = window.FindFirst(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.AutomationIdProperty, GridAutomationId));
                if (g != null) return g;
                Log("ATN", string.Format(
                    "Grade com AutomationId '{0}' não encontrada; usando heurística.", GridAutomationId));
            }

            ControlType[] types = new ControlType[]
            {
                ControlType.DataGrid, ControlType.Table, ControlType.List, ControlType.Tree
            };
            foreach (ControlType t in types)
            {
                AutomationElementCollection found = window.FindAll(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, t));
                foreach (AutomationElement g in found)
                {
                    if (AllDescendants(g).Count > 0) return g;
                }
            }
            return null;
        }

        private class Hit
        {
            public AutomationElement Element;
            public string Name;
            public string Type;
            public int Priority;
        }

        /// <summary>Elemento já lido: evita ida e volta cross-process a cada consulta.</summary>
        private class ElemInfo
        {
            public AutomationElement E;
            public string Name;
            public string NormName;
            public string Type;
            // Células de grade do ARIA (Janus) guardam o texto no Value, não no Name.
            public string Value;
            public string NormValue;
        }

        /// <summary>
        /// Lê Name, ControlType e Value da subárvore numa passada, com TEMPO MÁXIMO.
        /// Medido em 18/09 (1212 elementos WinForms): FindAll com cache 38 s,
        /// TreeWalker com cache 16–19 s. Não dá para interromper um FindAll; o
        /// TreeWalker dá — estourou o orçamento, devolve o que leu e marca truncated.
        /// </summary>
        private static List<ElemInfo> Snapshot(AutomationElement scope, int budgetMs, out bool truncated)
        {
            List<ElemInfo> list = new List<ElemInfo>();
            List<AutomationElement> all = new List<AutomationElement>();
            truncated = false;
            DateTime deadline = DateTime.Now.AddMilliseconds(budgetMs);

            CacheRequest cr = new CacheRequest();
            cr.Add(AutomationElement.NameProperty);
            cr.Add(AutomationElement.ControlTypeProperty);
            cr.Add(ValuePattern.ValueProperty);
            cr.TreeScope = TreeScope.Element;

            TreeWalker walker = TreeWalker.ControlViewWalker;
            Stack<AutomationElement> stack = new Stack<AutomationElement>();
            stack.Push(scope);
            try
            {
                while (stack.Count > 0)
                {
                    if (DateTime.Now > deadline) { truncated = true; break; }
                    AutomationElement node = stack.Pop();
                    AutomationElement child = walker.GetFirstChild(node, cr);
                    while (child != null)
                    {
                        all.Add(child);
                        stack.Push(child);
                        child = walker.GetNextSibling(child, cr);
                    }
                }
            }
            catch { truncated = true; }

            foreach (AutomationElement e in all)
            {
                string name, type;
                try { name = e.Cached.Name ?? ""; }
                catch { name = SafeName(e); }
                try { type = e.Cached.ControlType.ProgrammaticName.Replace("ControlType.", ""); }
                catch { type = TypeName(e); }

                string value = ReadValue(e, true);

                list.Add(new ElemInfo
                {
                    E = e, Name = name, NormName = Norm(name), Type = type,
                    Value = value, NormValue = Norm(value)
                });
            }
            return list;
        }

        private static List<Hit> FindTaskHits(List<ElemInfo> snap, string taskName)
        {
            string target = TaskKey(taskName);   // "Preparação de PD" == "Preparação PD"
            List<Hit> hits = new List<Hit>();

            foreach (ElemInfo info in snap)
            {
                // Casa pelo Name ou, nas grades Janus, pelo Value da célula.
                string shown = info.Name;
                string n = TaskKey(info.Name);
                if (!Matches(n, target, shown.Length))
                {
                    shown = info.Value;
                    n = TaskKey(info.Value);
                    if (!Matches(n, target, shown.Length)) continue;
                }

                bool exact = (n == target);
                bool isRow = Contains(RowTypes, info.Type) || info.Type == "Custom";

                int priority = 3;
                if (exact && isRow) priority = 0;
                else if (exact) priority = 1;
                else if (isRow) priority = 2;

                hits.Add(new Hit { Element = info.E, Name = shown, Type = info.Type, Priority = priority });
            }
            hits.Sort(delegate(Hit a, Hit b) { return a.Priority.CompareTo(b.Priority); });
            return hits;
        }

        /// <summary>
        /// Procura o ID ou o nome do paciente no título e nos textos da janela.
        /// </summary>
        private static bool FindPatientEvidence(AutomationElement window, List<ElemInfo> snap,
                                                string[] tokens, out string evidence)
        {
            evidence = "";

            string title = SafeName(window);
            string titleNorm = Norm(title);
            for (int i = 0; i < tokens.Length; i++)
            {
                if (tokens[i].Length == 0) continue;
                if (titleNorm.Contains(Norm(tokens[i])))
                {
                    evidence = title;
                    return true;
                }
            }

            foreach (ElemInfo info in snap)
            {
                if (info.Name.Length == 0 || info.Name.Length > MaxTaskNameLength) continue;
                for (int i = 0; i < tokens.Length; i++)
                {
                    if (tokens[i].Length == 0) continue;
                    if (info.NormName.Contains(Norm(tokens[i])))
                    {
                        evidence = info.Name;
                        return true;
                    }
                }
            }
            return false;
        }

        private static bool Matches(string normText, string normTarget, int rawLength)
        {
            if (rawLength == 0 || rawLength > MaxTaskNameLength) return false;
            return normText == normTarget || normText.Contains(normTarget);
        }

        // ---------- status da atividade ----------

        /// <summary>
        /// Status conhecidos (legenda do Care Path + combo da Caixa de diálogo
        /// Tarefa + inglês). Texto de status fora desta lista = "não identificado",
        /// e a linha NÃO vira candidata.
        /// </summary>
        public static readonly string[] KnownStatuses = new string[]
        {
            "Pendente", "Disponível", "Em Andamento", "Parcialmente Concluído", "Concluído",
            "Cancelado", "Quase Expirado", "Vencido", "Não Programado", "Decisão", "Abrir",
            "Open", "Pending", "Available", "In Progress", "Completed", "Cancelled", "Canceled", "Overdue"
        };

        /// <summary>Atividades fechadas: nunca são assumidas (pedido do usuário, 18/09).</summary>
        public static readonly string[] ClosedStatuses = new string[]
        {
            "Concluído", "Cancelado", "Completed", "Cancelled", "Canceled"
        };

        /// <summary>
        /// Fechada = texto COMEÇA com um status fechado. O ARIA tem variações, ex.
        /// "Concluído manualmente" (despejo de 18/09) — igualdade exata não pega.
        /// </summary>
        public static bool IsClosedStatus(string status)
        {
            string n = Norm(status);
            if (n.Length == 0) return false;
            for (int i = 0; i < ClosedStatuses.Length; i++)
                if (n.StartsWith(Norm(ClosedStatuses[i]))) return true;
            return false;
        }

        // ---------- grade da aba de lista ----------

        /// <summary>Name da grade de atividades (o AutomationId dela é um HWND, muda a cada sessão).</summary>
        public const string ListGridName = "m_dgTemplateViewer";

        private static readonly System.Text.RegularExpressions.Regex RowNameRx =
            new System.Text.RegularExpressions.Regex(@"^Row(\d+)$");

        public static bool IsOwnerName(string text, string[] owners)
        {
            string n = Norm(text);
            if (n.Length == 0) return false;
            for (int i = 0; i < owners.Length; i++)
                if (Norm(owners[i]) == n) return true;
            return false;
        }

        /// <summary>
        /// Lê as linhas da grade DE TRÁS PARA FRENTE — a lista é cronológica, as
        /// pendentes do tratamento atual ficam no fim — com orçamento de tempo.
        /// Por linha, uma única chamada traz as células (Name + Value em cache).
        /// </summary>
        public static List<ListRow> ReadRowsFromEnd(AutomationElement grid, int budgetMs, int recentDays,
                                                    out int totalRows, out bool complete, out bool cutoff)
        {
            List<ListRow> result = new List<ListRow>();
            totalRows = 0;
            complete = false;
            cutoff = false;
            int olderInARow = 0;
            DateTime deadline = DateTime.Now.AddMilliseconds(budgetMs);

            CacheRequest crName = new CacheRequest();
            crName.Add(AutomationElement.NameProperty);
            crName.TreeScope = TreeScope.Element;

            CacheRequest crCell = new CacheRequest();
            crCell.Add(AutomationElement.NameProperty);
            crCell.Add(ValuePattern.ValueProperty);
            crCell.TreeScope = TreeScope.Element;

            // Anda de trás para frente pelos irmãos a partir do ÚLTIMO filho da grade:
            // não enumera a lista inteira (anos de linhas) — só o que lê.
            TreeWalker walker = TreeWalker.ControlViewWalker;
            AutomationElement cur;
            try { cur = walker.GetLastChild(grid, crName); }
            catch { cur = null; }

            while (cur != null)
            {
                if (DateTime.Now > deadline) return result;   // complete = false

                string n;
                try { n = cur.Cached.Name ?? ""; }
                catch { n = SafeName(cur); }
                System.Text.RegularExpressions.Match m = RowNameRx.Match(n);
                ListRow lr = null;
                if (m.Success)
                {
                    totalRows++;
                    lr = ReadRow(cur, int.Parse(m.Groups[1].Value), crCell);
                    if (lr != null) result.Add(lr);
                }

                AutomationElement prev;
                try { prev = walker.GetPreviousSibling(cur, crName); }
                catch { prev = null; }
                if (!m.Success) { cur = prev; continue; }   // barra de rolagem, cabeçalho
                cur = prev;

                // Recorte por data: a lista é cronológica; 3 linhas seguidas mais antigas
                // que o recorte = já passou do tratamento atual (tolera pequena desordem).
                if (lr != null && recentDays > 0 && IsOlderThan(lr.Date, recentDays))
                {
                    if (++olderInARow >= 3) { cutoff = true; complete = true; return result; }
                }
                else olderInARow = 0;
            }
            complete = true;
            return result;
        }

        private static ListRow ReadRow(AutomationElement row, int index, CacheRequest crCell)
        {
            ListRow lr = new ListRow();
            lr.Index = index;
            lr.Row = row;
            AutomationElementCollection cells;
            try
            {
                using (crCell.Activate())
                    cells = row.FindAll(TreeScope.Children, Condition.TrueCondition);
            }
            catch { return null; }

            foreach (AutomationElement c in cells)
            {
                string name;
                try { name = c.Cached.Name ?? ""; }
                catch { name = SafeName(c); }
                int us = name.IndexOf('_');
                if (us < 0) continue;
                string col = name.Substring(us + 1);
                string val = ReadValue(c, true);

                if (col == "colActivityCode") lr.Activity = val;
                else if (col == "colStatus") lr.Status = val;
                else if (col == "colDate") lr.Date = val;
                else if (col == "colOwner") lr.Owner = val;
                else if (col == "colDuration") lr.ClickCell = c;
            }
            return lr;
        }

        /// <summary>Data da linha (dd/MM/yyyy) anterior a hoje − dias? Data ilegível = não.</summary>
        private static bool IsOlderThan(string date, int days)
        {
            DateTime d;
            if (!DateTime.TryParseExact(TaskDialogOwner.DatePart(date), "dd/MM/yyyy",
                    CultureInfo.InvariantCulture, DateTimeStyles.None, out d)) return false;
            return d < DateTime.Today.AddDays(-days);
        }

        /// <summary>
        /// Relê uma linha já conhecida: primeiro pelo próprio elemento (instantâneo);
        /// se não existir mais ou não conferir atividade/data, procura de novo na grade.
        /// </summary>
        public static ListRow RereadRow(AutomationElement grid, ListRow known)
        {
            if (known.Row != null)
            {
                CacheRequest crCell = new CacheRequest();
                crCell.Add(AutomationElement.NameProperty);
                crCell.Add(ValuePattern.ValueProperty);
                crCell.TreeScope = TreeScope.Element;
                ListRow lr = ReadRow(known.Row, known.Index, crCell);
                if (lr != null && TaskKey(lr.Activity) == TaskKey(known.Activity) && lr.Date == known.Date)
                    return lr;
            }
            return RereadRow(grid, known.Index);
        }

        /// <summary>Relê a linha pelo índice (a grade pode ter sido recriada após salvar).</summary>
        public static ListRow RereadRow(AutomationElement grid, int index)
        {
            AutomationElement row;
            try
            {
                row = grid.FindFirst(TreeScope.Children,
                    new PropertyCondition(AutomationElement.NameProperty, "Row" + index));
            }
            catch { return null; }
            if (row == null) return null;

            CacheRequest crCell = new CacheRequest();
            crCell.Add(AutomationElement.NameProperty);
            crCell.Add(ValuePattern.ValueProperty);
            crCell.TreeScope = TreeScope.Element;
            return ReadRow(row, index, crCell);
        }

        /// <summary>
        /// Monta o plano a partir das linhas: por tarefa, as pendentes (status que
        /// não começa com Concluído/Cancelado). Nome EXATO via TaskKey.
        /// </summary>
        private void PlanFromRows(List<ListRow> rows, bool complete, string[] tasks, string[] owners)
        {
            foreach (string task in tasks)
            {
                string target = TaskKey(task);
                List<ListRow> matches = new List<ListRow>();
                foreach (ListRow r in rows)
                    if (TaskKey(r.Activity) == target) matches.Add(r);

                // As linhas vêm do fim para o começo: as mais recentes primeiro.
                // Status variado é o normal no Care Path — concluída/cancelada fica de
                // fora; "em andamento", "pendente", "parcialmente concluído" entram.
                // Status ILEGÍVEL (no Citrix a coluna às vezes só desenha o ícone)
                // também entra: o status de verdade é lido no diálogo, antes de gravar.
                List<ListRow> pending = new List<ListRow>();
                int closed = 0, noStatus = 0;
                foreach (ListRow r in matches)
                {
                    if (IsClosedStatus(r.Status)) closed++;
                    else
                    {
                        if (Norm(r.Status).Length == 0) noStatus++;
                        pending.Add(r);
                    }
                }

                string detail = string.Format("{0} linha(s) lida(s): {1} pendente(s), {2} fechada(s){3}",
                    matches.Count, pending.Count, closed,
                    noStatus > 0 ? ", " + noStatus + " com status ilegível (conferido no diálogo)" : "");

                if (pending.Count > 0)
                {
                    // Mais de uma pendente da mesma atividade (retratamento, atividade
                    // repetida no fluxo): assume TODAS as recentes, cada uma conferida
                    // no diálogo antes de gravar. Acima do teto, o usuário decide.
                    int take = Math.Min(pending.Count, MaxPendingPerTask);
                    if (pending.Count > take)
                    {
                        Log("ATN", string.Format("{0}: {1} → {2} pendentes, mais que o teto de {3}; nenhuma assumida, escolha pelo duplo clique + script.",
                            task, detail, pending.Count, MaxPendingPerTask));
                        _result.Ambiguous.Add(task);
                        continue;
                    }
                    if (take > 1)
                        Log("INFO", string.Format("{0}: {1} → {2} pendentes; todas serão assumidas (da mais recente para a mais antiga).",
                            task, detail, take));

                    for (int i = 0; i < take; i++)
                    {
                        ListRow p = pending[i];
                        TaskCandidate cand = new TaskCandidate { Task = task, Status = p.Status, ListRow = p, Row = p.Row };
                        string what = string.Format("{0} — linha de {1}, status '{2}', dono atual '{3}'",
                            detail, p.Date, p.Status.Length > 0 ? p.Status : "(não lido na lista)", p.Owner);
                        if (IsOwnerName(p.Owner, owners))
                        {
                            Log("OK", string.Format("{0}: {1} → você JÁ é o proprietário.", task, what));
                            _result.AlreadyMine.Add(cand);
                        }
                        else
                        {
                            Log("OK", string.Format("{0}: {1} → será assumida.", task, what));
                            _result.Ready.Add(cand);
                        }
                    }
                }
                else if (matches.Count > 0)
                {
                    Log("INFO", string.Format("{0}: {1} → nenhuma pendente.", task, detail));
                    _result.NothingPending.Add(task);
                }
                else if (!complete)
                {
                    Log("ATN", string.Format("{0}: não está nas linhas lidas — NÃO VERIFICADA (leitura parcial).", task));
                    _result.NotChecked.Add(task);
                }
                else if (IsOptional(task))
                {
                    Log("INFO", string.Format("{0}: não existe neste Care Path — não se aplica.", task));
                    _result.NotApplicable++;
                    _result.NotApplicableTasks.Add(task);
                }
                else
                {
                    Log("ATN", string.Format("{0}: obrigatória, não encontrada na lista.", task));
                    _result.NotFound++;
                    _result.NotFoundTasks.Add(task);
                }
            }
        }

        private static string AsKnownStatus(string text)
        {
            string n = Norm(text);
            if (n.Length == 0) return null;
            for (int i = 0; i < KnownStatuses.Length; i++)
                if (Norm(KnownStatuses[i]) == n) return KnownStatuses[i];
            return null;
        }

        /// <summary>
        /// Sobe a partir da célula com o nome da tarefa até o menor ancestral que
        /// contenha UM status conhecido — a linha. Se um nível já tiver dois status
        /// diferentes, ele abrange várias linhas: para e devolve "não identificado".
        /// </summary>
        private static AutomationElement FindRowWithStatus(AutomationElement cell, out string status)
        {
            status = "";
            TreeWalker walker = TreeWalker.ControlViewWalker;
            AutomationElement current = cell;
            for (int level = 0; level < 5; level++)
            {
                try { current = walker.GetParent(current); }
                catch { return null; }
                if (current == null || TypeName(current) == "Window") return null;

                // Contagem LIMITADA: FindAll no ancestral errado leria a grade inteira
                // (anos de atividades) — foi o que travou o Eclipse com a V1.8.
                List<AutomationElement> desc = BoundedDescendants(current, MaxRowElements);
                if (desc == null) return null;   // passou do limite: já não é uma linha

                string found = null;
                foreach (AutomationElement d in desc)
                {
                    string s = AsKnownStatus(SafeName(d));
                    if (s == null) s = AsKnownStatus(ReadValue(d, false));
                    if (s == null) continue;
                    if (found == null) found = s;
                    else if (Norm(found) != Norm(s)) return null;   // várias linhas
                }
                if (found != null)
                {
                    status = found;
                    return current;
                }
            }
            return null;
        }

        // ---------- escrita ----------

        /// <summary>
        /// Variantes do nome do usuário, da mais provável para a menos: o ARIA
        /// costuma esperar o login sem domínio, não "DOMINIO\login".
        /// </summary>
        public static string[] OwnerVariants(string id, string displayName)
        {
            List<string> v = new List<string>();

            if (!string.IsNullOrEmpty(id))
            {
                int slash = id.LastIndexOf('\\');
                if (slash >= 0 && slash < id.Length - 1) v.Add(id.Substring(slash + 1)); // sem domínio
                v.Add(id);                                                                // como veio
            }
            if (!string.IsNullOrEmpty(displayName) && !v.Contains(displayName)) v.Add(displayName);
            if (v.Count == 0) v.Add(Environment.UserName);
            return v.ToArray();
        }

        // ---------- execução ----------

        /// <summary>
        /// Lê o Care Path e monta o PLANO: para cada tarefa, as linhas pendentes
        /// (nem concluídas nem canceladas). Só leitura — nada é alterado; a
        /// atribuição em si é feita pelo TaskDialogOwner.
        /// </summary>
        public OwnerResult Run(string[] owners, string[] tasks)
        {
            _result = new OwnerResult();
            if (tasks == null || tasks.Length == 0) tasks = DefaultTasks;

            Log("INFO", string.Format("Plano (só leitura) | Proprietário: '{0}' (variantes: {1})",
                owners[0], string.Join(", ", owners)));

            List<AutomationElement> candidates = FindCandidateWindows();
            if (candidates.Count == 0)
            {
                Log("FAIL", string.Format(
                    "Nenhuma janela do ARIA (processo {0}) encontrada após {1}s.",
                    string.Join(" / ", ProcessNames), TimeoutSeconds));
                Log("ATN", "Abra o ARIA na MESMA sessão do Eclipse e use o diagnóstico de janelas.");
                return _result;
            }
            _result.WindowFound = true;
            Log("OK", string.Format("{0} janela(s) do ARIA nesta sessão.", candidates.Count));

            // Escolhe a janela que mostra o paciente certo E contém as tarefas: o Care
            // Path pode estar na janela do paciente ou na tela inicial do usuário.
            AutomationElement window = null;
            List<ElemInfo> snap = null;
            int scopedWindows = 0;   // janelas em que o contêiner do Care Path existe

            foreach (AutomationElement cand in candidates)
            {
                string title = SafeName(cand);
                Log("INFO", string.Format("Examinando: \"{0}\"", Shorten(title, 70)));

                string procName;
                if (IsCitrixShell(cand, out procName))
                {
                    _result.CitrixBlocked = true;
                    Log("FAIL", string.Format(
                        "Janela do processo Citrix '{0}': UI Automation não alcança os controles daqui.", procName));
                    return _result;
                }

                // Com GridAutomationId configurado, lê só a grade (mais rápido e preciso);
                // senão lê a janela inteira.
                AutomationElement root = cand;

                // Só o contêiner do Care Path: fora dele há diálogos abertos cujos
                // combos listam todas as atividades (falso positivo).
                if (!string.IsNullOrEmpty(ScopeAutomationId))
                {
                    AutomationElement scope = FastFind(cand, ScopeAutomationId, null, false)
                                              ?? FindByAutomationId(cand, ScopeAutomationId);
                    if (scope == null)
                    {
                        Log("ATN", string.Format("  sem '{0}' nesta janela — ignorada.", ScopeAutomationId));
                        continue;
                    }
                    root = scope;
                    scopedWindows++;

                    if (!string.IsNullOrEmpty(TabToActivate))
                    {
                        if (FastFind(root, null, ListGridName, true) != null)
                        {
                            Log("OK", string.Format("  aba '{0}' já estava ativa.", TabToActivate));
                        }
                        else
                        {
                            // Abas = filhas DIRETAS do TabControl: não varre o conteúdo das páginas
                            // (a aba Visual tem centenas de ícones).
                            string how;
                            AutomationElement tabCtl = FastFind(root, TabControlAutomationId, null, false);
                            bool activated = tabCtl != null
                                ? ActivateTab(tabCtl, TabToActivate, TreeScope.Children, out how)
                                : ActivateTab(root, TabToActivate, TreeScope.Descendants, out how);
                            if (activated)
                            {
                                Log("OK", string.Format("  aba '{0}' ativada ({1}).", TabToActivate, how));
                                DateTime tabLimit = DateTime.Now.AddMilliseconds(TabWaitMs);
                                while (DateTime.Now < tabLimit && FastFind(root, null, ListGridName, true) == null)
                                    Thread.Sleep(100);
                            }
                            else
                            {
                                Log("ATN", string.Format("  aba '{0}': {1}.", TabToActivate, how));
                            }
                        }
                    }

                    // Caminho rápido: a grade da aba de lista (estrutura conhecida).
                    AutomationElement grid = FastFind(root, null, ListGridName, true) ?? FindByName(root, ListGridName);
                    if (grid != null)
                    {
                        if (PatientTokens.Length > 0)
                        {
                            string ev;
                            if (!FindPatientEvidence(cand, new List<ElemInfo>(), PatientTokens, out ev))
                            {
                                Log("ATN", "  paciente do Eclipse não está no título desta janela — ignorada.");
                                continue;
                            }
                            _result.PatientEvidence = ev;
                            Log("OK", string.Format("  paciente confirmado: \"{0}\"", Shorten(ev, 70)));
                        }

                        int total;
                        bool complete;
                        DateTime tGrid = DateTime.Now;
                        bool cutoff;
                        List<ListRow> rows = ReadRowsFromEnd(grid, SnapshotBudgetMs, RecentDays, out total, out complete, out cutoff);
                        Log("INFO", string.Format("  grade '{0}': {1} de {2} linha(s) lidas (das mais recentes) em {3:0.0} s{4}.",
                            ListGridName, rows.Count, total, (DateTime.Now - tGrid).TotalSeconds,
                            complete ? (cutoff ? " — recorte: últimos " + RecentDays + " dias" : "") : " — PARCIAL (limite de tempo)"));

                        _result.ListMode = true;
                        _result.Grid = grid;
                        _result.TotalRows = total;
                        _result.RowsRead = rows.Count;
                        _result.ReadTruncated = !complete;
                        PlanFromRows(rows, complete, tasks, owners);

                        _result.Assigned = _result.Ready.Count;
                        Log("INFO", string.Format(
                            "PLANO — assumir: {0} | já é seu: {1} | ambíguas: {2} | sem pendente: {3} | obrigatórias ausentes: {4} | PD não se aplica: {5} | não verificadas: {6}",
                            _result.Ready.Count, _result.AlreadyMine.Count, _result.Ambiguous.Count,
                            _result.NothingPending.Count, _result.NotFound, _result.NotApplicable, _result.NotChecked.Count));
                        return _result;
                    }
                }

                if (!string.IsNullOrEmpty(GridAutomationId))
                {
                    AutomationElement grid = FindGrid(root);
                    if (grid != null)
                    {
                        root = grid;
                        Log("OK", string.Format("  grade <{0}> AutomationId='{1}'",
                            TypeName(grid), SafeAutomationId(grid)));
                    }
                }

                bool truncated;
                DateTime t0 = DateTime.Now;
                List<ElemInfo> candSnap = Snapshot(root, SnapshotBudgetMs, out truncated);
                Log("INFO", string.Format("  {0} elementos lidos em {1:0.0} s.",
                    candSnap.Count, (DateTime.Now - t0).TotalSeconds));
                if (truncated)
                    Log("ATN", string.Format("  leitura PARCIAL: limite de {0} s atingido (lista grande).",
                        SnapshotBudgetMs / 1000));

                // 1) paciente correto?
                if (PatientTokens.Length > 0)
                {
                    string evidence;
                    if (!FindPatientEvidence(cand, candSnap, PatientTokens, out evidence))
                    {
                        Log("ATN", "  paciente do Eclipse não aparece nesta janela — ignorada.");
                        continue;
                    }
                    _result.PatientEvidence = evidence;
                    Log("OK", string.Format("  paciente confirmado: \"{0}\"", Shorten(evidence, 70)));
                }

                // 2) contém alguma das tarefas?
                int present = 0;
                foreach (string t in tasks)
                    if (FindTaskHits(candSnap, t).Count > 0) present++;

                if (present == 0 && !truncated)
                {
                    Log("ATN", "  nenhuma das tarefas está nesta janela — ignorada.");
                    continue;
                }

                Log("OK", string.Format("  {0} de {1} tarefas presentes — janela escolhida.", present, tasks.Length));
                window = cand;
                snap = candSnap;
                _result.ReadTruncated = truncated;
                break;
            }

            if (window == null)
            {
                if (!string.IsNullOrEmpty(ScopeAutomationId) && scopedWindows == 0)
                {
                    Log("FAIL", "O Care Path não está aberto em nenhuma janela do ARIA.");
                    Log("ATN", "Abra o workspace de Care Path / Sequência de Tratamento do paciente.");
                    foreach (string t in tasks) { _result.NotFound++; _result.NotFoundTasks.Add(t); }
                }
                else if (_result.PatientEvidence.Length == 0 && PatientTokens.Length > 0)
                {
                    _result.PatientMismatch = true;
                    Log("FAIL", string.Format(
                        "Paciente do Eclipse ({0}) não localizado em nenhuma janela do ARIA.",
                        string.Join(" / ", PatientTokens)));
                    Log("ATN", "Abra o MESMO paciente no ARIA antes de rodar o script.");
                }
                else
                {
                    Log("FAIL", "Nenhuma janela do ARIA contém as tarefas procuradas.");
                    Log("ATN", "Abra o workspace de Care Path / atividades do paciente e rode de novo.");
                    foreach (string t in tasks) { _result.NotFound++; _result.NotFoundTasks.Add(t); }
                }
                return _result;
            }

            try { window.SetFocus(); }
            catch { Log("ATN", "Não foi possível focar a janela do ARIA."); }

            // Plano: para cada tarefa, as linhas com o nome EXATO e o status de cada uma.
            // Só leitura — abrir e atribuir é com o TaskDialogOwner.
            foreach (string task in tasks)
            {
                string target = TaskKey(task);
                List<AutomationElement> rows = new List<AutomationElement>();
                List<TaskCandidate> pending = new List<TaskCandidate>();
                int closed = 0, unknown = 0;

                foreach (Hit h in FindTaskHits(snap, task))
                {
                    if (TaskKey(h.Name) != target) continue;   // "Documentação X" não é "Documentação"

                    string status;
                    AutomationElement row = FindRowWithStatus(h.Element, out status);
                    if (row != null)
                    {
                        bool dup = false;
                        foreach (AutomationElement r in rows)
                            if (Automation.Compare(r, row)) { dup = true; break; }
                        if (dup) continue;
                        rows.Add(row);
                    }

                    if (status.Length == 0) unknown++;
                    else if (IsClosedStatus(status)) closed++;
                    else pending.Add(new TaskCandidate { Task = task, Status = status, Cell = h.Element, Row = row });
                }

                int total = pending.Count + closed + unknown;
                string detail = string.Format("{0} linha(s): {1} pendente(s){2}, {3} concluída/cancelada, {4} sem status identificado",
                    total, pending.Count, pending.Count > 0 ? " [" + JoinStatuses(pending) + "]" : "", closed, unknown);

                if (total == 0 && _result.ReadTruncated)
                {
                    // Pode estar na parte que não deu tempo de ler.
                    Log("ATN", string.Format("{0}: não encontrada na parte lida — NÃO VERIFICADA (leitura parcial).", task));
                    _result.NotChecked.Add(task);
                }
                else if (total == 0)
                {
                    if (IsOptional(task))
                    {
                        // Fluxo sem Portal Dosimetry: a tarefa simplesmente não existe.
                        Log("INFO", string.Format("{0}: não existe neste Care Path — não se aplica.", task));
                        _result.NotApplicable++;
                        _result.NotApplicableTasks.Add(task);
                    }
                    else
                    {
                        Log("ATN", string.Format("{0}: obrigatória, não encontrada na lista.", task));
                        _result.NotFound++;
                        _result.NotFoundTasks.Add(task);
                    }
                }
                else if (pending.Count == 1)
                {
                    Log("OK", string.Format("{0}: {1} → será assumida.", task, detail));
                    _result.Ready.Add(pending[0]);
                }
                else if (pending.Count > 1)
                {
                    // Não escolhe sozinho entre duas pendentes com o mesmo nome.
                    Log("ATN", string.Format("{0}: {1} → mais de uma pendente, você escolhe.", task, detail));
                    _result.Ambiguous.Add(task);
                }
                else
                {
                    Log("INFO", string.Format("{0}: {1} → nenhuma pendente.", task, detail));
                    _result.NothingPending.Add(task);
                }
            }

            _result.Assigned = _result.Ready.Count;
            Log("INFO", string.Format(
                "PLANO — assumir: {0} | ambíguas: {1} | sem pendente: {2} | obrigatórias ausentes: {3} | PD não se aplica: {4} | não verificadas: {5}{6}",
                _result.Ready.Count, _result.Ambiguous.Count, _result.NothingPending.Count,
                _result.NotFound, _result.NotApplicable, _result.NotChecked.Count,
                _result.ReadTruncated ? " (LEITURA PARCIAL)" : ""));
            return _result;
        }

        // ---------- diagnóstico ----------

        // Tetos do despejo: sem eles, a lista do Care Path (anos de atividades) é
        // lida elemento a elemento, ~8 chamadas entre processos cada — minutos.
        public static int DumpMaxNodes = 3000;
        public static int DumpBudgetMs = 30000;

        [ThreadStatic] private static int _dumpCount;
        [ThreadStatic] private static DateTime _dumpDeadline;
        [ThreadStatic] private static bool _dumpTruncated;

        /// <summary>Despejo da árvore de controles, para descobrir os AutomationId reais.</summary>
        public static string DumpTree(AutomationElement root, int maxDepth)
        {
            _dumpCount = 0;
            _dumpTruncated = false;
            _dumpDeadline = DateTime.Now.AddMilliseconds(DumpBudgetMs);

            StringBuilder sb = new StringBuilder();
            sb.AppendLine("# Árvore de UI Automation — " +
                DateTime.Now.ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture));
            sb.AppendLine("# Janela: " + SafeName(root));
            sb.AppendLine();
            DumpNode(root, 0, maxDepth, sb);
            if (_dumpTruncated)
                sb.AppendLine(string.Format("# ... TRUNCADO: teto de {0} elementos / {1} s atingido ({2} elementos escritos).",
                    DumpMaxNodes, DumpBudgetMs / 1000, _dumpCount));
            return sb.ToString();
        }

        private static void DumpNode(AutomationElement e, int level, int maxDepth, StringBuilder sb)
        {
            if (level > maxDepth) return;
            if (_dumpCount >= DumpMaxNodes || DateTime.Now > _dumpDeadline)
            {
                _dumpTruncated = true;
                return;
            }
            _dumpCount++;

            string patterns = "";
            try
            {
                AutomationPattern[] ps = e.GetSupportedPatterns();
                string[] names = new string[ps.Length];
                for (int i = 0; i < ps.Length; i++)
                    names[i] = ps[i].ProgrammaticName.Replace("PatternIdentifiers.Pattern", "");
                patterns = string.Join(",", names);
            }
            catch { }

            string cls = "";
            try { cls = e.Current.ClassName ?? ""; }
            catch { }

            // Value é onde as grades do ARIA guardam o texto das células.
            string value = patterns.Contains("Value") ? ReadValue(e, false) : "";
            string valuePart = "";
            if (value.Length > 0)
            {
                if (value.Length > 200) value = value.Substring(0, 200) + "…";
                valuePart = " Value=\"" + value.Replace("\r", " ").Replace("\n", " ") + "\"";
            }

            // Estado de checkbox (flag Proprietário) e de seleção de linha.
            if (patterns.Contains("Toggle"))
            {
                try
                {
                    object tp;
                    if (e.TryGetCurrentPattern(TogglePattern.Pattern, out tp))
                        valuePart += " Toggle=" + ((TogglePattern)tp).Current.ToggleState;
                }
                catch { }
            }
            if (patterns.Contains("SelectionItem"))
            {
                try
                {
                    object sp;
                    if (e.TryGetCurrentPattern(SelectionItemPattern.Pattern, out sp) &&
                        ((SelectionItemPattern)sp).Current.IsSelected)
                        valuePart += " Selected=True";
                }
                catch { }
            }

            sb.AppendLine(string.Format("{0}<{1}> Name=\"{2}\"{6} AutomationId=\"{3}\" Class=\"{4}\" Patterns=[{5}]",
                new string(' ', level * 2), TypeName(e), SafeName(e), SafeAutomationId(e), cls, patterns, valuePart));

            TreeWalker walker = TreeWalker.ControlViewWalker;
            AutomationElement child = null;
            try { child = walker.GetFirstChild(e); }
            catch { return; }

            while (child != null && !_dumpTruncated)
            {
                DumpNode(child, level + 1, maxDepth, sb);
                try { child = walker.GetNextSibling(child); }
                catch { break; }
            }
        }
    }

    /// <summary>Resultado do fluxo pela "Caixa de diálogo Tarefa".</summary>
    public class DialogOwnerResult
    {
        public bool DialogFound;
        public bool Verified;      // atividade e paciente conferidos no próprio diálogo
        public bool Changed;       // houve alteração gravada (OK nos dois diálogos)
        public bool AlreadyOwner;  // já era participante e proprietário — nada gravado
        public bool Failed;
        public bool Skipped;       // não era para assumir (ex.: concluída/cancelada) — não é erro
        public bool WrongRow;      // abriu outra atividade/data — pode ser a tela desalinhada
        public string Activity = "";
        public string Patient = "";
        public string Status = "";
        public readonly List<string> Log = new List<string>();
    }

    /// <summary>
    /// Torna o usuário proprietário da atividade aberta na "Caixa de diálogo Tarefa",
    /// repetindo o fluxo manual: Adicionar → escolher o usuário → "->" → marcar
    /// Proprietário → OK → OK. A equipe já presente (ex.: "Físicos - Radioterapia")
    /// NÃO é tocada. AutomationIds tirados dos despejos do ARIA de 18/09/2026.
    /// </summary>
    public class TaskDialogOwner
    {
        // Caixa de diálogo Tarefa
        private const string ID_TASK_DLG = "VDlgTask";
        private const string ID_ACTIVITY = "m_cmbActivity";
        private const string ID_PATIENT  = "m_cmbPatient";
        private const string ID_STATUS   = "m_cmbTaskStatus";   // Abrir / Em andamento / Concluído / Cancelado
        private const string ID_DATE     = "m_ccDate";
        private const string ID_ADD      = "m_btnAddAttendee";
        private const string ID_SAVE     = "m_btnSave";
        private const string ID_CANCEL   = "m_btnCancel";

        // Seleção de Recurso e Equipe
        private const string ID_RES_DLG      = "VDlgResourceProviderSelection";
        private const string ID_PROVIDERS    = "m_lvProvider";
        private const string ID_SEL_PROVIDER = "m_btnSelectProvider";
        private const string ID_SELECTED     = "m_lvSelectedResources";
        private const string ID_RES_OK       = "m_btnOk";
        private const string ID_RES_CANCEL   = "m_btnCancel";

        public string[] ProcessNames = new string[] { "VMS.SF.Host" };
        public string[] PatientTokens = new string[0];
        public string[] Tasks = OwnerAssigner.DefaultTasks;
        public int StepTimeoutMs = 10000;

        // Modo automático (diálogo aberto pelo script a partir de uma linha da lista):
        // o diálogo tem que ser DAQUELA linha — senão Cancelar.
        public string ExpectedActivity = null;
        public string ExpectedDate = null;     // dd/MM/yyyy
        public bool CloseOnReject = false;

        /// <summary>
        /// Deixa os diálogos que o script abre TRANSPARENTES assim que aparecem — o
        /// usuário não vê nada (pedido de 18/09). Mensagens postadas e UI Automation
        /// continuam funcionando numa janela transparente.
        /// </summary>
        public bool HideDialogs = false;

        // Janela principal do ARIA que estava minimizada antes do script (restaurada
        // para os cliques; volta a minimizar em RestoreAriaWindow).
        private IntPtr _ariaWasMinimized = IntPtr.Zero;

        private DialogOwnerResult _r;

        // Linhas registradas antes de existir um resultado (OpenListRow roda antes de
        // Run) — o próximo Run as adota, uma vez só.
        private readonly List<string> _carryLog = new List<string>();

        private void Log(string level, string message)
        {
            string line = string.Format("{0} [{1}] {2}",
                DateTime.Now.ToString("HH:mm:ss", CultureInfo.InvariantCulture), level, message);
            if (_r == null) _carryLog.Add(line);
            else _r.Log.Add(line);
        }

        // ---------- Win32 ----------
        // Testado contra ListView/botões WinForms (mesmos controles do ARIA):
        //  - InvokePattern num botão DENTRO de um modal aberto por outro Invoke não
        //    completa o clique; BM_CLICK via PostMessage completa.
        //  - TogglePattern no checkbox da ListView não muda o estado; Espaço
        //    POSTADO no HWND da lista (linha selecionada) muda — sem depender de foco.
        //  - Clique no checkbox por coordenada acertou a linha ERRADA (o retângulo do
        //    checkbox informado pela ListView não era confiável) — não usar.
        //  - Duplo clique na GRADE (abrir atividade) usa coordenada, mas só depois de
        //    FromPoint confirmar a célula, e o diálogo aberto é conferido depois.
        //  - Diálogo modal fechado fica oculto, não destruído: checar visibilidade.
        // No ARIA real (18/09) o foco de teclado não chegou à linha e o Cancelar não
        // fechou — não reproduzido no mock; por isso: ativar o diálogo antes de
        // clicar, fechamento escalonado e log detalhado de cada tentativa.
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool IsWindow(IntPtr hWnd);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool IsWindowVisible(IntPtr hWnd);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr hWnd);

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct POINT { public int X; public int Y; }
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool ClientToScreen(IntPtr hWnd, ref POINT p);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr SetThreadDpiAwarenessContext(IntPtr ctx);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr GetWindowDpiAwarenessContext(IntPtr hWnd);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam,
                                                        uint flags, uint timeoutMs, out UIntPtr result);

        // Citrix / uma tela só: a janela do ARIA pode estar parcialmente fora do
        // monitor (posição herdada de outra resolução) e outra janela pode cobrir a
        // lista. Nos dois casos o ponto da linha não é clicável, e sem conferir isso o
        // script só sabia dizer "a linha não ficou visível".
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr WindowFromPoint(POINT p);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr MonitorFromWindow(IntPtr hWnd, uint flags);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFO mi);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool SetWindowPos(IntPtr hWnd, IntPtr after, int x, int y, int cx, int cy, uint flags);
        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
        private static extern int GetClassName(IntPtr hWnd, StringBuilder name, int max);
        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
        private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int max);

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct MONITORINFO
        {
            public int cbSize; public RECT rcMonitor; public RECT rcWork; public uint dwFlags;
        }
        private const uint MONITOR_DEFAULTTONEAREST = 2;
        private const uint SWP_NOSIZE = 0x0001;
        private const uint SWP_NOZORDER = 0x0004;
        private const uint SWP_NOACTIVATE = 0x0010;
        private const uint SMTO_ABORTIFHUNG = 0x0002;

        private const uint WM_LBUTTONDOWN = 0x0201;
        private const uint WM_LBUTTONUP = 0x0202;
        private const uint WM_LBUTTONDBLCLK = 0x0203;
        private const uint WM_MOUSEWHEEL = 0x020A;
        private const int MK_LBUTTON = 0x0001;

        private const uint BM_CLICK = 0x00F5;
        private const uint WM_CLOSE = 0x0010;
        private const byte VK_SPACE = 0x20;
        private const uint WM_KEYDOWN = 0x0100;
        private const uint WM_KEYUP = 0x0101;

        private static IntPtr Hwnd(AutomationElement e)
        {
            if (e == null) return IntPtr.Zero;
            try { return new IntPtr(e.Current.NativeWindowHandle); }
            catch { return IntPtr.Zero; }
        }

        /// <summary>Diálogo existe e está visível.</summary>
        private static bool IsOpen(AutomationElement dialog)
        {
            if (dialog == null) return false;
            IntPtr h = Hwnd(dialog);
            if (h != IntPtr.Zero) return IsWindow(h) && IsWindowVisible(h);
            try { return !dialog.Current.IsOffscreen; }
            catch { return false; }
        }

        /// <summary>Traz o diálogo para a frente: BM_CLICK e foco falham em janela inativa.</summary>
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern int GetWindowLong(IntPtr hWnd, int index);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern int SetWindowLong(IntPtr hWnd, int index, int value);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool SetLayeredWindowAttributes(IntPtr hWnd, uint crKey, byte alpha, uint flags);
        private const int GWL_EXSTYLE = -20;
        private const int WS_EX_LAYERED = 0x80000;
        private const uint LWA_ALPHA = 0x2;

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr GetForegroundWindow();
        [System.Runtime.InteropServices.DllImport("kernel32.dll")]
        private static extern uint GetCurrentThreadId();
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool attach);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool BringWindowToTop(IntPtr hWnd);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool PeekMessage(out POINT_MSG msg, IntPtr hWnd, uint min, uint max, uint remove);
        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct POINT_MSG { public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam; public uint time; public int x; public int y; }

        public static IntPtr CurrentForeground() { return GetForegroundWindow(); }

        /// <summary>
        /// Devolve o foco à janela dada (o Eclipse) no fim: ativar os diálogos do ARIA
        /// para os cliques traz o ARIA para a frente. AttachThreadInput permite trocar
        /// o primeiro plano mesmo depois que outro processo o tomou.
        /// </summary>
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr GetAncestor(IntPtr hWnd, uint flags);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool IsIconic(IntPtr hWnd);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int cmd);
        private const uint GA_ROOT = 2;
        private const int SW_RESTORE = 9;
        private const int SW_MINIMIZE = 6;

        /// <summary>Traz a janela do ARIA que contém a grade para a frente (restaura se minimizada).</summary>
        private void BringAriaToFront(IntPtr hGrid)
        {
            IntPtr top = GetAncestor(hGrid, GA_ROOT);
            if (top == IntPtr.Zero) return;
            if (IsIconic(top))
            {
                ShowWindow(top, SW_RESTORE);
                _ariaWasMinimized = top;
                Thread.Sleep(300);   // redesenho após restaurar
            }
            if (GetForegroundWindow() != top) { RestoreForeground(top); Thread.Sleep(100); }
        }

        /// <summary>
        /// Põe a THREAD no mesmo modo de DPI da janela e devolve o contexto anterior
        /// (Zero = nada a desfazer). Sob Citrix a sessão pode ter escala diferente da
        /// do console; medir e clicar no espaço da janela evita a conversão errada
        /// (em 18/09, a 125%, o clique caía 7 linhas acima).
        /// </summary>
        private static IntPtr EnterWindowDpi(IntPtr hwnd)
        {
            try
            {
                IntPtr ctx = GetWindowDpiAwarenessContext(hwnd);
                if (ctx == IntPtr.Zero) return IntPtr.Zero;
                return SetThreadDpiAwarenessContext(ctx);
            }
            catch (EntryPointNotFoundException) { return IntPtr.Zero; }   // Windows sem DPI por thread
        }

        private static void LeaveWindowDpi(IntPtr previous)
        {
            if (previous == IntPtr.Zero) return;
            try { SetThreadDpiAwarenessContext(previous); }
            catch (EntryPointNotFoundException) { }
        }

        // Janela do ARIA movida para dentro da tela (devolvida ao lugar no fim).
        private IntPtr _ariaMoved = IntPtr.Zero;
        private RECT _ariaOldRect;

        /// <summary>Quanto a janela pode passar da área de trabalho sem valer a pena mover.</summary>
        private static readonly int OffScreenSlack = 48;

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool IsZoomed(IntPtr hWnd);

        /// <summary>
        /// A célula que vamos clicar está fora da área visível do monitor? Só nesse
        /// caso mexer na janela se justifica — mover o ARIA à toa quebra o clique.
        /// </summary>
        private static bool CellOffWorkArea(AutomationElement cell, IntPtr hGrid)
        {
            try
            {
                System.Windows.Rect r = cell.Current.BoundingRectangle;
                if (r.IsEmpty) return false;
                IntPtr top = GetAncestor(hGrid, GA_ROOT);
                MONITORINFO mi = new MONITORINFO();
                mi.cbSize = System.Runtime.InteropServices.Marshal.SizeOf(typeof(MONITORINFO));
                IntPtr mon = MonitorFromWindow(top, MONITOR_DEFAULTTONEAREST);
                if (mon == IntPtr.Zero || !GetMonitorInfo(mon, ref mi)) return false;
                double cx = r.Left + r.Width / 2, cy = r.Top + r.Height / 2;
                return cx < mi.rcWork.Left || cx > mi.rcWork.Right || cy < mi.rcWork.Top || cy > mi.rcWork.Bottom;
            }
            catch { return false; }
        }

        /// <summary>
        /// Citrix/uma tela só: parte da janela do ARIA pode estar fora do monitor — o
        /// que está fora não é desenhado, o FromPoint não confirma a linha e o clique
        /// nunca sai. Move a janela para dentro da área de trabalho SEM redimensionar;
        /// a posição original volta em RestoreAriaWindow.
        /// </summary>
        private void EnsureOnScreen(IntPtr hGrid)
        {
            if (_ariaMoved != IntPtr.Zero) return;
            IntPtr top = GetAncestor(hGrid, GA_ROOT);
            RECT w;
            if (top == IntPtr.Zero || !GetWindowRect(top, out w)) return;

            // Janela MAXIMIZADA já está na tela — e o retângulo dela passa da área de
            // trabalho pelas bordas invisíveis (medido: -8,-8 a +8,+8). Sem esta
            // guarda, mover uma janela maximizada desalinhava o ARIA inteiro e o
            // clique não abria mais a atividade (teste real de 22/09, V2.7).
            if (IsZoomed(top)) return;

            MONITORINFO mi = new MONITORINFO();
            mi.cbSize = System.Runtime.InteropServices.Marshal.SizeOf(typeof(MONITORINFO));
            IntPtr mon = MonitorFromWindow(top, MONITOR_DEFAULTTONEAREST);
            if (mon == IntPtr.Zero || !GetMonitorInfo(mon, ref mi)) return;

            // Folga: passar da borda por poucos pixels não atrapalha nada — mover a
            // janela é que atrapalha. Só vale a pena com um pedaço de verdade fora.
            int width = w.Right - w.Left, height = w.Bottom - w.Top;
            int nx = w.Left, ny = w.Top;
            if (w.Right > mi.rcWork.Right + OffScreenSlack) nx = Math.Max(mi.rcWork.Left, mi.rcWork.Right - width);
            if (nx < mi.rcWork.Left - OffScreenSlack) nx = mi.rcWork.Left;
            if (w.Bottom > mi.rcWork.Bottom + OffScreenSlack) ny = Math.Max(mi.rcWork.Top, mi.rcWork.Bottom - height);
            if (ny < mi.rcWork.Top - OffScreenSlack) ny = mi.rcWork.Top;
            if (nx == w.Left && ny == w.Top) return;

            if (SetWindowPos(top, IntPtr.Zero, nx, ny, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE))
            {
                _ariaMoved = top;
                _ariaOldRect = w;
                Log("ATN", string.Format(
                    "Janela do ARIA estava parcialmente fora da tela ({0},{1}) — movida para ({2},{3}); volta ao lugar no fim.",
                    w.Left, w.Top, nx, ny));
                Thread.Sleep(200);   // redesenho após mover
            }
        }

        /// <summary>
        /// Janela que está POR CIMA do ponto, quando não é a própria janela do ARIA
        /// ("" = nada por cima). Com uma tela só isso é o caso comum: o Eclipse, a
        /// barra do Citrix ou um pop-up cobrem a lista.
        /// </summary>
        private static string CoveringWindow(System.Windows.Point p, IntPtr hGrid)
        {
            POINT pt = new POINT();
            pt.X = (int)Math.Round(p.X);
            pt.Y = (int)Math.Round(p.Y);
            IntPtr h = WindowFromPoint(pt);
            if (h == IntPtr.Zero) return "ponto fora de qualquer janela (área visível da tela?)";
            if (h == hGrid) return null;

            IntPtr topHit = GetAncestor(h, GA_ROOT);
            IntPtr topGrid = GetAncestor(hGrid, GA_ROOT);
            if (topHit != IntPtr.Zero && topHit == topGrid) return null;   // outra parte do próprio ARIA

            StringBuilder title = new StringBuilder(160);
            GetWindowText(topHit != IntPtr.Zero ? topHit : h, title, 160);
            StringBuilder cls = new StringBuilder(128);
            GetClassName(h, cls, 128);
            string t = title.ToString().Trim();
            return t.Length > 0 ? t : cls.ToString();
        }

        /// <summary>Alguma janela cobre o centro desta célula? (null = não)</summary>
        private static string CoveringCell(AutomationElement cell, IntPtr hGrid)
        {
            try
            {
                System.Windows.Rect r = cell.Current.BoundingRectangle;
                if (r.IsEmpty) return null;
                return CoveringWindow(Center(r), hGrid);
            }
            catch { return null; }
        }

        /// <summary>
        /// Restaura as janelas do ARIA que estão minimizadas: minimizada, a janela não
        /// expõe o conteúdo (o Care Path "some" para a leitura — teste de 18/09). Devolve
        /// as que foram restauradas, para minimizar de novo no fim.
        /// </summary>
        public static List<IntPtr> RestoreMinimized(string[] processNames)
        {
            List<uint> pids = new List<uint>();
            foreach (string pn in processNames)
            {
                try { foreach (Process p in Process.GetProcessesByName(pn)) pids.Add((uint)p.Id); }
                catch { }
            }
            List<IntPtr> restored = new List<IntPtr>();
            EnumWindows(delegate(IntPtr h, IntPtr l)
            {
                uint pid;
                GetWindowThreadProcessId(h, out pid);
                if (pids.Contains(pid) && IsWindowVisible(h) && IsIconic(h))
                {
                    ShowWindow(h, SW_RESTORE);
                    restored.Add(h);
                }
                return true;
            }, IntPtr.Zero);
            if (restored.Count > 0) Thread.Sleep(800);   // redesenho após restaurar
            return restored;
        }

        public static void Minimize(List<IntPtr> windows)
        {
            if (windows == null) return;
            // IsWindow: a janela do paciente pode ter sido FECHADA no fim (CloseAriaWindow).
            foreach (IntPtr h in windows) if (IsWindow(h)) ShowWindow(h, SW_MINIMIZE);
        }

        /// <summary>
        /// Fecha a janela do ARIA que o script usou — a do paciente (pedido de
        /// 22/09: "a tela do ARIA precisa ser fechada ao final"). As outras janelas
        /// do ARIA e o próprio aplicativo continuam de pé. Não fecha se ainda houver
        /// diálogo do script aberto, e se o ARIA pedir confirmação a janela FICA como
        /// está — responder por ele seria decidir no lugar do usuário.
        /// Devolve null se fechou, ou o motivo de não ter fechado.
        /// </summary>
        public string CloseAriaWindow(AutomationElement grid)
        {
            IntPtr hGrid = Hwnd(grid);
            IntPtr top = hGrid != IntPtr.Zero ? GetAncestor(hGrid, GA_ROOT) : IntPtr.Zero;
            if (top == IntPtr.Zero || !IsWindow(top)) return "janela do ARIA não identificada";
            if (FindOpenTaskDialog() != null) return "ainda há uma Caixa de diálogo Tarefa aberta";

            PostMessage(top, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
            DateTime limit = DateTime.Now.AddMilliseconds(CloseWindowTimeoutMs);
            while (DateTime.Now < limit)
            {
                if (!IsWindow(top) || !IsWindowVisible(top))
                {
                    // Fechada: não há mais o que restaurar (posição/minimizar).
                    _ariaMoved = IntPtr.Zero;
                    _ariaWasMinimized = IntPtr.Zero;
                    return null;
                }
                Thread.Sleep(100);
            }
            return "o ARIA não fechou — pode estar pedindo confirmação na tela";
        }

        /// <summary>Espera pelo fechamento da janela do ARIA.</summary>
        public int CloseWindowTimeoutMs = 5000;

        /// <summary>
        /// Devolve a janela do ARIA como estava: posição original (se foi movida para
        /// dentro da tela) e minimizada de novo, se assim estava. Depois de
        /// CloseAriaWindow não faz nada — a janela não existe mais.
        /// </summary>
        public void RestoreAriaWindow()
        {
            if (_ariaMoved != IntPtr.Zero)
            {
                IntPtr prev = EnterWindowDpi(_ariaMoved);   // mover e medir no mesmo espaço
                try
                {
                    SetWindowPos(_ariaMoved, IntPtr.Zero, _ariaOldRect.Left, _ariaOldRect.Top, 0, 0,
                                 SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
                }
                finally { LeaveWindowDpi(prev); }
                _ariaMoved = IntPtr.Zero;
            }
            if (_ariaWasMinimized != IntPtr.Zero) ShowWindow(_ariaWasMinimized, SW_MINIMIZE);
            _ariaWasMinimized = IntPtr.Zero;
        }

        public static void RestoreForeground(IntPtr target)
        {
            if (target == IntPtr.Zero) return;
            try
            {
                IntPtr fg = GetForegroundWindow();
                if (fg == target) return;
                uint pid;
                uint fgThread = GetWindowThreadProcessId(fg, out pid);
                uint targetThread = GetWindowThreadProcessId(target, out pid);
                uint me = GetCurrentThreadId();
                POINT_MSG m;
                PeekMessage(out m, IntPtr.Zero, 0, 0, 0);   // garante fila de mensagens nesta thread
                // Liga a fila desta thread e a do Eclipse à do dono atual do primeiro plano.
                bool a1 = fgThread != 0 && fgThread != me && AttachThreadInput(me, fgThread, true);
                bool a2 = fgThread != 0 && targetThread != 0 && targetThread != fgThread && targetThread != me &&
                          AttachThreadInput(targetThread, fgThread, true);
                try
                {
                    BringWindowToTop(target);
                    SetForegroundWindow(target);
                }
                finally
                {
                    if (a2) AttachThreadInput(targetThread, fgThread, false);
                    if (a1) AttachThreadInput(me, fgThread, false);
                }
            }
            catch { }
        }

        /// <summary>Janela totalmente transparente (continua existindo e recebendo mensagens).</summary>
        private static void HideWindow(AutomationElement dialog)
        {
            IntPtr h = Hwnd(dialog);
            if (h == IntPtr.Zero) return;
            try
            {
                SetWindowLong(h, GWL_EXSTYLE, GetWindowLong(h, GWL_EXSTYLE) | WS_EX_LAYERED);
                SetLayeredWindowAttributes(h, 0, 0, LWA_ALPHA);
            }
            catch { }
        }

        private static void Activate(AutomationElement dialog)
        {
            IntPtr h = Hwnd(dialog);
            if (h != IntPtr.Zero) SetForegroundWindow(h);
            Thread.Sleep(80);
        }

        /// <summary>Clique em botão: BM_CLICK assíncrono; Invoke só se não houver HWND.</summary>
        private static void Click(AutomationElement button)
        {
            if (button == null) return;
            IntPtr h = Hwnd(button);
            if (h != IntPtr.Zero) PostMessage(h, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
            else InvokeAsync(button);
        }

        private static string Describe(AutomationElement e)
        {
            if (e == null) return "(nenhum)";
            try
            {
                string proc = "?";
                try { proc = Process.GetProcessById(e.Current.ProcessId).ProcessName; }
                catch { }
                return string.Format("<{0}> '{1}' id='{2}' processo={3}",
                    e.Current.ControlType.ProgrammaticName.Replace("ControlType.", ""),
                    SafeName(e).Trim(), SafeId(e), proc);
            }
            catch { return "(indisponível)"; }
        }

        /// <summary>
        /// Botão pelo AutomationId, só do próprio diálogo: a Seleção de Recurso é
        /// FILHA da Caixa de diálogo Tarefa e as duas têm "m_btnCancel"/"m_btnHelp".
        /// </summary>
        private static AutomationElement OwnById(AutomationElement dialog, string automationId)
        {
            TreeWalker walker = TreeWalker.ControlViewWalker;
            try
            {
                AutomationElementCollection all = dialog.FindAll(TreeScope.Descendants,
                    new PropertyCondition(AutomationElement.AutomationIdProperty, automationId));
                foreach (AutomationElement e in all)
                {
                    AutomationElement p = walker.GetParent(e);
                    while (p != null)
                    {
                        bool isWindow = false;
                        try { isWindow = p.Current.ControlType == ControlType.Window; }
                        catch { }
                        if (isWindow) break;
                        p = walker.GetParent(p);
                    }
                    if (p != null && Automation.Compare(p, dialog)) return e;
                }
            }
            catch { }
            return null;
        }

        // ---------- localização ----------

        private static Condition WindowWithId(string automationId)
        {
            return new AndCondition(
                new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Window),
                new PropertyCondition(AutomationElement.AutomationIdProperty, automationId));
        }

        private bool IsTargetProcess(AutomationElement w)
        {
            try
            {
                string proc = Process.GetProcessById(w.Current.ProcessId).ProcessName;
                for (int i = 0; i < ProcessNames.Length; i++)
                    if (string.Equals(proc, ProcessNames[i], StringComparison.OrdinalIgnoreCase)) return true;
            }
            catch { }
            return false;
        }

        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lParam);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool EnumChildWindows(IntPtr parent, EnumWindowsProc cb, IntPtr lParam);

        /// <summary>
        /// Vários controles do diálogo de uma vez, pelas janelas-filhas (os controles
        /// WinForms do ARIA são HWNDs; AutomationId = Name do controle). Antes era uma
        /// busca na árvore de acessibilidade por campo (~2–3 s por diálogo no ARIA real).
        /// Diálogos "owned" (a Seleção de Recurso) não são filhos — não se misturam.
        /// </summary>
        private static Dictionary<string, AutomationElement> FindIds(AutomationElement dialog, params string[] ids)
        {
            Dictionary<string, AutomationElement> map = new Dictionary<string, AutomationElement>();
            List<string> wanted = new List<string>(ids);
            IntPtr h = Hwnd(dialog);
            if (h != IntPtr.Zero)
            {
                try
                {
                    EnumChildWindows(h, delegate(IntPtr c, IntPtr l)
                    {
                        try
                        {
                            AutomationElement e = AutomationElement.FromHandle(c);
                            string id = SafeId(e);
                            if (wanted.Contains(id) && !map.ContainsKey(id)) map[id] = e;
                        }
                        catch { }
                        return map.Count < wanted.Count;   // para quando achar todos
                    }, IntPtr.Zero);
                }
                catch { }
            }
            // Reserva: busca na árvore só para o que faltou.
            foreach (string id in ids)
                if (!map.ContainsKey(id))
                {
                    AutomationElement e = ById(dialog, id);
                    if (e != null) map[id] = e;
                }
            return map;
        }

        private static AutomationElement Get(Dictionary<string, AutomationElement> map, string id)
        {
            AutomationElement e;
            return map.TryGetValue(id, out e) ? e : null;
        }
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);

        /// <summary>
        /// Diálogo VISÍVEL com o AutomationId dado. Os diálogos do ARIA são janelas
        /// próprias (owned) do processo: EnumWindows acha na hora. A versão antiga
        /// varria os descendentes da janela principal — com a grade do Care Path isso
        /// levava ~1 min para abrir e 34 s para fechar no ARIA real (18/09).
        /// </summary>
        private AutomationElement FindDialog(string automationId, AutomationElement hint)
        {
            // PIDs do ARIA
            List<uint> pids = new List<uint>();
            for (int i = 0; i < ProcessNames.Length; i++)
            {
                try
                {
                    foreach (Process p in Process.GetProcessesByName(ProcessNames[i])) pids.Add((uint)p.Id);
                }
                catch { }
            }

            AutomationElement found = null;
            try
            {
                EnumWindows(delegate(IntPtr h, IntPtr l)
                {
                    if (!IsWindowVisible(h)) return true;
                    uint pid;
                    GetWindowThreadProcessId(h, out pid);
                    if (!pids.Contains(pid)) return true;
                    try
                    {
                        AutomationElement e = AutomationElement.FromHandle(h);
                        if (e != null && SafeId(e) == automationId) { found = e; return false; }
                    }
                    catch { }
                    return true;
                }, IntPtr.Zero);
            }
            catch { }
            if (found != null) return found;

            // Reserva barata: filho direto do 'hint' (sem varrer descendentes).
            try
            {
                if (hint != null)
                {
                    foreach (AutomationElement d in hint.FindAll(TreeScope.Children, WindowWithId(automationId)))
                        if (IsOpen(d)) return d;
                }
            }
            catch { }
            return null;
        }

        public AutomationElement FindOpenTaskDialog()
        {
            return FindDialog(ID_TASK_DLG, null);
        }

        // ---------- abrir linha da grade (modo automático) ----------

        /// <summary>
        /// Ponto de tela → coordenada-cliente da janela-alvo. Chamar com a THREAD no
        /// mesmo modo de DPI da janela (ver OpenListRow): aí UIA, FromPoint,
        /// ClientToScreen e o clique postado ficam todos no espaço dela, sem conversão.
        /// Medido em 18/09 (monitor a 125%, janela DPI-unaware): convertendo "na mão"
        /// a partir de coordenadas físicas o clique caía 7 linhas acima; com o modo
        /// casado acertou 3/3 linhas (inclusive após rolagem).
        /// </summary>
        private static bool ToTargetClient(IntPtr hwnd, double sx, double sy, out int cx, out int cy)
        {
            cx = 0; cy = 0;
            POINT o = new POINT();
            if (!ClientToScreen(hwnd, ref o)) return false;
            cx = (int)Math.Round(sx - o.X);
            cy = (int)Math.Round(sy - o.Y);
            return true;
        }

        private static System.Windows.Point Center(System.Windows.Rect r)
        {
            return new System.Windows.Point(r.Left + r.Width / 2, r.Top + r.Height / 2);
        }

        /// <summary>"Row12_colDuration" → "Row12".</summary>
        private static string RowPrefix(string cellName)
        {
            if (string.IsNullOrEmpty(cellName)) return "";
            int i = cellName.IndexOf('_');
            return i > 0 ? cellName.Substring(0, i) : cellName;
        }

        /// <summary>
        /// O que está NA TELA no ponto pertence à MESMA LINHA da célula? Exigir o nome
        /// exato da célula abortava o clique à toa sob Citrix, onde o FromPoint às
        /// vezes devolve a linha ou um filho da célula (o redesenho é remoto). O que
        /// precisa estar certo é a LINHA — é ela que define a atividade aberta.
        /// </summary>
        private static bool HitIs(System.Windows.Point p, string cellName)
        {
            try
            {
                AutomationElement hit = AutomationElement.FromPoint(p);
                if (hit == null) return false;
                string n = SafeName(hit);
                if (n == cellName) return true;
                string row = RowPrefix(cellName);
                if (row.Length == 0 || n.Length == 0) return false;
                return n == row || n.StartsWith(row + "_", StringComparison.Ordinal);
            }
            catch { return false; }
        }

        /// <summary>
        /// Rola a grade até a célula ficar visível e sem nada por cima. Barra de
        /// rolagem da grade (botões "Line/Page Down/Up", como no despejo do ARIA);
        /// sem ela, roda do mouse postada. Desiste se a rolagem parar de surtir efeito.
        /// </summary>
        private bool ScrollIntoView(AutomationElement grid, AutomationElement cell, string cellName)
        {
            IntPtr hGrid = Hwnd(grid);
            double lastTop = double.NaN;
            int stuck = 0;

            for (int i = 0; i < 250; i++)
            {
                System.Windows.Rect gr, cr;
                try
                {
                    gr = grid.Current.BoundingRectangle;
                    cr = cell.Current.BoundingRectangle;
                }
                catch { return false; }

                if (!cr.IsEmpty && cr.Top >= gr.Top && cr.Bottom <= gr.Bottom && HitIs(Center(cr), cellName))
                    return true;

                // Acima da área visível (ou coberta pelo cabeçalho) → sobe; senão desce.
                bool up = !cr.IsEmpty && cr.Top < gr.Top + cr.Height * 1.5;
                bool far = cr.IsEmpty || Math.Abs(cr.Top - gr.Top) > gr.Height * 1.5;

                if (!cr.IsEmpty && !double.IsNaN(lastTop) && Math.Abs(cr.Top - lastTop) < 0.5)
                {
                    if (++stuck >= 4) return false;   // rolagem não está surtindo efeito
                }
                else stuck = 0;
                lastTop = cr.IsEmpty ? double.NaN : cr.Top;

                // Longe: vários degraus de roda de uma vez (~3 linhas cada).
                int steps = 1;
                if (far && !cr.IsEmpty && cr.Height > 0)
                    steps = Math.Max(1, Math.Min(10, (int)(Math.Abs(cr.Top - gr.Top) / (cr.Height * 3)) - 1));
                if (!ScrollStep(grid, hGrid, up, far, steps)) return false;
                Thread.Sleep(60);
            }
            return false;
        }

        private static bool ScrollStep(AutomationElement grid, IntPtr hGrid, bool up, bool far, int wheelSteps)
        {
            // 1) botões da barra de rolagem da própria grade. No ARIA a barra é o
            // PRIMEIRO filho da grade; olhar só ele evita varrer todas as linhas.
            try
            {
                AutomationElement bar = TreeWalker.ControlViewWalker.GetFirstChild(grid);
                if (bar != null && bar.Current.ControlType != ControlType.ScrollBar) bar = null;
                if (bar != null)
                {
                    string[] names = up
                        ? (far ? new string[] { "Page Up", "Line Up" } : new string[] { "Line Up" })
                        : (far ? new string[] { "Page Down", "Line Down" } : new string[] { "Line Down" });
                    foreach (string n in names)
                    {
                        AutomationElement b = bar.FindFirst(TreeScope.Children,
                            new PropertyCondition(AutomationElement.NameProperty, n));
                        object ip;
                        if (b != null && b.TryGetCurrentPattern(InvokePattern.Pattern, out ip))
                        {
                            ((InvokePattern)ip).Invoke();
                            return true;
                        }
                    }
                }
            }
            catch { }

            // 2) roda do mouse ENVIADA (síncrona) à grade. Postada não serve: as
            // consultas de posição via UIA são atendidas antes da fila de mensagens,
            // então a posição era lida com rolagens ainda pendentes e o clique caía em
            // outra linha (teste no mock de 18/09: abriu Row24 em vez de Row32).
            if (hGrid == IntPtr.Zero) return false;
            System.Windows.Rect gr = grid.Current.BoundingRectangle;
            int x = (int)(gr.Left + gr.Width / 2), y = (int)(gr.Top + gr.Height / 2);
            int delta = up ? 120 : -120;
            UIntPtr res;
            for (int i = 0; i < Math.Max(1, wheelSteps); i++)
                SendMessageTimeout(hGrid, WM_MOUSEWHEEL, new IntPtr(delta << 16),
                    new IntPtr((y << 16) | (x & 0xFFFF)), SMTO_ABORTIFHUNG, 2000, out res);
            return true;
        }

        /// <summary>
        /// Posição da célula estável (duas leituras iguais com intervalo) E confirmada
        /// por FromPoint — só então é seguro clicar.
        /// </summary>
        private static bool StableAndHit(AutomationElement cell, string cellName, out System.Windows.Point p)
        {
            p = new System.Windows.Point();
            try
            {
                System.Windows.Rect a = cell.Current.BoundingRectangle;
                Thread.Sleep(150);
                System.Windows.Rect b = cell.Current.BoundingRectangle;
                if (a.IsEmpty || b.IsEmpty || Math.Abs(a.Top - b.Top) > 0.5 || Math.Abs(a.Left - b.Left) > 0.5)
                    return false;
                p = Center(b);
                return HitIs(p, cellName);
            }
            catch { return false; }
        }

        /// <summary>
        /// Abre a "Caixa de diálogo Tarefa" da linha com duplo clique na célula sem
        /// botão (colDuration). Só clica se FromPoint confirmar que o ponto é aquela
        /// célula. Devolve null e o diálogo aberto, ou a mensagem de erro.
        /// </summary>
        public string OpenListRow(AutomationElement grid, ListRow row, out AutomationElement taskDlg)
        {
            taskDlg = null;
            _r = null;   // o resultado anterior já foi entregue: o que for registrado aqui é do próximo
            if (FindOpenTaskDialog() != null) return "já existe uma Caixa de diálogo Tarefa aberta";
            if (row.ClickCell == null) return "linha sem a célula de clique (colDuration)";

            IntPtr hGrid = Hwnd(grid);
            if (hGrid == IntPtr.Zero) return "grade sem HWND";

            // Thread no MESMO modo de DPI da grade: medir, confirmar e clicar no espaço
            // de coordenadas dela (ver ToTargetClient).
            IntPtr prevCtx = EnterWindowDpi(hGrid);

            try
            {
                // A grade precisa estar VISÍVEL na tela: FromPoint confere o que está de
                // fato ali. Com o Eclipse por cima (ou o ARIA minimizado) a conferência
                // falharia — traz o ARIA à frente (e restaura se estiver minimizado).
                BringAriaToFront(hGrid);

                string cellName = SafeName(row.ClickCell);
                System.Windows.Point p = new System.Windows.Point();
                bool ready = false;
                string covering = null;
                bool scrolled = true;
                for (int attempt = 0; attempt < 4 && !ready; attempt++)
                {
                    if (attempt > 0)
                    {
                        // Uma tela só: o Eclipse, a barra do Citrix ou um pop-up voltaram
                        // para cima da lista — reativa o ARIA e tenta de novo antes de
                        // desistir (antes, uma cobertura passageira já era erro).
                        BringAriaToFront(hGrid);
                        // Mover a janela é ÚLTIMO recurso (desalinha o ARIA): só quando
                        // a linha está mesmo fora da área visível do monitor.
                        if (CellOffWorkArea(row.ClickCell, hGrid)) EnsureOnScreen(hGrid);
                        Thread.Sleep(200);
                    }
                    scrolled = ScrollIntoView(grid, row.ClickCell, cellName);
                    if (scrolled) ready = StableAndHit(row.ClickCell, cellName, out p);
                    if (!ready) covering = CoveringCell(row.ClickCell, hGrid);
                }
                if (!ready)
                {
                    if (covering != null)
                        return "a lista está coberta por outra janela (" + covering +
                               ") — deixe o ARIA visível e rode de novo";
                    return scrolled
                        ? "a linha não ficou parada/visível sob o ponto de clique — clique NÃO enviado"
                        : "não consegui deixar a linha visível na grade (rolagem)";
                }

                int cx, cy;
                if (!ToTargetClient(hGrid, p.X, p.Y, out cx, out cy)) return "falha ao converter coordenadas";
                IntPtr lp = new IntPtr((cy << 16) | (cx & 0xFFFF));
                IntPtr mk = new IntPtr(MK_LBUTTON);

                // Registrado para diagnóstico: quando o diálogo não abre, o log diz
                // onde o duplo clique foi parar e em que célula.
                Log("INFO", string.Format("Duplo clique em '{0}': tela ({1:0},{2:0}) → cliente ({3},{4}).",
                    cellName, p.X, p.Y, cx, cy));

                PostMessage(hGrid, WM_LBUTTONDOWN, mk, lp);
                PostMessage(hGrid, WM_LBUTTONUP, IntPtr.Zero, lp);
                PostMessage(hGrid, WM_LBUTTONDBLCLK, mk, lp);
                PostMessage(hGrid, WM_LBUTTONUP, IntPtr.Zero, lp);
            }
            finally
            {
                LeaveWindowDpi(prevCtx);
            }

            DateTime limit = DateTime.Now.AddMilliseconds(StepTimeoutMs);
            while (DateTime.Now < limit)
            {
                taskDlg = FindOpenTaskDialog();
                if (taskDlg != null) { if (HideDialogs) HideWindow(taskDlg); return null; }
                Thread.Sleep(HideDialogs ? 10 : 100);
            }
            return "a Caixa de diálogo Tarefa não abriu após o duplo clique";
        }

        /// <summary>
        /// Mesma data em dd/MM/yyyy ou MM/dd/yyyy. No ARIA real (18/09) a lista mostra
        /// "16/09/2026" e o diálogo "09/16/2026" — a mesma data em formatos diferentes.
        /// A troca dia/mês só pode confundir duas ocorrências da MESMA atividade
        /// pendente, e o plano já exclui esse caso (ambígua).
        /// </summary>
        public static bool SameDate(string a, string b)
        {
            string[] x = DatePart(a).Split('/');
            string[] y = DatePart(b).Split('/');
            if (x.Length != 3 || y.Length != 3) return false;
            if (x[2] != y[2]) return false;
            return (x[0] == y[0] && x[1] == y[1]) || (x[0] == y[1] && x[1] == y[0]);
        }

        public static string DatePart(string text)
        {
            if (string.IsNullOrEmpty(text)) return "";
            System.Text.RegularExpressions.Match m =
                System.Text.RegularExpressions.Regex.Match(text, @"\d{2}/\d{2}/\d{4}");
            return m.Success ? m.Value : "";
        }

        private static string ReadValueLive(AutomationElement e)
        {
            if (e == null) return "";
            try
            {
                object vp;
                if (e.TryGetCurrentPattern(ValuePattern.Pattern, out vp))
                    return ((ValuePattern)vp).Current.Value ?? "";
            }
            catch { }
            return SafeName(e);
        }

        /// <summary>Recusa: registra e, no modo automático, fecha o diálogo SEM salvar.</summary>
        private DialogOwnerResult Reject(AutomationElement taskDlg, string reason)
        {
            Log("FAIL", reason);
            if (CloseOnReject) CloseWithoutSaving(taskDlg, ID_CANCEL, "Caixa de diálogo Tarefa");
            _r.Failed = true;
            return _r;
        }

        /// <summary>
        /// Fecha sem salvar, mas NÃO é falha: a atividade simplesmente não era para
        /// ser assumida (concluída/cancelada). No modo automático a execução segue
        /// para as outras — status variado no Care Path é o normal, não um problema.
        /// </summary>
        private DialogOwnerResult Skip(AutomationElement taskDlg, string reason)
        {
            Log("INFO", reason);
            if (CloseOnReject) CloseWithoutSaving(taskDlg, ID_CANCEL, "Caixa de diálogo Tarefa");
            _r.Skipped = true;
            return _r;
        }

        /// <summary>Abriu a linha errada: falha, mas pode ser desalinhamento de tela (vale repetir).</summary>
        private DialogOwnerResult RejectWrongRow(AutomationElement taskDlg, string reason)
        {
            _r.WrongRow = true;
            return Reject(taskDlg, reason);
        }

        private AutomationElement WaitDialog(string automationId, AutomationElement hint)
        {
            DateTime limit = DateTime.Now.AddMilliseconds(StepTimeoutMs);
            while (DateTime.Now < limit)
            {
                AutomationElement d = FindDialog(automationId, hint);
                if (d != null) return d;
                Thread.Sleep(HideDialogs ? 10 : 100);
            }
            return null;
        }

        private bool WaitClosed(AutomationElement dialog)
        {
            return WaitClosed(dialog, StepTimeoutMs);
        }

        /// <summary>True quando o diálogo fica invisível ou é destruído.</summary>
        private static bool WaitClosed(AutomationElement dialog, int timeoutMs)
        {
            DateTime limit = DateTime.Now.AddMilliseconds(timeoutMs);
            while (DateTime.Now < limit)
            {
                if (!IsOpen(dialog)) return true;
                Thread.Sleep(60);
            }
            return !IsOpen(dialog);
        }

        /// <summary>
        /// Fecha o diálogo SEM salvar, escalonando: Cancelar (BM_CLICK com o diálogo
        /// ativo) → Cancelar (Invoke) → WM_CLOSE (equivale ao X). Registra o que deu certo.
        /// </summary>
        private bool CloseWithoutSaving(AutomationElement dialog, string cancelId, string label)
        {
            if (!IsOpen(dialog)) return true;

            AutomationElement cancel = OwnById(dialog, cancelId);
            Log("INFO", string.Format("Fechando '{0}' sem salvar — Cancelar: {1}.",
                label, cancel != null ? Describe(cancel) : "NÃO encontrado"));

            Activate(dialog);
            if (cancel != null)
            {
                Click(cancel);
                if (WaitClosed(dialog, 3000)) { Log("OK", label + " fechada (Cancelar/BM_CLICK)."); return true; }
                InvokeAsync(cancel);
                if (WaitClosed(dialog, 3000)) { Log("OK", label + " fechada (Cancelar/Invoke)."); return true; }
            }
            IntPtr h = Hwnd(dialog);
            if (h != IntPtr.Zero)
            {
                PostMessage(h, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
                if (WaitClosed(dialog, 3000)) { Log("OK", label + " fechada (WM_CLOSE)."); return true; }
            }
            Log("FAIL", label + " continua aberta — feche manualmente com Cancelar.");
            return false;
        }

        private static AutomationElement ById(AutomationElement root, string automationId)
        {
            return OwnerAssigner.FindByAutomationId(root, automationId);
        }

        private static string SafeName(AutomationElement e)
        {
            try { return e.Current.Name ?? ""; }
            catch { return ""; }
        }

        private static string SafeId(AutomationElement e)
        {
            try { return e.Current.AutomationId ?? ""; }
            catch { return ""; }
        }

        /// <summary>Item selecionado de um ComboBox (o Name do combo não é confiável).</summary>
        private static string SelectedText(AutomationElement combo)
        {
            if (combo == null) return "";
            try
            {
                object sp;
                if (combo.TryGetCurrentPattern(SelectionPattern.Pattern, out sp))
                {
                    AutomationElement[] sel = ((SelectionPattern)sp).Current.GetSelection();
                    if (sel.Length > 0 && SafeName(sel[0]).Length > 0) return SafeName(sel[0]);
                }
                object vp;
                if (combo.TryGetCurrentPattern(ValuePattern.Pattern, out vp))
                {
                    string v = ((ValuePattern)vp).Current.Value;
                    if (!string.IsNullOrEmpty(v)) return v;
                }
            }
            catch { }
            return SafeName(combo);
        }

        /// <summary>
        /// Invoke em outra thread: botões que abrem diálogo modal travam a chamada
        /// síncrona de UI Automation até o modal fechar.
        /// </summary>
        private static void InvokeAsync(AutomationElement button)
        {
            if (button == null) return;
            Thread t = new Thread(delegate()
            {
                try
                {
                    object p;
                    if (button.TryGetCurrentPattern(InvokePattern.Pattern, out p))
                        ((InvokePattern)p).Invoke();
                }
                catch { }
            });
            t.IsBackground = true;
            t.Start();
        }

        private static List<AutomationElement> Items(AutomationElement list)
        {
            List<AutomationElement> items = new List<AutomationElement>();
            if (list == null) return items;
            try
            {
                AutomationElementCollection c = list.FindAll(TreeScope.Children,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.DataItem));
                foreach (AutomationElement e in c) items.Add(e);
                if (items.Count == 0)
                {
                    c = list.FindAll(TreeScope.Children,
                        new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.ListItem));
                    foreach (AutomationElement e in c) items.Add(e);
                }
            }
            catch { }
            return items;
        }

        /// <summary>Casamento EXATO com alguma variante — "Geovani" não pode casar com outro Geovani.</summary>
        private static bool IsUser(string itemText, string[] owners, bool selectedFormat)
        {
            string n = OwnerAssigner.Norm(itemText);
            for (int i = 0; i < owners.Length; i++)
            {
                string o = OwnerAssigner.Norm(owners[i]);
                if (o.Length == 0) continue;
                if (n == o) return true;
                // Lista de selecionados: "Nome - Departamento"
                if (selectedFormat && n.StartsWith(o + " -")) return true;
            }
            return false;
        }

        private static AutomationElement FindUserItem(AutomationElement list, string[] owners, bool selectedFormat)
        {
            foreach (AutomationElement it in Items(list))
                if (IsUser(SafeName(it), owners, selectedFormat)) return it;
            return null;
        }

        /// <summary>Checkbox Proprietário da linha (no próprio item ou no CheckBox filho).</summary>
        private static TogglePattern OwnerToggle(AutomationElement item)
        {
            object tp;
            if (item.TryGetCurrentPattern(TogglePattern.Pattern, out tp)) return (TogglePattern)tp;
            try
            {
                AutomationElement cb = item.FindFirst(TreeScope.Children,
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.CheckBox));
                if (cb != null && cb.TryGetCurrentPattern(TogglePattern.Pattern, out tp)) return (TogglePattern)tp;
            }
            catch { }
            return null;
        }

        private static ToggleState ReadToggle(AutomationElement item)
        {
            TogglePattern t = OwnerToggle(item);
            if (t == null) return ToggleState.Indeterminate;
            try { return t.Current.ToggleState; }
            catch { return ToggleState.Indeterminate; }
        }

        private static bool IsOnlySelected(AutomationElement list, AutomationElement item)
        {
            try
            {
                object sp;
                if (!list.TryGetCurrentPattern(SelectionPattern.Pattern, out sp)) return false;
                AutomationElement[] sel = ((SelectionPattern)sp).Current.GetSelection();
                return sel.Length == 1 && Automation.Compare(sel[0], item);
            }
            catch { return false; }
        }

        /// <summary>
        /// Marca o checkbox Proprietário da linha do usuário: seleciona a linha (o
        /// que também a torna o item "focado" da ListView) e POSTA Espaço direto no
        /// HWND da lista. Sem foco de teclado (falhou no ARIA real em 18/09), sem
        /// coordenadas (clique por coordenada acertou a linha errada no teste — DPI)
        /// e sem teclado global. Depois exige a linha em On e TODOS os outros itens
        /// no estado anterior; senão o chamador fecha a seleção sem salvar.
        /// </summary>
        private string CheckOwner(AutomationElement res, AutomationElement list, AutomationElement item)
        {
            List<AutomationElement> others = new List<AutomationElement>();
            List<ToggleState> before = new List<ToggleState>();
            foreach (AutomationElement it in Items(list))
            {
                if (Automation.Compare(it, item)) continue;
                others.Add(it);
                before.Add(ReadToggle(it));
            }

            IntPtr hList = Hwnd(list);
            if (hList == IntPtr.Zero) return "lista sem HWND";

            object sp;
            if (!item.TryGetCurrentPattern(SelectionItemPattern.Pattern, out sp))
                return "linha do usuário não aceita seleção";
            ((SelectionItemPattern)sp).Select();
            Thread.Sleep(100);
            if (!IsOnlySelected(list, item))
                return "não foi possível deixar só a linha do usuário selecionada — Espaço NÃO enviado";

            PostMessage(hList, WM_KEYDOWN, new IntPtr(VK_SPACE), new IntPtr(0x00390001));
            PostMessage(hList, WM_KEYUP, new IntPtr(VK_SPACE), unchecked(new IntPtr((int)0xC0390001)));
            Log("INFO", "Espaço enviado à lista (linha do usuário selecionada).");

            DateTime limit = DateTime.Now.AddMilliseconds(2000);
            while (ReadToggle(item) != ToggleState.On && DateTime.Now < limit) Thread.Sleep(50);
            if (ReadToggle(item) != ToggleState.On)
                return "o checkbox não ficou marcado (estado: " + ReadToggle(item) + ")";

            for (int i = 0; i < others.Count; i++)
                if (ReadToggle(others[i]) != before[i])
                    return string.Format("outro item mudou de estado ('{0}')", SafeName(others[i]).Trim());

            return null;   // sucesso
        }

        // ---------- fluxo ----------

        /// <summary>
        /// Com apply=false só confere atividade/paciente e relata. Com apply=true
        /// executa o fluxo; qualquer falha fecha a seleção SEM salvar e NÃO clica OK
        /// na tarefa — o usuário encontra a tarefa aberta como estava.
        /// </summary>
        public DialogOwnerResult Run(AutomationElement taskDlg, string[] owners, bool apply)
        {
            _r = new DialogOwnerResult();
            // Adota o que OpenListRow registrou (tela/posição da janela).
            if (_carryLog.Count > 0) { _r.Log.AddRange(_carryLog); _carryLog.Clear(); }
            if (taskDlg == null)
            {
                Log("FAIL", "Nenhuma Caixa de diálogo Tarefa aberta.");
                _r.Failed = true;
                return _r;
            }
            _r.DialogFound = true;

            // 1) Confere a atividade e o paciente NO PRÓPRIO diálogo.
            // Todos os campos do diálogo numa passada (ver FindIds).
            Dictionary<string, AutomationElement> ctl =
                FindIds(taskDlg, ID_ACTIVITY, ID_PATIENT, ID_STATUS, ID_DATE, ID_ADD, ID_SAVE);
            _r.Activity = SelectedText(Get(ctl, ID_ACTIVITY));
            _r.Patient = SelectedText(Get(ctl, ID_PATIENT));
            _r.Status = SelectedText(Get(ctl, ID_STATUS));
            Log("INFO", string.Format("Diálogo: atividade '{0}' | paciente '{1}' | status '{2}'",
                _r.Activity, _r.Patient, _r.Status));

            bool taskOk = false;
            for (int i = 0; i < Tasks.Length; i++)
                if (OwnerAssigner.TaskKey(_r.Activity) == OwnerAssigner.TaskKey(Tasks[i])) taskOk = true;
            if (!taskOk)
                return Reject(taskDlg, string.Format("'{0}' não é uma das tarefas-alvo — nada feito.", _r.Activity));

            bool patientOk = PatientTokens.Length == 0;
            for (int i = 0; i < PatientTokens.Length; i++)
                if (PatientTokens[i].Length > 0 &&
                    OwnerAssigner.Norm(_r.Patient).Contains(OwnerAssigner.Norm(PatientTokens[i]))) patientOk = true;
            if (!patientOk)
                return Reject(taskDlg, string.Format("Paciente do diálogo não é o do Eclipse ({0}) — nada feito.",
                    string.Join(" / ", PatientTokens)));

            // Só atividades pendentes. Concluída/cancelada é PULADA (não é erro): o
            // status real vem daqui, que é onde ele sempre está legível — na lista ele
            // pode aparecer só como ícone, e aí a linha chega até aqui sem status.
            // "Em andamento", "Pendente", "Parcialmente concluído" etc. são assumidas.
            if (OwnerAssigner.IsClosedStatus(_r.Status))
                return Skip(taskDlg, string.Format(
                    "Atividade com status '{0}' — pulada (só pendentes são assumidas).", _r.Status));

            // Modo automático: o diálogo tem que ser o da linha que o script abriu.
            if (ExpectedActivity != null &&
                OwnerAssigner.TaskKey(_r.Activity) != OwnerAssigner.TaskKey(ExpectedActivity))
                return RejectWrongRow(taskDlg, string.Format(
                    "Abriu '{0}', mas a linha clicada era '{1}' — diálogo errado, cancelado.", _r.Activity, ExpectedActivity));
            if (!string.IsNullOrEmpty(ExpectedDate))
            {
                string dlgDate = DatePart(ReadValueLive(Get(ctl, ID_DATE)));
                if (dlgDate.Length == 0)
                    Log("INFO", "Data do diálogo não lida — conferência de data pulada (atividade/paciente/status conferidos).");
                else if (!SameDate(dlgDate, ExpectedDate))
                    return RejectWrongRow(taskDlg, string.Format(
                        "Data do diálogo {0} ≠ data da linha {1} — outra ocorrência da atividade, cancelado.", dlgDate, ExpectedDate));
                else
                    Log("OK", string.Format("Data do diálogo ({0}) confere com a linha ({1}).", dlgDate, ExpectedDate));
            }

            // Seleção de Recurso já aberta (ex.: sobra de uma execução anterior):
            // clicar Adicionar de novo faz o ARIA lançar "Form that is already visible...".
            AutomationElement leftover = FindDialog(ID_RES_DLG, taskDlg);
            if (leftover != null)
            {
                Log("FAIL", "A janela 'Seleção de Recurso e Equipe' já está aberta — feche-a com Cancelar e rode de novo.");
                _r.Failed = true;
                return _r;
            }

            _r.Verified = true;
            Log("OK", "Atividade e paciente conferidos no diálogo.");

            if (!apply)
            {
                Log("INFO", "SIMULADO: Adicionar → escolher o usuário → '->' → marcar Proprietário → OK → OK.");
                return _r;
            }

            // 2) Adicionar → Seleção de Recurso e Equipe
            AutomationElement add = Get(ctl, ID_ADD);
            if (add == null) { Log("FAIL", "Botão Adicionar não encontrado."); _r.Failed = true; return _r; }
            Activate(taskDlg);
            Click(add);
            AutomationElement res = WaitDialog(ID_RES_DLG, taskDlg);
            if (res != null && HideDialogs) HideWindow(res);
            if (res == null)
            {
                Log("FAIL", "A janela 'Seleção de Recurso e Equipe' não abriu.");
                _r.Failed = true;
                return _r;
            }
            Log("OK", "Seleção de Recurso e Equipe aberta.");

            Dictionary<string, AutomationElement> rc =
                FindIds(res, ID_SELECTED, ID_PROVIDERS, ID_SEL_PROVIDER, ID_RES_OK);
            AutomationElement selected = Get(rc, ID_SELECTED);
            bool changed = false;

            // 3) Já está entre os selecionados? Senão, escolhe na lista de pessoas e move.
            AutomationElement mine = FindUserItem(selected, owners, true);
            if (mine == null)
            {
                AutomationElement person = FindUserItem(Get(rc, ID_PROVIDERS), owners, false);
                if (person == null)
                    return Abort(res, string.Format("Usuário ({0}) não está na lista de pessoas.",
                        string.Join(" / ", owners)));

                object sp;
                if (!person.TryGetCurrentPattern(SelectionItemPattern.Pattern, out sp))
                    return Abort(res, "Linha do usuário não aceita seleção.");
                ((SelectionItemPattern)sp).Select();
                Thread.Sleep(100);

                AutomationElement move = Get(rc, ID_SEL_PROVIDER);
                if (move == null) return Abort(res, "Botão '->' não encontrado.");
                Activate(res);
                Click(move);

                DateTime limit = DateTime.Now.AddMilliseconds(StepTimeoutMs);
                while (mine == null && DateTime.Now < limit)
                {
                    Thread.Sleep(80);
                    mine = FindUserItem(selected, owners, true);
                }
                if (mine == null) return Abort(res, "O usuário não apareceu em 'Equipes/Recursos Selecionados'.");
                Log("OK", string.Format("Adicionado: '{0}'", SafeName(mine).Trim()));
                changed = true;
            }
            else
            {
                Log("INFO", string.Format("Já participante: '{0}'", SafeName(mine).Trim()));
            }

            // 4) Marca Proprietário na linha do usuário (a equipe fica como está).
            if (OwnerToggle(mine) == null) return Abort(res, "Checkbox Proprietário não encontrado na linha do usuário.");
            if (ReadToggle(mine) != ToggleState.On)
            {
                string err = CheckOwner(res, selected, mine);
                if (err != null) return Abort(res, "Não foi possível marcar Proprietário: " + err + ".");
                Log("OK", "Proprietário marcado (demais itens inalterados).");
                changed = true;
            }
            else
            {
                Log("INFO", "Já estava marcado como Proprietário.");
            }

            // Nada mudou: fecha os dois diálogos sem salvar em vez de regravar a tarefa.
            if (!changed)
            {
                CloseWithoutSaving(res, ID_RES_CANCEL, "Seleção de Recurso");
                CloseWithoutSaving(taskDlg, ID_CANCEL, "Caixa de diálogo Tarefa");
                _r.AlreadyOwner = true;
                Log("OK", "Já era proprietário — nada gravado.");
                return _r;
            }

            // 5) OK na seleção (sem gravação no banco: só devolve à tarefa).
            AutomationElement resOk = Get(rc, ID_RES_OK);
            if (resOk == null) return Abort(res, "Botão OK da seleção não encontrado.");
            Activate(res);
            Click(resOk);
            if (!WaitClosed(res, 4000))
            {
                Log("INFO", "OK da seleção por BM_CLICK não fechou — tentando Invoke.");
                InvokeAsync(resOk);
                if (!WaitClosed(res, 4000))
                    return Abort(res, "A janela de seleção não fechou após OK.");
            }

            // 6) OK na tarefa — é aqui que grava. Uma tentativa só: se não fechar,
            // o usuário confere na tela e decide.
            AutomationElement save = Get(ctl, ID_SAVE);
            if (save == null)
            {
                Log("FAIL", "Botão OK da tarefa não encontrado — tarefa NÃO salva; confira na tela e clique OK você mesmo.");
                _r.Failed = true;
                return _r;
            }
            Activate(taskDlg);
            Click(save);
            if (!WaitClosed(taskDlg))
            {
                Log("FAIL", "A Caixa de diálogo Tarefa não fechou após OK — confira na tela (mensagem de validação?) e clique OK você mesmo se estiver certo.");
                _r.Failed = true;
                return _r;
            }

            _r.Changed = true;
            Log("OK", string.Format("'{0}': proprietário atribuído e tarefa salva.", _r.Activity));
            return _r;
        }

        /// <summary>Fecha a seleção sem salvar e deixa a tarefa aberta, sem salvar.</summary>
        private DialogOwnerResult Abort(AutomationElement res, string reason)
        {
            Log("FAIL", reason);
            CloseWithoutSaving(res, ID_RES_CANCEL, "Seleção de Recurso");
            Log("ATN", CloseOnReject
                ? "A tarefa NÃO foi salva."
                : "A tarefa NÃO foi salva e continua aberta na tela.");
            _r.Failed = true;
            return _r;
        }

        /// <summary>
        /// Modo automático, após falha: fecha SEM salvar o que tiver ficado aberto
        /// (Seleção de Recurso e/ou a Caixa de diálogo Tarefa aberta pelo script).
        /// </summary>
        public void CloseLeftover(AutomationElement taskDlg)
        {
            if (_r == null) _r = new DialogOwnerResult();
            AutomationElement res = FindDialog(ID_RES_DLG, taskDlg);
            if (res != null) CloseWithoutSaving(res, ID_RES_CANCEL, "Seleção de Recurso");
            if (IsOpen(taskDlg)) CloseWithoutSaving(taskDlg, ID_CANCEL, "Caixa de diálogo Tarefa");
        }
    }

    /// <summary>Resultado do modo automático (várias atividades em sequência).</summary>
    public class AutoResult
    {
        public int Done;
        public int AlreadyOwner;
        public readonly List<string> DoneTasks = new List<string>();
        /// <summary>Não era para assumir (concluída/cancelada descoberta no diálogo) — não é erro.</summary>
        public readonly List<string> SkippedTasks = new List<string>();
        public bool Stopped;
        public readonly List<string> Log = new List<string>();
    }

    /// <summary>
    /// Abre e assume, uma a uma, as atividades prontas do plano. Para na PRIMEIRA
    /// falha: as seguintes não são tentadas e nada fica aberto sem o usuário saber.
    /// </summary>
    public static class AutoAssigner
    {
        /// <summary>Tentativas de abrir a MESMA linha antes de desistir (tela/Citrix).</summary>
        private static readonly int MaxOpenAttempts = 3;

        private static void Add(AutoResult ar, string level, string msg)
        {
            ar.Log.Add(string.Format("{0} [{1}] {2}",
                DateTime.Now.ToString("HH:mm:ss", CultureInfo.InvariantCulture), level, msg));
        }

        public static AutoResult Run(AutomationElement grid, List<TaskCandidate> ready,
                                     TaskDialogOwner tdo, string[] owners)
        {
            AutoResult ar = new AutoResult();
            foreach (TaskCandidate c in ready)
            {
                ListRow expected = c.ListRow;
                Add(ar, "INFO", string.Format("=== {0} — linha de {1} ===", c.Task, expected.Date));

                // A grade pode ter sido recriada depois do salvamento anterior: relê a
                // linha e confere que continua sendo a mesma atividade/data.
                ListRow fresh = null;
                for (int tries = 0; tries < 15; tries++)   // até ~3 s se a grade estiver se atualizando
                {
                    fresh = OwnerAssigner.RereadRow(grid, expected);
                    if (fresh != null && OwnerAssigner.TaskKey(fresh.Activity) == OwnerAssigner.TaskKey(expected.Activity) &&
                        fresh.Date == expected.Date) break;
                    Thread.Sleep(200);
                }
                if (fresh == null ||
                    OwnerAssigner.TaskKey(fresh.Activity) != OwnerAssigner.TaskKey(expected.Activity) ||
                    fresh.Date != expected.Date)
                {
                    Add(ar, "FAIL", "A lista mudou desde o plano (linha não confere) — rode o script de novo.");
                    ar.Stopped = true;
                    break;
                }
                if (OwnerAssigner.IsClosedStatus(fresh.Status))
                {
                    Add(ar, "INFO", string.Format("Status agora é '{0}' — pulada.", fresh.Status));
                    ar.SkippedTasks.Add(c.Task);
                    continue;
                }
                if (OwnerAssigner.IsOwnerName(fresh.Owner, owners))
                {
                    Add(ar, "INFO", "Você já é o proprietário — pulada.");
                    ar.AlreadyOwner++;
                    continue;
                }

                // Até 3 tentativas: sob Citrix (redesenho remoto, janela coberta ou
                // meio fora da tela) o duplo clique pode cair na linha vizinha. Nesse
                // caso o diálogo é cancelado sem salvar e a linha é aberta de novo;
                // só depois disso é que o script desiste.
                bool stop = false, handled = false;
                for (int attempt = 1; attempt <= MaxOpenAttempts && !handled && !stop; attempt++)
                {
                    AutomationElement dlg;
                    string err = tdo.OpenListRow(grid, fresh, out dlg);
                    if (err != null)
                    {
                        if (attempt < MaxOpenAttempts)
                        {
                            Add(ar, "ATN", "Não abriu a atividade: " + err + " — tentando de novo.");
                            Thread.Sleep(400);
                            continue;
                        }
                        Add(ar, "FAIL", "Não abriu a atividade: " + err + ".");
                        stop = true;
                        break;
                    }
                    Add(ar, "OK", "Caixa de diálogo Tarefa aberta.");

                    tdo.ExpectedActivity = fresh.Activity;
                    tdo.ExpectedDate = TaskDialogOwner.DatePart(fresh.Date);
                    tdo.CloseOnReject = true;
                    DialogOwnerResult r = tdo.Run(dlg, owners, true);
                    if (r.Failed || r.Skipped) tdo.CloseLeftover(dlg);   // nada fica aberto
                    foreach (string line in r.Log) ar.Log.Add("    " + line);

                    if (r.WrongRow && attempt < MaxOpenAttempts)
                    {
                        Add(ar, "ATN", "Abriu a linha errada (tela desalinhada?) — nada salvo, abrindo de novo.");
                        Thread.Sleep(600);   // deixa a grade assentar
                        continue;
                    }
                    if (r.Failed)
                    {
                        Add(ar, "FAIL", "Parado nesta atividade — as seguintes NÃO foram tentadas.");
                        stop = true;
                        break;
                    }
                    handled = true;
                    if (r.Skipped) ar.SkippedTasks.Add(c.Task);
                    else if (r.AlreadyOwner) ar.AlreadyOwner++;
                    else if (r.Changed) { ar.Done++; ar.DoneTasks.Add(c.Task); }
                }
                if (stop) { ar.Stopped = true; break; }

                // Sem pausa fixa: a releitura da próxima linha já espera a grade.
            }
            return ar;
        }
    }

    /// <summary>
    /// Deixa transparentes, NO INSTANTE em que aparecem, só os diálogos que o script
    /// abre (por título exato). O Windows avisa pela notificação EVENT_OBJECT_SHOW;
    /// sondar a cada 10 ms ainda deixava ~50 ms de "piscada" por diálogo (18/09).
    /// Mensagens de erro do ARIA NÃO casam com os títulos e continuam visíveis.
    /// </summary>
    public sealed class DialogHider : IDisposable
    {
        private delegate void WinEventProc(IntPtr hook, uint evt, IntPtr hwnd, int idObject, int idChild,
                                           uint thread, uint time);

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern IntPtr SetWinEventHook(uint min, uint max, IntPtr mod, WinEventProc proc,
                                                     uint pid, uint tid, uint flags);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool UnhookWinEvent(IntPtr hook);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern int GetMessage(out MSG msg, IntPtr hwnd, uint min, uint max);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool PostThreadMessage(uint tid, uint msg, IntPtr w, IntPtr l);
        [System.Runtime.InteropServices.DllImport("kernel32.dll")]
        private static extern uint GetCurrentThreadId();
        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
        private static extern int GetWindowText(IntPtr h, StringBuilder s, int max);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern int GetWindowLong(IntPtr h, int index);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern int SetWindowLong(IntPtr h, int index, int value);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool SetLayeredWindowAttributes(IntPtr h, uint key, byte alpha, uint flags);

        [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
        private struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam; public uint time; public int x; public int y; }

        private const uint EVENT_OBJECT_SHOW = 0x8002;
        private const uint WINEVENT_OUTOFCONTEXT = 0x0000;
        private const uint WM_QUIT = 0x0012;

        private readonly string[] _titles;
        private readonly WinEventProc _proc;   // referência mantida: o GC não pode coletar
        private readonly Thread _thread;
        private uint _tid;
        private readonly ManualResetEvent _ready = new ManualResetEvent(false);

        public DialogHider(string[] processNames, string[] titles)
        {
            _titles = new string[titles.Length];
            for (int i = 0; i < titles.Length; i++) _titles[i] = OwnerAssigner.Norm(titles[i]);
            _proc = OnEvent;

            List<uint> pids = new List<uint>();
            foreach (string pn in processNames)
            {
                try { foreach (Process p in Process.GetProcessesByName(pn)) pids.Add((uint)p.Id); }
                catch { }
            }

            // Thread própria com fila de mensagens: é nela que o Windows entrega o aviso.
            _thread = new Thread(delegate()
            {
                _tid = GetCurrentThreadId();
                List<IntPtr> hooks = new List<IntPtr>();
                foreach (uint pid in pids)
                {
                    IntPtr h = SetWinEventHook(EVENT_OBJECT_SHOW, EVENT_OBJECT_SHOW, IntPtr.Zero, _proc,
                                               pid, 0, WINEVENT_OUTOFCONTEXT);
                    if (h != IntPtr.Zero) hooks.Add(h);
                }
                _ready.Set();
                MSG m;
                while (GetMessage(out m, IntPtr.Zero, 0, 0) > 0) { }
                foreach (IntPtr h in hooks) UnhookWinEvent(h);
            });
            _thread.IsBackground = true;
            _thread.SetApartmentState(ApartmentState.STA);
            _thread.Start();
            _ready.WaitOne(2000);
        }

        private void OnEvent(IntPtr hook, uint evt, IntPtr hwnd, int idObject, int idChild, uint thread, uint time)
        {
            if (idObject != 0 || idChild != 0 || hwnd == IntPtr.Zero) return;   // só a janela em si
            try
            {
                StringBuilder sb = new StringBuilder(256);
                GetWindowText(hwnd, sb, 256);
                string t = OwnerAssigner.Norm(sb.ToString());
                if (t.Length == 0) return;
                for (int i = 0; i < _titles.Length; i++)
                {
                    if (t == _titles[i])
                    {
                        SetWindowLong(hwnd, -20 /* GWL_EXSTYLE */, GetWindowLong(hwnd, -20) | 0x80000 /* WS_EX_LAYERED */);
                        SetLayeredWindowAttributes(hwnd, 0, 0, 0x2 /* LWA_ALPHA */);
                        return;
                    }
                }
            }
            catch { }
        }

        public void Dispose()
        {
            if (_tid != 0) PostThreadMessage(_tid, WM_QUIT, IntPtr.Zero, IntPtr.Zero);
            _thread.Join(2000);
        }
    }
}
