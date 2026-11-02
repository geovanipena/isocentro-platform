using System;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

namespace VMS.TPS
{
    public enum Tecnica
    {
        Vmat,
        CamposFixos
    }

    /// <summary>
    /// Tudo o que a janela decidiu, num objeto só.
    ///
    /// A janela mostra os ângulos que vão ser criados e a Montagem cria os
    /// ângulos que a janela mostrou — os dois chamam o MESMO
    /// <see cref="AngulosDeGantry"/>. Duas implementações da mesma conta é
    /// como a tela passa a prometer uma coisa e o plano a sair outra, sem
    /// que nada dê erro.
    /// </summary>
    public class Pedido
    {
        // ---- onde ---------------------------------------------------------
        public Course Curso;
        public string IdPlano;
        public Structure Alvo;

        // ---- prescrição ---------------------------------------------------
        public int Fracoes;
        public double DosePorFracaoCGy;

        // ---- técnica ------------------------------------------------------
        public Tecnica Tecnica;
        public int NumeroDeCampos;          // só para CamposFixos

        // ---- equipamento --------------------------------------------------
        // As quatro primeiras são strings CRUAS que precisam bater exatamente
        // com a configuração desta máquina no serviço. Não há catálogo de
        // máquinas na ESAPI 15.6 para conferir antes — ver Maquinas.cs.
        public string Maquina;
        public string Energia;
        public int TaxaDose;
        public string TecnicaId;            // "ARC" nos arcos, "STATIC" nos fixos

        /// <summary>
        /// A técnica COLHIDA do plano vizinho ("SRS ARC", por exemplo), quando
        /// diferente da documentada. Fica como SEGUNDA tentativa, não como
        /// primeira: a doc oficial do ExternalBeamMachineParameters diz que o
        /// techniqueId é "typically STATIC or ARC", e o Technique.Id de um
        /// feixe é o nome da técnica DO PLANO — nome de exibição, como o
        /// EnergyModeDisplayName. Preferir o colhido custou uma ida ao Eclipse
        /// em 03/09/2026.
        /// </summary>
        public string TecnicaAlternativa;

        public string ModoFluencia;         // vazio = com filtro; "FFF" ou "SRS"

        // ---- geometria ----------------------------------------------------
        public VVector Isocentro;           // SEMPRE em coordenada DICOM, em mm
        public string OrigemDoIsocentro;    // texto para o relatório
        public double ColimadorArco1;
        public double ColimadorArco2;
        public double ColimadorCamposFixos;
        public double MargemColimadorMm;
        public bool OtimizarRotacaoDoColimador;

        // ---- otimização ---------------------------------------------------
        public bool AdicionarNto;
        public double PrioridadeNto;

        public double DoseTotalCGy
        {
            get { return DosePorFracaoCGy * Fracoes; }
        }

        /// <summary>
        /// Ângulos dos campos fixos, igualmente espaçados a partir de 180°.
        ///
        /// Começa em 180 (posterior, no paciente supino) porque é o arranjo
        /// simétrico que o planejador reconhece de imediato — 7 campos dão
        /// 180, 231, 283, 334, 26, 77, 129. Não é uma escolha clínica: é um
        /// ponto de partida visível na janela ANTES de criar, para quem for
        /// mudar já saber o que vai mudar.
        /// </summary>
        public double[] AngulosDeGantry()
        {
            var angulos = new double[NumeroDeCampos];
            for (int i = 0; i < NumeroDeCampos; i++)
                angulos[i] = Math.Round((180.0 + i * 360.0 / NumeroDeCampos) % 360.0, 0);
            return angulos;
        }
    }
}
