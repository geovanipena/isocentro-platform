using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

namespace VMS.TPS
{
    /// <summary>
    /// A janela onde tudo é decidido. Montada em código, sem XAML: numa tela
    /// só, o aparato de Page/App.xaml no .csproj custa mais do que rende.
    ///
    /// Nenhum campo tem valor adivinhado a partir do caso — o que o script
    /// oferece é o ponto de partida mais comum, sempre visível antes de
    /// escrever. Plano montado com uma energia que ninguém conferiu é pior
    /// que plano nenhum, porque já parece trabalho feito.
    /// </summary>
    public class JanelaPrePlan : Window
    {
        readonly Bancada _bancada;
        readonly StructureSet _ss;

        // O que já existe gravado. É daqui que sai o Id de técnica sugerido: a
        // técnica de arco de um serviço pode se chamar ARC, ARC DYNAMIC ou
        // SRS ARC, e o nome errado só é recusado na criação do primeiro campo,
        // com o plano já criado.
        List<Equipamento> _conhecidos = new List<Equipamento>();

        readonly ComboBox _curso = new ComboBox();
        readonly TextBox _idPlano = new TextBox { Text = "PrePlan" };
        readonly ComboBox _alvo = new ComboBox();

        readonly TextBox _dosePorFracao = new TextBox { Text = "200" };
        readonly TextBox _fracoes = new TextBox { Text = "25" };

        readonly RadioButton _vmat = new RadioButton { Content = "VMAT — 2 arcos", IsChecked = true };
        readonly RadioButton _fixos = new RadioButton { Content = "Campos fixos" };
        readonly TextBox _numCampos = new TextBox { Text = "7", Width = 40 };

        readonly ComboBox _equipamento = new ComboBox();
        readonly TextBox _maquina = new TextBox();
        readonly TextBox _energia = new TextBox();
        readonly TextBox _taxaDose = new TextBox { Text = "600" };
        readonly TextBox _tecnicaId = new TextBox { Text = "ARC" };
        readonly TextBox _fluencia = new TextBox();

        readonly RadioButton _isoAlvo = new RadioButton { Content = "centro do alvo", IsChecked = true };
        readonly RadioButton _isoOrigem = new RadioButton { Content = "origem do usuário (marcação da TC)" };

        readonly TextBox _margem = new TextBox { Text = "5" };
        readonly CheckBox _rotacao = new CheckBox { Content = "otimizar a rotação do colimador" };
        readonly StackPanel _painelArcos = new StackPanel();
        readonly StackPanel _painelFixos = new StackPanel();
        readonly TextBox _colArco1 = new TextBox { Text = "30" };
        readonly TextBox _colArco2 = new TextBox { Text = "330" };
        readonly TextBox _colFixos = new TextBox { Text = "0" };

        readonly CheckBox _nto = new CheckBox { Content = "adicionar o NTO automático", IsChecked = true };
        readonly TextBox _prioridadeNto = new TextBox { Text = "150", Width = 50 };

        readonly TextBlock _resumo = new TextBlock { TextWrapping = TextWrapping.Wrap };
        readonly Button _montar = new Button { Content = "Montar plano", Width = 120, Height = 28, IsDefault = true };

        public Pedido Pedido { get; private set; }

        public JanelaPrePlan(Bancada bancada, List<Course> cursos, List<Structure> alvos)
        {
            _bancada = bancada;
            _ss = bancada.Conjunto;

            Title = Script.NOME;
            Width = 560;
            Height = 720;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            ResizeMode = ResizeMode.CanResize;

            PreencherCursos(cursos, bancada.CursoAberto);
            PreencherAlvos(alvos);
            PreencherEquipamentos(bancada.Paciente);

            // Origem do usuário só é oferecida se ela existe. Sem HasUserOrigin
            // a "origem" da imagem é o canto do volume da TC, e um isocentro ali
            // fica fora do paciente — sem erro nenhum, só errado.
            if (!_ss.Image.HasUserOrigin)
            {
                _isoOrigem.IsEnabled = false;
                _isoOrigem.ToolTip = "Esta imagem não tem origem do usuário marcada.";
            }

            var raiz = new Grid { Margin = new Thickness(16) };
            raiz.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            raiz.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            raiz.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

            var conteudo = new StackPanel();
            conteudo.Children.Add(Grupo("Plano", MontarGrupoPlano()));
            conteudo.Children.Add(Grupo("Campos", MontarGrupoCampos()));
            conteudo.Children.Add(Grupo("Geometria", MontarGrupoGeometria()));
            conteudo.Children.Add(Grupo("Otimização", MontarGrupoOtimizacao()));

            var rolo = new ScrollViewer
            {
                Content = conteudo,
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto
            };
            Grid.SetRow(rolo, 0);
            raiz.Children.Add(rolo);

            var caixaResumo = new Border
            {
                Background = Brushes.WhiteSmoke,
                BorderBrush = Brushes.LightGray,
                BorderThickness = new Thickness(1),
                Padding = new Thickness(10),
                Margin = new Thickness(0, 12, 0, 0),
                Child = _resumo
            };
            Grid.SetRow(caixaResumo, 1);
            raiz.Children.Add(caixaResumo);

            var botoes = new DockPanel { Margin = new Thickness(0, 12, 0, 0) };

            // O diagnóstico fica à ESQUERDA, longe dos outros dois: ele não faz
            // parte do fluxo, e uma varredura disparada por engano cria e apaga
            // um plano no banco clínico.
            var diagnostico = new Button
            {
                Content = "Diagnóstico…",
                Width = 120,
                Height = 28,
                HorizontalAlignment = HorizontalAlignment.Left,
                ToolTip = "Lê o que a API sabe sobre os campos que já existem e, se você "
                        + "autorizar, experimenta as combinações de energia, taxa e técnica "
                        + "num plano temporário."
            };
            diagnostico.Click += Diagnostico_Click;
            DockPanel.SetDock(diagnostico, Dock.Left);
            botoes.Children.Add(diagnostico);

            var direita = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right
            };
            direita.Children.Add(new Button
            {
                Content = "Cancelar",
                Width = 100,
                Height = 28,
                IsCancel = true,
                Margin = new Thickness(0, 0, 8, 0)
            });
            _montar.Click += Montar_Click;
            direita.Children.Add(_montar);
            botoes.Children.Add(direita);
            Grid.SetRow(botoes, 2);
            raiz.Children.Add(botoes);

            Content = raiz;

            // Um ouvinte só, ligado depois de tudo montado: durante a montagem
            // os controles ainda estão pela metade e o Revisar leria campo que
            // ainda não existe.
            LigarOuvintes();
            Revisar();
        }

        // -------------------------------------------------------------------
        // Grupos
        // -------------------------------------------------------------------

        UIElement MontarGrupoPlano()
        {
            var pilha = new StackPanel();
            pilha.Children.Add(Linha("Curso", _curso));
            pilha.Children.Add(Linha("Id do plano", _idPlano));
            pilha.Children.Add(Linha("Alvo", _alvo,
                "Decide o isocentro e a abertura dos campos."));
            pilha.Children.Add(Linha("Dose por fração (cGy)", _dosePorFracao));
            pilha.Children.Add(Linha("Frações", _fracoes));
            return pilha;
        }

        UIElement MontarGrupoCampos()
        {
            var pilha = new StackPanel();

            var tecnica = new StackPanel { Orientation = Orientation.Horizontal };
            tecnica.Children.Add(_vmat);
            _fixos.Margin = new Thickness(20, 0, 6, 0);
            tecnica.Children.Add(_fixos);
            tecnica.Children.Add(_numCampos);
            tecnica.Children.Add(new TextBlock
            {
                Text = " campos",
                VerticalAlignment = VerticalAlignment.Center
            });
            pilha.Children.Add(Linha("Técnica", tecnica));

            pilha.Children.Add(Linha("Já usado neste paciente", _equipamento,
                "A ESAPI não tem catálogo de máquinas. Esta lista vem dos planos "
              + "que o paciente já tem e do que já deu certo nesta estação."));
            pilha.Children.Add(Linha("Máquina", _maquina));
            pilha.Children.Add(Linha("Energia", _energia,
                "Só a energia: 6X. O \"-FFF\" que o Eclipse mostra junto é o modo de "
              + "fluência, e vai no campo de baixo."));
            pilha.Children.Add(Linha("Taxa de dose (UM/min)", _taxaDose));
            pilha.Children.Add(Linha("Técnica (Id)", _tecnicaId,
                "A doc oficial diz \"typically STATIC or ARC\". NÃO é o nome da técnica do "
              + "plano (SRS ARC, por exemplo): esse é nome de exibição. Se o que já está "
              + "gravado no paciente usar outro nome, ele entra como segunda tentativa "
              + "sozinho."));
            pilha.Children.Add(Linha("Modo de fluência", _fluencia,
                "Vazio = com filtro achatador. FFF quando a energia for sem filtro. "
              + "Energia \"6X-FFF\" com este campo vazio é recusada pelo Eclipse com "
              + "\"External beam configuration not found\"."));

            return pilha;
        }

        UIElement MontarGrupoGeometria()
        {
            var pilha = new StackPanel();

            var iso = new StackPanel();
            iso.Children.Add(_isoAlvo);
            iso.Children.Add(_isoOrigem);
            pilha.Children.Add(Linha("Isocentro", iso));

            _painelArcos.Children.Add(Linha("Colimador do arco 1", _colArco1));
            _painelArcos.Children.Add(Linha("Colimador do arco 2", _colArco2,
                "Opostos de propósito: o vazamento entre lâminas de um arco cai "
              + "onde o outro não tem junta."));
            pilha.Children.Add(_painelArcos);

            _painelFixos.Children.Add(Linha("Colimador dos campos", _colFixos));
            _painelFixos.Children.Add(Linha("", _rotacao));
            pilha.Children.Add(_painelFixos);

            pilha.Children.Add(Linha("Margem do colimador (mm)", _margem,
                "Folga das jaws em volta do alvo, no ajuste automático."));

            return pilha;
        }

        UIElement MontarGrupoOtimizacao()
        {
            var pilha = new StackPanel();

            var linha = new StackPanel { Orientation = Orientation.Horizontal };
            linha.Children.Add(_nto);
            linha.Children.Add(new TextBlock
            {
                Text = "   prioridade ",
                VerticalAlignment = VerticalAlignment.Center
            });
            linha.Children.Add(_prioridadeNto);
            pilha.Children.Add(Linha("", linha));

            pilha.Children.Add(new TextBlock
            {
                Text = "Os objetivos do alvo e dos órgãos de risco NÃO são criados aqui: "
                     + "eles são do protocolo do serviço, e um objetivo inventado por script "
                     + "é uma dose que o otimizador vai perseguir.",
                TextWrapping = TextWrapping.Wrap,
                Foreground = Brushes.Gray,
                Margin = new Thickness(0, 6, 0, 0)
            });

            return pilha;
        }

        // -------------------------------------------------------------------
        // Preenchimento
        // -------------------------------------------------------------------

        void PreencherCursos(List<Course> cursos, Course aberto)
        {
            foreach (Course c in cursos)
                _curso.Items.Add(new ComboBoxItem { Content = c.Id, Tag = c });

            _curso.SelectedIndex = 0;
            if (aberto != null)
            {
                for (int i = 0; i < cursos.Count; i++)
                    if (cursos[i].Id == aberto.Id)
                        _curso.SelectedIndex = i;
            }
        }

        void PreencherAlvos(List<Structure> alvos)
        {
            foreach (Structure s in alvos)
                _alvo.Items.Add(new ComboBoxItem
                {
                    Content = string.Format("{0}      {1:0.0} cm3", s.Id, s.Volume),
                    Tag = s
                });

            // Vem marcado o MAIOR de tipo PTV — quando há PTV de vários níveis,
            // o de dose mais baixa costuma ser o que engloba os outros, e é
            // dele que sai o isocentro que serve para todos. Marcado, não
            // decidido: quem confirma é quem está olhando.
            Structure sugerido = alvos
                .Where(s => string.Equals(s.DicomType, "PTV", StringComparison.OrdinalIgnoreCase))
                .OrderByDescending(s => s.Volume)
                .FirstOrDefault();

            int i = sugerido == null ? 0 : alvos.FindIndex(s => s.Id == sugerido.Id);
            _alvo.SelectedIndex = Math.Max(0, i);
        }

        void PreencherEquipamentos(Patient paciente)
        {
            _conhecidos = Maquinas.Conhecidos(paciente);

            foreach (Equipamento e in _conhecidos)
                _equipamento.Items.Add(new ComboBoxItem
                {
                    Content = e.ToString() + (e.Arco ? "   (arco)" : "   (fixo)"),
                    Tag = e
                });

            if (_conhecidos.Count == 0)
            {
                _equipamento.IsEnabled = false;
                _equipamento.ToolTip = "Nenhuma máquina encontrada nos planos deste paciente "
                                     + "nem no histórico desta estação. Digite abaixo.";
                return;
            }

            _equipamento.SelectionChanged += (a, b) =>
            {
                var item = _equipamento.SelectedItem as ComboBoxItem;
                if (item == null)
                    return;
                var e = (Equipamento)item.Tag;
                _maquina.Text = e.Maquina;
                _taxaDose.Text = e.TaxaDose.ToString(CultureInfo.CurrentCulture);

                // Energia e fluência entram SEPARADAS, mesmo que o combo mostre
                // "6X-FFF" numa linha só: é assim que o
                // ExternalBeamMachineParameters as quer.
                _energia.Text = e.Energia;
                _fluencia.Text = e.Fluencia == null ? "" : e.Fluencia;

                // A técnica NÃO vem junto. O Technique.Id de um feixe é o nome
                // da técnica do PLANO ("SRS ARC"), e o techniqueId que o
                // AddBeam quer é outro: a doc oficial diz "typically STATIC or
                // ARC". Preferir o colhido custou uma ida ao Eclipse em
                // 03/09/2026 — ele agora fica só como segunda tentativa.
                Revisar();
            };
            _equipamento.SelectedIndex = 0;
        }

        // -------------------------------------------------------------------
        // Revisão contínua
        // -------------------------------------------------------------------

        void LigarOuvintes()
        {
            foreach (TextBox t in new[] { _idPlano, _dosePorFracao, _fracoes, _numCampos,
                                          _maquina, _energia, _taxaDose, _tecnicaId, _fluencia,
                                          _margem, _colArco1, _colArco2, _colFixos, _prioridadeNto })
                t.TextChanged += (a, b) => Revisar();

            _vmat.Checked += (a, b) => TrocarTecnica();
            _fixos.Checked += (a, b) => TrocarTecnica();
            _isoAlvo.Checked += (a, b) => Revisar();
            _isoOrigem.Checked += (a, b) => Revisar();
            _nto.Checked += (a, b) => Revisar();
            _nto.Unchecked += (a, b) => Revisar();
            _rotacao.Checked += (a, b) => Revisar();
            _rotacao.Unchecked += (a, b) => Revisar();
            _curso.SelectionChanged += (a, b) => Revisar();
            _alvo.SelectionChanged += (a, b) => Revisar();

            TrocarTecnica();
        }

        /// <summary>
        /// A técnica manda no Id de técnica e em quais campos de colimador
        /// aparecem. Sobrescrever o Id é deliberado: técnica de campo fixo num
        /// plano de arcos é a recusa que só aparece na criação do primeiro
        /// campo, com o plano já criado.
        /// </summary>
        void TrocarTecnica()
        {
            bool vmat = _vmat.IsChecked == true;

            _painelArcos.Visibility = vmat ? Visibility.Visible : Visibility.Collapsed;
            _painelFixos.Visibility = vmat ? Visibility.Collapsed : Visibility.Visible;
            _numCampos.IsEnabled = !vmat;

            // "typically STATIC or ARC" — ExternalBeamMachineParameters, doc
            // oficial da 15.6. O que foi colhido do plano vizinho entra como
            // SEGUNDA tentativa, no Pedido, não aqui.
            _tecnicaId.Text = vmat ? "ARC" : "STATIC";

            Revisar();
        }

        /// <summary>
        /// A técnica COLHIDA do que já existe gravado, ou null se não houver.
        /// Vale como segunda tentativa: se o serviço tiver batizado a técnica
        /// de outra coisa, é daqui que sai o nome. Primeiro a da mesma
        /// máquina, depois qualquer uma do mesmo tipo.
        /// </summary>
        string TecnicaColhida(bool arco)
        {
            string maquina = _maquina.Text.Trim();

            Equipamento achado = _conhecidos.FirstOrDefault(e =>
                e.Arco == arco && !string.IsNullOrWhiteSpace(e.Tecnica) &&
                string.Equals(e.Maquina, maquina, StringComparison.CurrentCultureIgnoreCase));

            if (achado == null)
                achado = _conhecidos.FirstOrDefault(e =>
                    e.Arco == arco && !string.IsNullOrWhiteSpace(e.Tecnica));

            return achado == null ? null : achado.Tecnica;
        }

        void Revisar()
        {
            string motivo;
            Pedido p = Montar(out motivo);

            _montar.IsEnabled = p != null;
            _montar.ToolTip = p != null ? null : motivo;
            _resumo.Text = p != null ? Resumir(p) : "Falta: " + motivo;
        }

        static string Resumir(Pedido p)
        {
            var linhas = new List<string>();
            linhas.Add(string.Format("{0} no curso {1} — {2} x {3:0} cGy = {4:0} cGy",
                p.IdPlano, p.Curso.Id, p.Fracoes, p.DosePorFracaoCGy, p.DoseTotalCGy));

            if (p.Tecnica == Tecnica.Vmat)
                linhas.Add(string.Format("2 arcos: 181→179 horário (col {0:0}) e 179→181 anti-horário (col {1:0})",
                    p.ColimadorArco1, p.ColimadorArco2));
            else
                linhas.Add(string.Format("{0} campos em G {1}   (col {2:0})",
                    p.NumeroDeCampos,
                    string.Join(", ", p.AngulosDeGantry().Select(a => a.ToString("0"))),
                    p.ColimadorCamposFixos));

            linhas.Add(string.Format("Isocentro no {0}:  {1:0.0}  {2:0.0}  {3:0.0} mm (DICOM)",
                p.OrigemDoIsocentro, p.Isocentro.x, p.Isocentro.y, p.Isocentro.z));

            linhas.Add(p.Maquina + "   " + p.Energia + "   " + p.TaxaDose + " UM/min   " + p.TecnicaId
                     + (string.IsNullOrWhiteSpace(p.ModoFluencia) ? "" : "   " + p.ModoFluencia));

            return string.Join(Environment.NewLine, linhas);
        }

        /// <summary>
        /// Devolve o pedido pronto, ou null e o motivo. É a MESMA função que
        /// acende o botão e que produz o que vai ser criado — assim não existe
        /// estado em que o botão está aceso e o pedido é outro.
        /// </summary>
        Pedido Montar(out string motivo)
        {
            motivo = null;

            var p = new Pedido();

            var itemCurso = _curso.SelectedItem as ComboBoxItem;
            var itemAlvo = _alvo.SelectedItem as ComboBoxItem;
            if (itemCurso == null || itemAlvo == null)
            {
                motivo = "escolher o curso e o alvo";
                return null;
            }
            p.Curso = (Course)itemCurso.Tag;
            p.Alvo = (Structure)itemAlvo.Tag;

            p.IdPlano = _idPlano.Text.Trim();
            if (p.IdPlano.Length == 0)
            {
                motivo = "dar um Id ao plano";
                return null;
            }
            if (p.Curso.PlanSetups.Any(x => string.Equals(x.Id, p.IdPlano, StringComparison.OrdinalIgnoreCase)))
            {
                motivo = "já existe um plano '" + p.IdPlano + "' neste curso";
                return null;
            }

            if (!Numero(_dosePorFracao, out p.DosePorFracaoCGy) || p.DosePorFracaoCGy <= 0)
            {
                motivo = "dose por fração";
                return null;
            }

            double fracoes;
            if (!Numero(_fracoes, out fracoes) || fracoes < 1)
            {
                motivo = "número de frações";
                return null;
            }
            p.Fracoes = (int)fracoes;

            p.Tecnica = _vmat.IsChecked == true ? Tecnica.Vmat : Tecnica.CamposFixos;

            double campos;
            if (!Numero(_numCampos, out campos) || campos < 2 || campos > 20)
            {
                if (p.Tecnica == Tecnica.CamposFixos)
                {
                    motivo = "número de campos (2 a 20)";
                    return null;
                }
                campos = 7;
            }
            p.NumeroDeCampos = (int)campos;

            p.Maquina = _maquina.Text.Trim();
            p.Energia = _energia.Text.Trim();
            p.TecnicaId = _tecnicaId.Text.Trim();

            // A colhida só entra se for DIFERENTE da digitada — senão a
            // Montagem tentaria duas vezes a mesma coisa e o diagnóstico
            // mostraria duas linhas iguais, que é o que mandou procurar no
            // lugar errado da última vez.
            string colhida = TecnicaColhida(p.Tecnica == Tecnica.Vmat);
            p.TecnicaAlternativa =
                colhida != null && !string.Equals(colhida, p.TecnicaId,
                                                  StringComparison.CurrentCultureIgnoreCase)
                ? colhida : null;
            p.ModoFluencia = _fluencia.Text.Trim();
            if (p.Maquina.Length == 0 || p.Energia.Length == 0 || p.TecnicaId.Length == 0)
            {
                motivo = "máquina, energia e Id de técnica";
                return null;
            }

            double taxa;
            if (!Numero(_taxaDose, out taxa) || taxa <= 0)
            {
                motivo = "taxa de dose";
                return null;
            }
            p.TaxaDose = (int)taxa;

            if (!Numero(_margem, out p.MargemColimadorMm) || p.MargemColimadorMm < 0)
            {
                motivo = "margem do colimador";
                return null;
            }

            if (!Numero(_colArco1, out p.ColimadorArco1) ||
                !Numero(_colArco2, out p.ColimadorArco2) ||
                !Numero(_colFixos, out p.ColimadorCamposFixos))
            {
                motivo = "ângulo de colimador";
                return null;
            }

            p.OtimizarRotacaoDoColimador = p.Tecnica == Tecnica.CamposFixos && _rotacao.IsChecked == true;

            p.AdicionarNto = _nto.IsChecked == true;
            if (p.AdicionarNto && (!Numero(_prioridadeNto, out p.PrioridadeNto) || p.PrioridadeNto <= 0))
            {
                motivo = "prioridade do NTO";
                return null;
            }

            if (_isoOrigem.IsChecked == true)
            {
                p.Isocentro = _ss.Image.UserOrigin;
                p.OrigemDoIsocentro = "origem do usuário";
            }
            else
            {
                p.Isocentro = p.Alvo.CenterPoint;
                p.OrigemDoIsocentro = "centro de " + p.Alvo.Id;
            }

            // Estrutura vazia ou com contorno degenerado devolve coordenada
            // NaN, e o AddBeam aceita: o campo nasce com isocentro inválido e
            // o Eclipse só reclama muito depois.
            if (double.IsNaN(p.Isocentro.x) || double.IsNaN(p.Isocentro.y) || double.IsNaN(p.Isocentro.z))
            {
                motivo = "o isocentro escolhido não tem coordenada válida";
                return null;
            }

            return p;
        }

        /// <summary>
        /// Duas partes, e a segunda é opcional: a leitura do que já existe
        /// (que não escreve nada) e a varredura das combinações (que cria um
        /// plano temporário). A leitura já sai sozinha — dá para responder
        /// "não" à varredura e mandar só ela.
        /// </summary>
        void Diagnostico_Click(object remetente, RoutedEventArgs e)
        {
            var texto = new StringBuilder();
            texto.AppendLine("PrePlan — diagnóstico de " + DateTime.Now.ToString("dd/MM/yyyy HH:mm"));
            texto.AppendLine();

            try
            {
                texto.AppendLine(Sonda.Inventario(_bancada.Paciente));
            }
            catch (Exception erro)
            {
                texto.AppendLine("A leitura falhou: " + erro.GetType().Name + ": " + erro.Message);
            }

            string motivo;
            Pedido p = Montar(out motivo);

            if (p == null)
            {
                texto.AppendLine("Varredura não feita: falta " + motivo + ".");
            }
            else
            {
                bool autorizada = MessageBox.Show(
                    "Experimentar as combinações de energia, taxa de dose e técnica?\n\n" +
                    "Isso cria um plano TEMPORÁRIO no curso " + p.Curso.Id + ", tenta criar campos " +
                    "nele e o apaga no fim. Um AddBeam recusado não grava nada; os aceitos viram " +
                    "campos nesse plano temporário.\n\n" +
                    "A leitura do que já existe já foi feita — dá para responder Não e usar só ela.",
                    Script.NOME, MessageBoxButton.YesNo, MessageBoxImage.Question,
                    MessageBoxResult.No) == MessageBoxResult.Yes;

                if (!autorizada)
                {
                    texto.AppendLine("Varredura não autorizada.");
                }
                else
                {
                    try
                    {
                        texto.AppendLine(Sonda.Varrer(_bancada, p));
                    }
                    catch (Exception erro)
                    {
                        texto.AppendLine("A varredura parou: " + erro.GetType().Name + ": " + erro.Message);
                    }
                }
            }

            string arquivo = Sonda.Gravar(texto.ToString());
            MessageBox.Show(
                arquivo != null
                    ? "Diagnóstico gravado em:\n\n" + arquivo
                    : "Não foi possível gravar o arquivo de diagnóstico.",
                Script.NOME, MessageBoxButton.OK, MessageBoxImage.Information);
        }

        void Montar_Click(object remetente, RoutedEventArgs e)
        {
            string motivo;
            Pedido = Montar(out motivo);
            if (Pedido == null)
                return;

            DialogResult = true;
        }

        // -------------------------------------------------------------------
        // Utilidades de tela
        // -------------------------------------------------------------------

        /// <summary>
        /// Aceita vírgula E ponto. A estação é pt-BR e o físico digita "2,5";
        /// material copiado do TPS vem com ponto. Recusar um dos dois seria uma
        /// recusa que ninguém entende olhando o próprio número na tela.
        /// </summary>
        static bool Numero(TextBox caixa, out double valor)
        {
            string texto = caixa.Text.Trim();
            if (double.TryParse(texto, NumberStyles.Any, CultureInfo.CurrentCulture, out valor))
                return true;
            return double.TryParse(texto.Replace(',', '.'), NumberStyles.Any,
                                   CultureInfo.InvariantCulture, out valor);
        }

        static UIElement Grupo(string titulo, UIElement conteudo)
        {
            var pilha = new StackPanel { Margin = new Thickness(0, 0, 0, 14) };
            pilha.Children.Add(new TextBlock
            {
                Text = titulo,
                FontWeight = FontWeights.SemiBold,
                Margin = new Thickness(0, 0, 0, 6)
            });
            pilha.Children.Add(conteudo);
            return pilha;
        }

        static UIElement Linha(string rotulo, UIElement controle, string dica = null)
        {
            var pilha = new StackPanel { Margin = new Thickness(0, 0, 0, 4) };

            var linha = new DockPanel { LastChildFill = true };
            var texto = new TextBlock
            {
                Text = rotulo,
                Width = 160,
                VerticalAlignment = VerticalAlignment.Center
            };
            DockPanel.SetDock(texto, Dock.Left);
            linha.Children.Add(texto);
            linha.Children.Add(controle);
            pilha.Children.Add(linha);

            if (dica != null)
                pilha.Children.Add(new TextBlock
                {
                    Text = dica,
                    TextWrapping = TextWrapping.Wrap,
                    Foreground = Brushes.Gray,
                    Margin = new Thickness(160, 2, 0, 6)
                });

            return pilha;
        }
    }
}
