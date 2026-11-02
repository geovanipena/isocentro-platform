using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

namespace VMS.TPS
{
    /// <summary>
    /// Recusa ANTES de escrever qualquer coisa. Depois da primeira escrita não
    /// se lança mais isto: o que já foi criado tem de aparecer no relatório, e
    /// não sumir dentro de uma mensagem de erro.
    /// </summary>
    public class MontagemImpossivel : Exception
    {
        public MontagemImpossivel(string motivo) : base(motivo) { }
    }

    public class Resultado
    {
        public ExternalPlanSetup Plano;
        public List<string> Relatorio = new List<string>();
        public List<string> Avisos = new List<string>();
        public bool Incompleto;

        /// <summary>
        /// O plano foi criado e ficou sem nenhum campo. Não é o mesmo que
        /// "incompleto": aqui não sobrou nada de aproveitável, e o plano vazio
        /// no curso é justamente o que faz alguém pensar que o script montou
        /// alguma coisa.
        /// </summary>
        public bool SemCampos;

        /// <summary>
        /// A leitura de energia que o Eclipse ACEITOU — não necessariamente a
        /// que foi digitada. É esta que vai para o histórico da estação: a
        /// digitada pode ter sido a que falhou.
        /// </summary>
        public Equipamento Equipamento;
    }

    /// <summary>
    /// A escrita no banco clínico. Tudo o que decide alguma coisa já foi
    /// decidido no <see cref="Pedido"/>; aqui só se executa e se relata.
    /// </summary>
    public static class Montagem
    {
        /// <summary>
        /// Pontos de controle por arco. 178 é o padrão do Eclipse para um arco
        /// de ~360°, e é só isso que os pesos definem: o otimizador reescreve
        /// todos eles — peso, MLC e UM.
        /// </summary>
        const int CONTROLES_POR_ARCO = 178;

        /// <summary>
        /// Arco de 360° cheio não existe: início e fim iguais seriam um arco de
        /// zero grau. 181 a 179 é a convenção do Eclipse, e deixa o ponto morto
        /// atrás do paciente supino, não sobre ele.
        /// </summary>
        const double ARCO_INICIO = 181.0;
        const double ARCO_FIM = 179.0;

        /// <summary>
        /// Abertura provisória dos campos fixos, em mm. Ela é SUBSTITUÍDA pelo
        /// FitCollimatorToStructure logo em seguida — mas o AddStaticBeam exige
        /// um valor, e este fica no lugar se o ajuste falhar. Por isso a falha
        /// do ajuste vira aviso e não é engolida: 10x10 num alvo grande é um
        /// plano com cara de pronto.
        /// </summary>
        static readonly VRect<double> ABERTURA_PROVISORIA = new VRect<double>(-50, -50, 50, 50);

        public static Resultado Montar(Bancada bancada, Pedido p)
        {
            var r = new Resultado();
            StructureSet ss = bancada.Conjunto;

            // BeginModifications vem ANTES de qualquer pergunta sobre escrita.
            // O CanAddPlanSetup responde sobre o estado ATUAL do paciente, e num
            // paciente que ainda não foi aberto para modificação a resposta é
            // sempre "não" — a recusa não fala do curso, fala do modo. Custou
            // uma rodada no plug-in dos anéis, com o CanAddStructure.
            bancada.Paciente.BeginModifications();

            if (!p.Curso.CanAddPlanSetup(ss))
                throw new MontagemImpossivel(
                    "O curso " + p.Curso.Id + " não aceita um plano novo com este structure set.\n\n" +
                    "Em geral é curso ou structure set aprovado/completado. " +
                    "Resolva no Eclipse e rode de novo.");

            // ---------------------------------------------------------------
            // A partir daqui já se escreve no banco clínico.
            // ---------------------------------------------------------------
            ExternalPlanSetup plano = p.Curso.AddExternalPlanSetup(ss);
            r.Plano = plano;

            // O Id do plano tem limite de tamanho e precisa ser único no curso.
            // Se o Eclipse recusar, o plano JÁ existe com o Id automático — o
            // certo é seguir e avisar, não abortar deixando para trás um plano
            // com nome que ninguém reconhece.
            try
            {
                plano.Id = p.IdPlano;
            }
            catch (Exception e)
            {
                r.Avisos.Add("O nome " + p.IdPlano + " não foi aceito (" + e.Message.Trim() +
                             "). O plano ficou como " + plano.Id + " — renomeie no Eclipse.");
            }

            try
            {
                // O terceiro parâmetro é a porcentagem do tratamento como
                // FRAÇÃO: 1.0 é 100%. Passar 100 aqui daria uma prescrição cem
                // vezes maior, e isso não aparece em lugar nenhum até a
                // normalização sair errada.
                plano.SetPrescription(p.Fracoes,
                                      new DoseValue(p.DosePorFracaoCGy, DoseValue.DoseUnit.cGy),
                                      1.0);
            }
            catch (Exception e)
            {
                r.Avisos.Add("A prescrição não foi gravada (" + e.Message.Trim() +
                             "). Preencha no Eclipse.");
            }

            // A lista é preenchida por dentro, e não devolvida no fim: se o
            // segundo arco falhar, o PRIMEIRO já existe no plano, e ele tem de
            // aparecer no relatório e receber o ajuste de colimador. Devolver a
            // lista só no sucesso faria o script perder de vista um campo que
            // está lá no banco.
            var feixes = new List<Beam>();
            Exception ultimaFalha = null;

            foreach (Equipamento leitura in Leituras(p))
            {
                var maquina = new ExternalBeamMachineParameters(
                    leitura.Maquina, leitura.Energia, leitura.TaxaDose, leitura.Tecnica,
                    string.IsNullOrWhiteSpace(leitura.Fluencia) ? null : leitura.Fluencia);

                try
                {
                    if (p.Tecnica == Tecnica.Vmat)
                        Arcos(plano, maquina, p, feixes);
                    else
                        CamposFixos(plano, maquina, p, feixes);

                    r.Equipamento = leitura;
                    ultimaFalha = null;
                    break;
                }
                catch (Exception e)
                {
                    // Máquina, energia, fluência ou técnica que não existem na
                    // configuração do serviço estouram aqui, na chamada de
                    // AddBeam.
                    ultimaFalha = e;

                    // Se algum campo JÁ foi criado, a segunda leitura não é
                    // tentada: ela criaria campos repetidos por cima dos que
                    // estão lá. Só se repete quando nada foi gravado.
                    if (feixes.Count > 0)
                        break;
                }
            }

            if (ultimaFalha != null)
            {
                r.Incompleto = true;
                r.Avisos.Add(DiagnosticoDeFeixe(bancada.Paciente, p, ultimaFalha));
            }

            r.SemCampos = feixes.Count == 0;

            // ---- colimador -------------------------------------------------
            // Um try por feixe: o arco que não coube não pode impedir o outro
            // de ser ajustado, e a lista de avisos diz qual foi.
            foreach (Beam feixe in feixes)
            {
                try
                {
                    feixe.FitCollimatorToStructure(
                        new FitToStructureMargins(p.MargemColimadorMm),
                        p.Alvo,
                        true,   // jaws X assimétricas: abraçam o alvo em vez de
                        true,   // jaws Y assimétricas: espelhar a metade maior
                        p.OtimizarRotacaoDoColimador);
                }
                catch (Exception e)
                {
                    r.Incompleto = true;
                    r.Avisos.Add(feixe.Id + ": o colimador não foi ajustado ao alvo (" +
                                 e.Message.Trim() + "). Ficou com a abertura provisória — " +
                                 "ajuste no Eclipse antes de otimizar.");
                }
            }

            // ---- NTO -------------------------------------------------------
            if (p.AdicionarNto)
            {
                try
                {
                    plano.OptimizationSetup.AddAutomaticNormalTissueObjective(p.PrioridadeNto);
                }
                catch (Exception e)
                {
                    r.Avisos.Add("O NTO automático não foi adicionado (" + e.Message.Trim() + ").");
                }
            }

            // ---- gravação --------------------------------------------------
            // Uma linha, num lugar só. Dentro do Eclipse não faz nada; fora
            // dele, é ela que põe tudo no banco — e sem ela o script rodaria
            // inteiro, o relatório sairia bonito e o banco não mudaria.
            try
            {
                bancada.Salvar();
            }
            catch (Exception e)
            {
                r.Incompleto = true;
                r.Avisos.Add("A GRAVAÇÃO FALHOU: " + e.Message.Trim() + "\n\n" +
                             "Nada do que está descrito acima foi para o banco.");
            }

            Relatar(r, plano, feixes, ss, p);
            r.Relatorio.Add("");
            r.Relatorio.Add(bancada.ComoSalva);
            return r;
        }

        static void Arcos(ExternalPlanSetup plano, ExternalBeamMachineParameters maquina,
                          Pedido p, List<Beam> feixes)
        {
            // Dois arcos com colimadores opostos (30 e 330, por padrão): o
            // vazamento entre lâminas de um cai onde o outro não tem junta.
            // Dois arcos com colimador em 0 empilham o vazamento das duas
            // passagens na mesma linha.
            var arcos = new[]
            {
                new
                {
                    Colimador = p.ColimadorArco1,
                    Inicio = ARCO_INICIO,
                    Fim = ARCO_FIM,
                    Sentido = GantryDirection.Clockwise
                },
                new
                {
                    Colimador = p.ColimadorArco2,
                    Inicio = ARCO_FIM,
                    Fim = ARCO_INICIO,
                    Sentido = GantryDirection.CounterClockwise
                }
            };

            for (int i = 0; i < arcos.Length; i++)
            {
                Beam feixe = plano.AddVMATBeam(
                    maquina,
                    PesosIguais(CONTROLES_POR_ARCO),
                    arcos[i].Colimador,
                    arcos[i].Inicio,
                    arcos[i].Fim,
                    arcos[i].Sentido,
                    0.0,                  // mesa em 0
                    p.Isocentro);

                Nomear(feixe, "Arco" + (i + 1));
                feixes.Add(feixe);
            }
        }

        static void CamposFixos(ExternalPlanSetup plano, ExternalBeamMachineParameters maquina,
                                Pedido p, List<Beam> feixes)
        {
            double[] angulos = p.AngulosDeGantry();

            for (int i = 0; i < angulos.Length; i++)
            {
                // Campo estático aberto, com as jaws ajustadas ao alvo logo
                // abaixo. É o mesmo ponto de partida de quem cria os campos à
                // mão: quem transforma isto em IMRT é o otimizador do Eclipse,
                // com o plano marcado como IMRT.
                Beam feixe = plano.AddStaticBeam(
                    maquina,
                    ABERTURA_PROVISORIA,
                    p.ColimadorCamposFixos,
                    angulos[i],
                    0.0,                  // mesa em 0
                    p.Isocentro);

                Nomear(feixe, "C" + (i + 1));
                feixes.Add(feixe);
            }
        }

        /// <summary>
        /// As leituras possíveis do par energia/fluência, na ordem em que valem
        /// a tentativa.
        ///
        /// O Eclipse EXIBE a energia como "6X-FFF", mas o
        /// ExternalBeamMachineParameters quer "6X" na energia e "FFF" no modo
        /// de fluência. Passar o nome de exibição inteiro dá
        /// <c>ApplicationException: External beam configuration not found</c>,
        /// com a máquina, a taxa e a técnica idênticas às de um plano que já
        /// existe — foi assim que a primeira rodada real falhou, em 03/09/2026.
        ///
        /// E não há como perguntar qual é a certa: o ExternalBeamTreatmentUnit
        /// não lista energias (conferido por reflexão na 15.6). Então tenta-se
        /// a leitura oposta — e só enquanto nenhum campo tiver sido criado, que
        /// é quando repetir não duplica nada.
        /// </summary>
        public static List<Equipamento> Leituras(Pedido p)
        {
            var leituras = new List<Equipamento>();
            var vistas = new HashSet<string>();

            // O produto de duas dúvidas: como a energia se parte, e como a
            // técnica se chama. Cada uma tem duas leituras plausíveis, e a
            // ordem é a da confiança — primeiro o que a doc oficial diz, por
            // último o que foi colhido do plano vizinho.
            foreach (string tecnica in new[] { p.TecnicaId, p.TecnicaAlternativa })
            {
                if (string.IsNullOrWhiteSpace(tecnica))
                    continue;

                foreach (Equipamento energia in Energias(p))
                {
                    var leitura = new Equipamento
                    {
                        Maquina = p.Maquina,
                        Energia = energia.Energia,
                        Fluencia = energia.Fluencia,
                        TaxaDose = p.TaxaDose,
                        Tecnica = tecnica.Trim(),
                        Arco = p.Tecnica == Tecnica.Vmat
                    };

                    if (vistas.Add(leitura.Chave()))
                        leituras.Add(leitura);
                }
            }

            return leituras;
        }

        /// <summary>
        /// As duas leituras possíveis do par energia/fluência.
        ///
        /// A doc oficial do ExternalBeamMachineParameters (15.6) é explícita: o
        /// energyModeId é "6X", e o primaryFluenceModeId aceita null, vazio,
        /// "SRS" ou "FFF". O que o Eclipse EXIBE, porém, é "6X-FFF" — os dois
        /// grudados. Quem digita copia da tela, e a tela mostra o grudado.
        /// </summary>
        static List<Equipamento> Energias(Pedido p)
        {
            var energias = new List<Equipamento>();

            energias.Add(new Equipamento
            {
                Energia = p.Energia,
                Fluencia = p.ModoFluencia
            });

            var alternativa = new Equipamento();
            if (string.IsNullOrWhiteSpace(p.ModoFluencia))
            {
                // Digitou "6X-FFF" com a fluência vazia: tentar separado.
                Maquinas.SepararEnergia(p.Energia, alternativa);
                if (!string.IsNullOrWhiteSpace(alternativa.Fluencia))
                    energias.Add(alternativa);
            }
            else
            {
                // Digitou separado: tentar junto, para o serviço em que a
                // energia se chame mesmo "6X-FFF".
                alternativa.Energia = p.Energia + "-" + p.ModoFluencia;
                alternativa.Fluencia = null;
                energias.Add(alternativa);
            }

            return energias;
        }

        /// <summary>
        /// Quando o AddBeam recusa, a mensagem precisa mostrar o que foi
        /// PEDIDO e o que existe para comparar — não uma frase dizendo que
        /// alguma das strings está errada.
        ///
        /// As quatro vão entre colchetes de propósito: espaço sobrando no fim
        /// de um nome colado de outra tela é invisível em qualquer outro
        /// formato, e é motivo de recusa.
        /// </summary>
        static string DiagnosticoDeFeixe(Patient paciente, Pedido p, Exception e)
        {
            var sb = new StringBuilder();
            sb.AppendLine("A criação dos campos parou. O plano foi criado e ficou vazio.");
            sb.AppendLine();
            sb.AppendLine(e.GetType().Name + ": " + e.Message.Trim());

            // A ESAPI costuma pôr o motivo real na exceção de dentro — a de
            // fora diz só que a operação falhou.
            for (Exception dentro = e.InnerException; dentro != null; dentro = dentro.InnerException)
                sb.AppendLine("   causa: " + dentro.Message.Trim());

            sb.AppendLine();
            sb.AppendLine("Foi tentado, nesta ordem:");
            foreach (Equipamento leitura in Leituras(p))
                sb.AppendLine("   máquina [" + leitura.Maquina + "]  energia [" + leitura.Energia +
                              "]  fluência [" + (leitura.Fluencia == null ? "" : leitura.Fluencia) +
                              "]  taxa [" + leitura.TaxaDose + "]  técnica [" + leitura.Tecnica + "]");
            sb.AppendLine("   como " + (p.Tecnica == Tecnica.Vmat ? "arcos de VMAT" : "campos fixos"));

            List<Equipamento> conhecidos = Maquinas.Conhecidos(paciente);
            sb.AppendLine();
            if (conhecidos.Count == 0)
            {
                sb.AppendLine("Este paciente não tem nenhum campo gravado para comparar. " +
                              "Abra um plano de outro paciente na mesma máquina e copie de lá " +
                              "a máquina, a energia e o Id de técnica.");
            }
            else
            {
                sb.AppendLine("O que já existe gravado neste paciente (máquina / energia / taxa / técnica):");
                foreach (Equipamento eq in conhecidos)
                    sb.AppendLine("   " + eq + (eq.Arco ? "   (arco)" : "   (fixo)"));
            }

            return sb.ToString();
        }

        /// <summary>
        /// Nome do campo. O Id tem limite de tamanho e o Eclipse recusa
        /// repetido — e nenhum dos dois vale perder o campo que já foi criado.
        /// </summary>
        static void Nomear(Beam feixe, string id)
        {
            try
            {
                feixe.Id = id;
            }
            catch (Exception)
            {
                // O campo existe com o Id automático do Eclipse. Renomear é
                // cosmético; perder o campo por causa do nome, não.
            }
        }

        /// <summary>
        /// Pesos iguais. O que estes números decidem de fato é a QUANTIDADE de
        /// pontos de controle do arco; os valores em si o otimizador reescreve
        /// na primeira iteração.
        /// </summary>
        public static IEnumerable<double> PesosIguais(int quantos)
        {
            return Enumerable.Repeat(1.0 / quantos, quantos);
        }

        static void Relatar(Resultado r, ExternalPlanSetup plano, List<Beam> feixes,
                            StructureSet ss, Pedido p)
        {
            r.Relatorio.Add("Plano:      " + plano.Id + "   (curso " + p.Curso.Id + ")");
            r.Relatorio.Add("Alvo:       " + p.Alvo.Id + string.Format("   {0:0.0} cm3", p.Alvo.Volume));
            r.Relatorio.Add(string.Format("Prescrição: {0} x {1:0} cGy = {2:0} cGy",
                p.Fracoes, p.DosePorFracaoCGy, p.DoseTotalCGy));
            // A leitura ACEITA, não a digitada: se a energia foi digitada
            // "6X-FFF" e o Eclipse só aceitou "6X" + fluência "FFF", é a
            // segunda que está nos campos criados, e é ela que tem de aparecer
            // aqui para quem for conferir.
            r.Relatorio.Add("Máquina:    " + (r.Equipamento != null
                ? r.Equipamento.ToString()
                : p.Maquina + "   " + p.Energia + "   " + p.TaxaDose + " UM/min   " + p.TecnicaId));
            r.Relatorio.Add("");
            r.Relatorio.Add("Isocentro   (" + p.OrigemDoIsocentro + ")");
            r.Relatorio.Add(string.Format("   DICOM     {0:0.0}  {1:0.0}  {2:0.0} mm",
                p.Isocentro.x, p.Isocentro.y, p.Isocentro.z));

            // Coordenada do usuário só depois que o plano existe: o DicomToUser
            // exige um PlanSetup. É esta linha que o físico compara com o que
            // está na tela do Eclipse — a de DICOM não bate com nada do que ele
            // vê ali.
            try
            {
                VVector u = ss.Image.DicomToUser(p.Isocentro, plano);
                r.Relatorio.Add(string.Format("   usuário   {0:0.0}  {1:0.0}  {2:0.0} mm", u.x, u.y, u.z));
            }
            catch (Exception)
            {
                r.Relatorio.Add("   usuário   (não convertido)");
            }

            if (feixes.Count > 0)
            {
                r.Relatorio.Add("");
                r.Relatorio.Add("Campos:");
                foreach (Beam feixe in feixes)
                    r.Relatorio.Add("   " + DescreverFeixe(feixe));
            }
        }

        /// <summary>
        /// A abertura em cm é o que denuncia um ajuste de colimador que não
        /// aconteceu: 10 x 10 num alvo de 12 cm salta aos olhos na mensagem, e
        /// não saltaria no Eclipse até alguém abrir o BEV.
        /// </summary>
        static string DescreverFeixe(Beam feixe)
        {
            try
            {
                ControlPoint primeiro = feixe.ControlPoints.First();
                VRect<double> j = primeiro.JawPositions;

                string geometria = feixe.ControlPoints.Count() > 1
                    ? string.Format("G {0:0} a {1:0}", primeiro.GantryAngle,
                                    feixe.ControlPoints.Last().GantryAngle)
                    : string.Format("G {0:0}", primeiro.GantryAngle);

                return string.Format("{0,-8} {1,-14} Col {2:0}   {3:0.0} x {4:0.0} cm",
                    feixe.Id, geometria, primeiro.CollimatorAngle,
                    (j.X2 - j.X1) / 10.0, (j.Y2 - j.Y1) / 10.0);
            }
            catch (Exception)
            {
                return feixe.Id;
            }
        }
    }
}
