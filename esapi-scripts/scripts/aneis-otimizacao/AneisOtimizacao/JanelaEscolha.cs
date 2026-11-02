using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using VMS.TPS.Common.Model.API;

namespace VMS.TPS
{
    /// <summary>
    /// Escolha dos PTVs que entram na soma. Montada em código, sem XAML: numa
    /// tela só, o aparato de Page/App.xaml no .csproj custa mais do que rende.
    /// </summary>
    public class JanelaEscolha : Window
    {
        readonly List<CheckBox> _caixas = new List<CheckBox>();
        readonly Button _criar;

        public List<Structure> Escolhidos { get; private set; }

        public JanelaEscolha(List<Structure> candidatos, string anel1Id, string anel2Id)
        {
            Escolhidos = new List<Structure>();

            Title = "Anéis de otimização";
            Width = 430;
            Height = 520;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            ResizeMode = ResizeMode.CanResize;

            var raiz = new Grid { Margin = new Thickness(16) };
            raiz.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            raiz.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            raiz.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

            // ---- cabeçalho ------------------------------------------------
            var cabecalho = new StackPanel { Margin = new Thickness(0, 0, 0, 12) };
            cabecalho.Children.Add(new TextBlock
            {
                Text = "Quais estruturas entram na soma?",
                FontWeight = FontWeights.SemiBold,
                FontSize = 14,
                Margin = new Thickness(0, 0, 0, 4)
            });
            cabecalho.Children.Add(new TextBlock
            {
                Text = "As de tipo PTV já vêm marcadas. Confira: um PTV a mais ou a "
                     + "menos muda os dois anéis.",
                TextWrapping = TextWrapping.Wrap,
                Foreground = Brushes.Gray
            });
            Grid.SetRow(cabecalho, 0);
            raiz.Children.Add(cabecalho);

            // ---- lista ----------------------------------------------------
            var pilha = new StackPanel();
            foreach (Structure s in candidatos)
            {
                // O tipo DICOM só decide o que vem MARCADO. A palavra final é
                // de quem está olhando a tela — auxiliares antigas costumam ter
                // nascido com tipo PTV e não devem entrar na soma.
                bool ehPtv = string.Equals(s.DicomType, "PTV", StringComparison.OrdinalIgnoreCase);

                var linha = new DockPanel();

                var volume = new TextBlock
                {
                    Text = string.Format("{0:0.0} cm³", s.Volume),
                    Foreground = Brushes.Gray,
                    Margin = new Thickness(12, 0, 0, 0)
                };
                DockPanel.SetDock(volume, Dock.Right);
                linha.Children.Add(volume);

                linha.Children.Add(new TextBlock
                {
                    Text = s.Id,
                    TextTrimming = TextTrimming.CharacterEllipsis
                });

                var caixa = new CheckBox
                {
                    Content = linha,
                    IsChecked = ehPtv,
                    Tag = s,
                    Margin = new Thickness(0, 4, 0, 4)
                };
                caixa.Checked += (a, b) => AtualizarBotao();
                caixa.Unchecked += (a, b) => AtualizarBotao();

                _caixas.Add(caixa);
                pilha.Children.Add(caixa);
            }

            var rolo = new ScrollViewer
            {
                Content = pilha,
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                BorderBrush = Brushes.LightGray,
                BorderThickness = new Thickness(1),
                Padding = new Thickness(10)
            };
            Grid.SetRow(rolo, 1);
            raiz.Children.Add(rolo);

            // ---- rodapé ---------------------------------------------------
            var rodape = new StackPanel { Margin = new Thickness(0, 12, 0, 0) };

            rodape.Children.Add(new TextBlock
            {
                Text = string.Format("Serão criados {0} (2 a 20 mm) e {1} (20 a 40 mm), "
                                   + "cortados pelo contorno externo.", anel1Id, anel2Id),
                TextWrapping = TextWrapping.Wrap,
                Foreground = Brushes.Gray,
                Margin = new Thickness(0, 0, 0, 12)
            });

            var botoes = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right
            };

            var cancelar = new Button
            {
                Content = "Cancelar",
                Width = 100,
                Height = 28,
                IsCancel = true,
                Margin = new Thickness(0, 0, 8, 0)
            };
            botoes.Children.Add(cancelar);

            _criar = new Button
            {
                Content = "Criar anéis",
                Width = 110,
                Height = 28,
                IsDefault = true
            };
            _criar.Click += Criar_Click;
            botoes.Children.Add(_criar);

            rodape.Children.Add(botoes);
            Grid.SetRow(rodape, 2);
            raiz.Children.Add(rodape);

            Content = raiz;
            AtualizarBotao();
        }

        /// <summary>
        /// Botão aceso significa pronto: sem nenhuma estrutura marcada não há
        /// soma, e o clique só teria como resposta um aviso de erro.
        /// </summary>
        void AtualizarBotao()
        {
            int marcadas = _caixas.Count(c => c.IsChecked == true);
            _criar.IsEnabled = marcadas > 0;
            _criar.ToolTip = marcadas > 0
                ? null
                : "Marque ao menos uma estrutura para somar.";
        }

        void Criar_Click(object remetente, RoutedEventArgs e)
        {
            Escolhidos = _caixas
                .Where(c => c.IsChecked == true)
                .Select(c => (Structure)c.Tag)
                .ToList();

            DialogResult = true;
        }
    }
}
