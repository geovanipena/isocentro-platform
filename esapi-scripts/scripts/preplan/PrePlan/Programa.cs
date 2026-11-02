using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Windows;
using EsapiApp = VMS.TPS.Common.Model.API.Application;

namespace VMS.TPS
{
    /// <summary>
    /// A porta de entrada do .EXE — o mesmo código do plug-in, rodado por fora
    /// do Eclipse, pelo .bat.
    ///
    /// Vale a pena por dois motivos. O primeiro é hoje: o Eclipse guarda o
    /// script pela identidade do assembly e NÃO deixa reimportar por cima, então
    /// cada rodada de desenvolvimento precisava de um nome novo e de uma volta
    /// inteira pela tela de aprovação. O .exe se roda de novo apertando a seta
    /// para cima.
    ///
    /// O segundo é depois: <c>Optimize</c> e <c>CalculateDose</c> só são
    /// liberados em aplicativo standalone. É por esta porta que eles entram, no
    /// dia em que entrarem.
    /// </summary>
    public static class Programa
    {
        [STAThread]
        public static int Main(string[] args)
        {
            // O resolvedor tem de estar de pé ANTES de o JIT tocar em qualquer
            // tipo da ESAPI — e o JIT compila um método inteiro ao entrar nele.
            // Por isso este Main não menciona nenhum: quem fala com a API é o
            // Abrir, que só é compilado quando chamado, com o resolvedor já
            // registrado. Sem essa separação, o processo morre antes da
            // primeira linha, com FileNotFoundException.
            AppDomain.CurrentDomain.AssemblyResolve += Resolver;

            // "Onde" não toca na ESAPI: só mostra onde ela seria procurada, e em
            // que ordem. É a primeira pergunta quando o executável não abre numa
            // estação — e a única que se responde sem sessão, sem licença e sem
            // paciente aberto.
            if (args.Length > 0 && args[0] == "--onde")
            {
                foreach (string pasta in Pastas())
                    Console.WriteLine((Directory.Exists(pasta) ? "existe    " : "não existe") +
                                      "   " + pasta);
                return 0;
            }

            return Abrir(args);
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        static int Abrir(string[] args)
        {
            EsapiApp aplicacao;
            try
            {
                // Sem usuário e senha: entra com a identidade do Windows. É por
                // isso que o .bat pode precisar de runas /netonly numa máquina
                // fora do domínio.
                aplicacao = EsapiApp.CreateApplication();
            }
            catch (Exception e)
            {
                Erro("Não foi possível abrir a sessão da ESAPI.\n\n" +
                     e.GetType().Name + ": " + e.Message + "\n\n" +
                     "As causas de sempre: licença Eclipse Automation ausente, usuário sem " +
                     "permissão de API, ou identidade de rede errada (ver runas /netonly no README).");
                return 2;
            }

            try
            {
                Console.WriteLine("PrePlan — sessão aberta como " + Ler(() => aplicacao.CurrentUser.Id));

                var abrir = new JanelaAbrir(aplicacao, args.Length > 0 ? args[0] : "");
                if (abrir.ShowDialog() != true)
                {
                    Console.WriteLine("Cancelado.");
                    return 1;
                }

                Fluxo.Rodar(new Bancada(aplicacao, abrir.Paciente, abrir.Conjunto));
                return 0;
            }
            catch (Exception e)
            {
                Erro("Erro inesperado:\n\n" + e.GetType().Name + ": " + e.Message +
                     "\n\n" + e.StackTrace);
                return 3;
            }
            finally
            {
                // Fechar e descartar sempre: uma sessão de ESAPI que fica
                // pendurada segura licença e trava a próxima rodada.
                try { aplicacao.ClosePatient(); }
                catch (Exception) { }
                try { aplicacao.Dispose(); }
                catch (Exception) { }
            }
        }

        static string Ler(Func<string> leitura)
        {
            try { return leitura(); }
            catch (Exception) { return "(?)"; }
        }

        static void Erro(string texto)
        {
            Console.Error.WriteLine(texto);
            MessageBox.Show(texto, "PrePlan", MessageBoxButton.OK, MessageBoxImage.Error);
        }

        // -------------------------------------------------------------------
        // Onde estão as DLLs da Varian
        // -------------------------------------------------------------------

        /// <summary>
        /// O .NET procura as dependências ao lado do EXE, e as DLLs da ESAPI
        /// são licenciadas: copiá-las para junto do executável espalharia cópia
        /// de arquivo licenciado por aí. Então o executável as busca onde elas
        /// já estão instalados.
        /// </summary>
        static Assembly Resolver(object remetente, ResolveEventArgs e)
        {
            string nome;
            try
            {
                nome = new AssemblyName(e.Name).Name;
            }
            catch (Exception)
            {
                return null;
            }

            if (!nome.StartsWith("VMS.", StringComparison.OrdinalIgnoreCase))
                return null;

            foreach (string pasta in Pastas())
            {
                try
                {
                    string caminho = Path.Combine(pasta, nome + ".dll");
                    if (File.Exists(caminho))
                        return Assembly.LoadFrom(caminho);
                }
                catch (Exception)
                {
                    // Pasta inacessível é pasta que não serve: seguir para a
                    // próxima vale mais que derrubar a abertura aqui.
                }
            }

            return null;
        }

        static IEnumerable<string> Pastas()
        {
            // 1. O que a estação mandar, se mandar. É a saída para instalação
            //    fora do padrão — e para apontar uma versão específica quando a
            //    máquina tem duas.
            string doAmbiente = Environment.GetEnvironmentVariable("PREPLAN_ESAPI");
            if (!string.IsNullOrWhiteSpace(doAmbiente))
                yield return doAmbiente;

            // 2. Ao lado do executável.
            string aoLado = null;
            try
            {
                aoLado = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            }
            catch (Exception)
            {
            }
            if (!string.IsNullOrWhiteSpace(aoLado))
                yield return aoLado;

            // 3. As instalações da Varian, da versão mais nova para a mais
            //    antiga. Ordenar como VERSÃO, não como texto: por texto, "9.0"
            //    vem depois de "15.6".
            foreach (string raiz in new[] { @"C:\Program Files\Varian\RTM",
                                            @"C:\Program Files (x86)\Varian\RTM" })
            {
                string[] versoes;
                try
                {
                    if (!Directory.Exists(raiz))
                        continue;
                    versoes = Directory.GetDirectories(raiz);
                }
                catch (Exception)
                {
                    continue;
                }

                foreach (string versao in versoes.OrderByDescending(Numero))
                    yield return Path.Combine(versao, @"esapi\API");
            }
        }

        /// <summary>
        /// System.Version escrito por extenso: dentro do namespace VMS.TPS,
        /// "Version" sozinho resolve para o namespace VMS.TPS.Version, da
        /// própria ESAPI, e o compilador para dizendo que um namespace está
        /// sendo usado como tipo.
        /// </summary>
        static System.Version Numero(string pasta)
        {
            System.Version v;
            if (System.Version.TryParse(Path.GetFileName(pasta), out v))
                return v;
            return new System.Version(0, 0);
        }
    }
}
