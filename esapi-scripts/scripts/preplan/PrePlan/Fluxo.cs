using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Windows;
using VMS.TPS.Common.Model.API;

namespace VMS.TPS
{
    /// <summary>
    /// O caminho do script, do paciente aberto até a mensagem final.
    ///
    /// Está fora do <see cref="Script"/> porque são DOIS hospedeiros: o
    /// plug-in do Eclipse e o .exe que roda pelo .bat. Uma segunda cópia deste
    /// caminho para o standalone seria a maneira mais fácil de o .exe e o
    /// plug-in passarem a montar planos diferentes — e ninguém notaria até um
    /// deles montar errado.
    /// </summary>
    public static class Fluxo
    {
        public static void Rodar(Bancada bancada)
        {
            StructureSet ss = bancada.Conjunto;

            if (ss.Image == null)
            {
                Avisar("Este structure set não está ligado a uma imagem.\n\n" +
                       "O isocentro é uma coordenada da imagem — sem ela não há onde pôr o plano.");
                return;
            }

            // Alvo: qualquer estrutura preenchida. Quem escolhe é o usuário — o
            // alvo decide o isocentro E a abertura do colimador, e um filtro por
            // prefixo "PTV" pegaria junto PTV_eval, PTV_old e as auxiliares que
            // sobraram de casos anteriores.
            List<Structure> alvos = ss.Structures
                .Where(s => !s.IsEmpty)
                .OrderBy(s => s.Id, StringComparer.CurrentCultureIgnoreCase)
                .ToList();

            if (alvos.Count == 0)
            {
                Avisar("Este structure set não tem nenhuma estrutura preenchida.\n\n" +
                       "O alvo é o que define o isocentro e a abertura dos campos.");
                return;
            }

            // O curso NÃO é criado por este script. Abrir curso é decisão
            // clínica e administrativa (é o que o serviço fatura e acompanha);
            // um script de pré-planejamento que cria curso sozinho acaba
            // deixando "Curso 2" vazio atrás de si.
            List<Course> cursos = bancada.Paciente.Courses
                .OrderBy(c => c.Id, StringComparer.CurrentCultureIgnoreCase)
                .ToList();

            if (cursos.Count == 0)
            {
                Avisar("Este paciente não tem nenhum curso.\n\n" +
                       "Crie o curso no Eclipse e rode de novo — abrir curso é " +
                       "decisão do serviço, não de script.");
                return;
            }

            var janela = new JanelaPrePlan(bancada, cursos, alvos);
            if (janela.ShowDialog() != true)
                return;                                  // cancelado pelo usuário

            Pedido pedido = janela.Pedido;
            Resultado resultado;

            try
            {
                resultado = Montagem.Montar(bancada, pedido);
            }
            catch (MontagemImpossivel e)
            {
                // Recusa antes de escrever: nada foi criado.
                Avisar(e.Message);
                return;
            }
            catch (Exception e)
            {
                // Qualquer outra coisa pode ter deixado um plano pela metade, e
                // a mensagem precisa dizer isso — um plano incompleto no curso é
                // pior que nenhum, porque parece um plano.
                Avisar("A montagem parou com um erro inesperado:\n\n" +
                       e.GetType().Name + ": " + e.Message + "\n\n" +
                       "Confira o curso no Eclipse: pode ter ficado um plano incompleto.");
                return;
            }

            // Guarda a leitura que o Eclipse ACEITOU, não a que foi digitada: se
            // a energia foi digitada "6X-FFF" e só passou como "6X" + fluência
            // "FFF", guardar a digitada faria a próxima vez oferecer de novo a
            // que falhou. E só guarda depois de os campos existirem.
            if (!resultado.Incompleto && resultado.Equipamento != null)
                Maquinas.Lembrar(resultado.Equipamento);

            MostrarResultado(resultado, pedido);
            OferecerApagar(bancada, resultado, pedido);
        }

        static void MostrarResultado(Resultado r, Pedido p)
        {
            var msg = new StringBuilder();
            foreach (string linha in r.Relatorio)
                msg.AppendLine(linha);

            if (r.Avisos.Count > 0)
            {
                msg.AppendLine();
                msg.AppendLine("ATENÇÃO");
                foreach (string aviso in r.Avisos)
                    msg.AppendLine("   " + aviso);
            }

            // "O script rodou" e "o plano está pronto" são coisas diferentes, e
            // esta lista é a diferença. Sem ela, um plano sem modelo de cálculo
            // e sem objetivos parece pronto para otimizar — e só na hora de
            // apertar Optimize é que a falta aparece, com o planejador achando
            // que o script já tinha resolvido.
            msg.AppendLine();
            msg.AppendLine("FALTA, antes de otimizar:");
            msg.AppendLine("   • conferir o isocentro e a abertura dos campos no BEV");
            msg.AppendLine("   • modelo de cálculo e de otimização (os nomes são de cada");
            msg.AppendLine("     serviço; o script não os escolhe)");
            msg.AppendLine("   • objetivos do alvo e dos órgãos de risco");
            if (p.Tecnica == Tecnica.CamposFixos)
            {
                msg.AppendLine("   • marcar o plano como IMRT: os campos saem estáticos, e é o");
                msg.AppendLine("     otimizador que os transforma em fluência");
            }

            MessageBoxImage icone = r.Avisos.Count > 0
                ? MessageBoxImage.Exclamation
                : MessageBoxImage.Information;

            MessageBox.Show(msg.ToString(), Script.NOME, MessageBoxButton.OK, icone);
        }

        /// <summary>
        /// Plano criado e sem nenhum campo é lixo que parece trabalho: ele
        /// aparece na lista do curso com nome de plano. Como a tentativa que
        /// falhou vai ser repetida em seguida com a máquina certa, sobrariam
        /// dois, três planos vazios.
        ///
        /// Apagar é destrutivo, então PERGUNTA — e a pergunta nasce em "Não".
        /// Só se oferece para o plano que este script acabou de criar e que não
        /// tem campo nenhum dentro.
        /// </summary>
        static void OferecerApagar(Bancada bancada, Resultado r, Pedido p)
        {
            if (!r.SemCampos || r.Plano == null)
                return;

            if (!p.Curso.CanRemovePlanSetup(r.Plano))
                return;

            MessageBoxResult resposta = MessageBox.Show(
                "O plano " + r.Plano.Id + " foi criado e ficou sem nenhum campo.\n\n" +
                "Apagar esse plano vazio?",
                Script.NOME, MessageBoxButton.YesNo, MessageBoxImage.Question,
                MessageBoxResult.No);

            if (resposta != MessageBoxResult.Yes)
                return;

            try
            {
                string id = r.Plano.Id;
                p.Curso.RemovePlanSetup(r.Plano);
                bancada.Salvar();
                MessageBox.Show("Plano " + id + " apagado.", Script.NOME,
                                MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception e)
            {
                Avisar("Não foi possível apagar o plano: " + e.Message.Trim() +
                       "\n\nApague no Eclipse.");
            }
        }

        public static void Avisar(string texto)
        {
            MessageBox.Show(texto, Script.NOME, MessageBoxButton.OK, MessageBoxImage.Exclamation);
        }
    }
}
