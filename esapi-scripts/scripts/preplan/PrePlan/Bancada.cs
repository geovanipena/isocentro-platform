using System;
using VMS.TPS.Common.Model.API;

namespace VMS.TPS
{
    /// <summary>
    /// O paciente, o structure set e o curso aberto — venham eles do Eclipse
    /// (plug-in) ou de uma sessão aberta por fora (o .exe).
    ///
    /// Existe para que a Montagem, a Sonda e a janela não saibam em qual dos
    /// dois estão rodando. A diferença que importa entre os hospedeiros é uma
    /// só, e é ela que esta classe esconde: <see cref="Salvar"/>.
    /// </summary>
    public class Bancada
    {
        public readonly Patient Paciente;
        public readonly StructureSet Conjunto;
        public readonly Course CursoAberto;

        /// <summary>Nula no plug-in. Só o standalone tem uma.</summary>
        readonly Application _aplicacao;

        public Bancada(ScriptContext contexto)
        {
            Paciente = contexto.Patient;
            Conjunto = contexto.StructureSet;
            CursoAberto = contexto.Course;
            _aplicacao = null;
        }

        public Bancada(Application aplicacao, Patient paciente, StructureSet conjunto)
        {
            _aplicacao = aplicacao;
            Paciente = paciente;
            Conjunto = conjunto;
            CursoAberto = null;      // o standalone não tem curso "aberto"
        }

        public bool NoEclipse
        {
            get { return _aplicacao == null; }
        }

        /// <summary>
        /// **A armadilha do standalone.** Dentro do Eclipse, quem grava é o
        /// Eclipse — e chamar SaveModifications de um plug-in é recusado. Fora
        /// dele, NADA vai para o banco sem esta chamada: o script roda inteiro,
        /// o relatório sai bonito, a mensagem diz que criou o plano, e o banco
        /// não mudou. É a pior forma de falhar que existe aqui, porque ela
        /// parece sucesso.
        ///
        /// Por isso a gravação é uma linha só, num lugar só, e a falha dela é
        /// relatada como falha — nunca engolida.
        /// </summary>
        public void Salvar()
        {
            if (_aplicacao != null)
                _aplicacao.SaveModifications();
        }

        public string ComoSalva
        {
            get
            {
                return _aplicacao == null
                    ? "gravação: pelo Eclipse, ao fechar o paciente"
                    : "gravação: SaveModifications() — já feita";
            }
        }
    }
}
