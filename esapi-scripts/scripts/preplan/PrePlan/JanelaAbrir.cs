using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using VMS.TPS.Common.Model.API;
using EsapiApp = VMS.TPS.Common.Model.API.Application;

namespace VMS.TPS
{
    /// <summary>
    /// Escolher paciente e structure set — o passo que o Eclipse já tinha feito
    /// quando o script roda como plug-in.
    ///
    /// A busca exige texto e não lista tudo: <c>PatientSummaries</c> é o banco
    /// inteiro do serviço, e uma lista com todos os pacientes é uma lista em que
    /// se clica no vizinho de baixo por engano.
    /// </summary>
    public class JanelaAbrir : Window
    {
        readonly EsapiApp _aplicacao;

        readonly TextBox _busca = new TextBox();
        readonly ListBox _pacientes = new ListBox { Height = 180 };
        readonly ComboBox _conjuntos = new ComboBox { IsEnabled = false };
        readonly TextBlock _situacao = new TextBlock { Foreground = Brushes.Gray, TextWrapping = TextWrapping.Wrap };
        readonly Button _continuar = new Button { Content = "Continuar", Width = 110, Height = 28, IsDefault = true, IsEnabled = false };

        /// <summary>Quantos resultados a busca mostra. Mais que isto não se lê.</summary>
        const int MAXIMO_DE_ACHADOS = 40;

        public Patient Paciente { get; private set; }
        public StructureSet Conjunto { get; private set; }

        public JanelaAbrir(EsapiApp aplicacao, string buscaInicial)
        {
            _aplicacao = aplicacao;

            Title = "PrePlan — abrir paciente";
            Width = 520;
            Height = 480;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;

            var raiz = new StackPanel { Margin = new Thickness(16) };

            raiz.Children.Add(new TextBlock
            {
                Text = "Id do paciente, ou parte do nome",
                Margin = new Thickness(0, 0, 0, 4)
            });

            var linhaBusca = new DockPanel { Margin = new Thickness(0, 0, 0, 8) };
            var procurar = new Button { Content = "Procurar", Width = 90, Height = 24, Margin = new Thickness(8, 0, 0, 0) };
            DockPanel.SetDock(procurar, Dock.Right);
            procurar.Click += (a, b) => Procurar();
            linhaBusca.Children.Add(procurar);
            _busca.Text = buscaInicial;
            _busca.KeyDown += (a, b) =>
            {
                if (b.Key == System.Windows.Input.Key.Enter)
                    Procurar();
            };
            linhaBusca.Children.Add(_busca);
            raiz.Children.Add(linhaBusca);

            _pacientes.SelectionChanged += (a, b) => AbrirPaciente();
            raiz.Children.Add(_pacientes);

            raiz.Children.Add(new TextBlock
            {
                Text = "Structure set",
                Margin = new Thickness(0, 12, 0, 4)
            });
            _conjuntos.SelectionChanged += (a, b) => Revisar();
            raiz.Children.Add(_conjuntos);

            _situacao.Margin = new Thickness(0, 10, 0, 0);
            raiz.Children.Add(_situacao);

            var botoes = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right,
                Margin = new Thickness(0, 14, 0, 0)
            };
            botoes.Children.Add(new Button
            {
                Content = "Cancelar",
                Width = 100,
                Height = 28,
                IsCancel = true,
                Margin = new Thickness(0, 0, 8, 0)
            });
            _continuar.Click += (a, b) => Continuar();
            botoes.Children.Add(_continuar);
            raiz.Children.Add(botoes);

            Content = raiz;

            if (!string.IsNullOrWhiteSpace(buscaInicial))
                Loaded += (a, b) => Procurar();
        }

        void Procurar()
        {
            string texto = _busca.Text.Trim();
            _pacientes.Items.Clear();
            _conjuntos.Items.Clear();
            _conjuntos.IsEnabled = false;
            Paciente = null;
            Conjunto = null;
            Revisar();

            if (texto.Length < 2)
            {
                _situacao.Text = "Digite ao menos dois caracteres.";
                return;
            }

            List<PatientSummary> achados;
            try
            {
                achados = _aplicacao.PatientSummaries
                    .Where(s => Casa(s, texto))
                    .OrderBy(s => s.LastName, StringComparer.CurrentCultureIgnoreCase)
                    .Take(MAXIMO_DE_ACHADOS + 1)
                    .ToList();
            }
            catch (Exception e)
            {
                _situacao.Text = "A busca falhou: " + e.Message;
                return;
            }

            bool demais = achados.Count > MAXIMO_DE_ACHADOS;
            foreach (PatientSummary s in achados.Take(MAXIMO_DE_ACHADOS))
                _pacientes.Items.Add(new ListBoxItem
                {
                    Content = s.Id + "      " + s.LastName + ", " + s.FirstName,
                    Tag = s
                });

            _situacao.Text = _pacientes.Items.Count == 0
                ? "Nenhum paciente encontrado."
                : demais
                    ? "Mais de " + MAXIMO_DE_ACHADOS + " encontrados — refine a busca."
                    : _pacientes.Items.Count + " encontrado(s).";
        }

        static bool Casa(PatientSummary s, string texto)
        {
            return Contem(s.Id, texto) || Contem(s.LastName, texto) || Contem(s.FirstName, texto);
        }

        static bool Contem(string valor, string texto)
        {
            return valor != null &&
                   valor.IndexOf(texto, StringComparison.CurrentCultureIgnoreCase) >= 0;
        }

        void AbrirPaciente()
        {
            var item = _pacientes.SelectedItem as ListBoxItem;
            if (item == null)
                return;

            _conjuntos.Items.Clear();
            _conjuntos.IsEnabled = false;
            Conjunto = null;

            try
            {
                // Só um paciente por sessão: abrir o segundo sem fechar o
                // primeiro é recusado pela API.
                if (Paciente != null)
                    _aplicacao.ClosePatient();

                Paciente = _aplicacao.OpenPatient((PatientSummary)item.Tag);
            }
            catch (Exception e)
            {
                Paciente = null;
                _situacao.Text = "Não foi possível abrir o paciente: " + e.Message;
                Revisar();
                return;
            }

            var conjuntos = new List<StructureSet>();
            try
            {
                conjuntos = Paciente.StructureSets
                    .OrderByDescending(ss => ss.HistoryDateTime)
                    .ToList();
            }
            catch (Exception)
            {
            }

            foreach (StructureSet ss in conjuntos)
                _conjuntos.Items.Add(new ComboBoxItem { Content = Descrever(ss), Tag = ss });

            _conjuntos.IsEnabled = _conjuntos.Items.Count > 0;
            if (_conjuntos.Items.Count > 0)
                _conjuntos.SelectedIndex = 0;

            _situacao.Text = _conjuntos.Items.Count == 0
                ? "Este paciente não tem structure set — sem ele não há alvo nem isocentro."
                : Paciente.Id + " aberto.";

            Revisar();
        }

        static string Descrever(StructureSet ss)
        {
            string imagem;
            try
            {
                imagem = ss.Image == null ? "(sem imagem)" : ss.Image.Id;
            }
            catch (Exception)
            {
                imagem = "(?)";
            }

            int quantas;
            try
            {
                quantas = ss.Structures.Count();
            }
            catch (Exception)
            {
                quantas = -1;
            }

            return ss.Id + "      imagem " + imagem +
                   (quantas < 0 ? "" : "      " + quantas + " estruturas");
        }

        void Revisar()
        {
            var item = _conjuntos.SelectedItem as ComboBoxItem;
            Conjunto = item == null ? null : (StructureSet)item.Tag;

            _continuar.IsEnabled = Paciente != null && Conjunto != null;
            _continuar.ToolTip = _continuar.IsEnabled
                ? null
                : "Escolha um paciente e um structure set.";
        }

        void Continuar()
        {
            if (Paciente == null || Conjunto == null)
                return;
            DialogResult = true;
        }
    }
}
