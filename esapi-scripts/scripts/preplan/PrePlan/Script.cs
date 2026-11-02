using VMS.TPS.Common.Model.API;

// Sem este atributo o script nasce read-only: compila igual, e falha na
// PRIMEIRA escrita, em tempo de execução, com o paciente aberto na tela.
// Vale para os dois hospedeiros — o plug-in e o .exe.
[assembly: ESAPIScript(IsWriteable = true)]

namespace VMS.TPS
{
    /// <summary>
    /// A porta de entrada do PLUG-IN. O caminho de verdade está no
    /// <see cref="Fluxo"/>, que o .exe também usa — ver Programa.cs.
    /// </summary>
    public class Script
    {
        public const string NOME = "PrePlan";

        public Script()
        {
        }

        public void Execute(ScriptContext contexto)
        {
            if (contexto.Patient == null || contexto.StructureSet == null)
            {
                Fluxo.Avisar("Abra um paciente com imagem e structure set antes de rodar o script.");
                return;
            }

            Fluxo.Rodar(new Bancada(contexto));
        }
    }
}
