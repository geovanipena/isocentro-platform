////////////////////////////////////////////////////////////////////////////////
//  EstruturasOpt_Prostata.cs                Clinica-Rede · Física Médica
//------------------------------------------------------------------------------
//  Caso: Próstata (boost PTV_60). Cria AUTOMATICAMENTE as estruturas de
//  otimização:
//    - PTV_44_opt : PTV_44 menos PTV_60 (com recuo opcional sobre o PTV_60)
//    - anel_1-20  : (soma dos PTVs + 20mm) menos (soma dos PTVs + 1mm)
//    - anel_20-40 : (soma dos PTVs + 40mm) menos (soma dos PTVs + 20mm)
//
//  "soma dos PTVs" = união booleana de PTV_60 e PTV_44.
//  Os anéis são opcionalmente recortados (And) pelo External/Body.
//------------------------------------------------------------------------------
//  Tipo: DLL binária GRAVÁVEL — compilada via MSBuild (ver
//  EstruturasOpt_Prostata.csproj nesta mesma pasta), não roda como
//  single-file (Eclipse 15.6 não suporta single-file gravável; gravável só a
//  partir da v16.1).
//
//  CONVENÇÕES
//    · namespace VMS.TPS · public class Script (deve ser PUBLIC: sem o
//      modificador, o Eclipse falha com "entry type not found" ao carregar a
//      DLL por reflexão — single-file tolera internal, DLL binária não)
//    · [assembly: ESAPIScript(IsWriteable = true)] sempre logo após os usings
//    · static readonly (não const): no compilador do plug-in, ramos não
//      tomados por uma constante viram "código inalcançável" (CS0162/CS0429),
//      tratado como erro
//
//  VALIDAR EXAUSTIVAMENTE em ambiente NÃO-CLÍNICO antes de uso real.
////////////////////////////////////////////////////////////////////////////////

using System;
using System.Linq;
using System.Text;
using System.Windows;
using System.Collections.Generic;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

[assembly: ESAPIScript(IsWriteable = true)]

namespace VMS.TPS
{
    public class Script
    {
        // ===================== CONFIGURAÇÃO DA CLÍNICA =====================
        // IDs principais das fontes (busca por Id, case-insensitive). Os aliases
        // cobrem variações comuns de nomenclatura.
        private static readonly string ID_PTV_ALTO  = "PTV_60";  // PTV 60 Gy (boost)
        private static readonly string ID_PTV_BAIXO = "PTV_44";  // PTV 44 Gy (drenagem)

        private static readonly string[] ALIAS_PTV_ALTO  = { "PTV_60", "PTV60", "PTV 60", "PTV_6000", "PTV6000" };
        private static readonly string[] ALIAS_PTV_BAIXO = { "PTV_44", "PTV44", "PTV 44", "PTV_4400", "PTV4400" };

        // Nomes das estruturas geradas (limite de 16 caracteres no Eclipse).
        private static readonly string ID_PTV_OPT = "PTV_44_opt";
        private static readonly string ID_ANEL_1  = "anel_1-20";
        private static readonly string ID_ANEL_2  = "anel_20-40";

        // Tipo DICOM das estruturas geradas.
        private static readonly string TIPO_PTV_OPT = "PTV";
        private static readonly string TIPO_ANEL    = "CONTROL";

        // PTV_44_opt = PTV_baixo menos (PTV_alto expandido OPT_SUB_MARGIN mm).
        // 5.0 = recuo de 5mm em torno do PTV_60 (PTV_44 - (PTV_60 + 5mm)).
        private static readonly double OPT_SUB_MARGIN = 5.0;

        // Margens dos anéis (mm): anel = soma.Margin(externo) - soma.Margin(interno).
        private static readonly double ANEL1_INTERNO = 1.0;
        private static readonly double ANEL1_EXTERNO = 20.0;
        private static readonly double ANEL2_INTERNO = 20.0;
        private static readonly double ANEL2_EXTERNO = 40.0;

        // Recorta os anéis pelo contorno externo do paciente (evita "vazar" do corpo).
        private static readonly bool CROP_TO_BODY = true;
        private static readonly string[] ALIAS_BODY = { "BODY" };

        // Limite de margem da ESAPI (mm). Valores fora disso lançam exceção.
        private static readonly double MAX_MARGIN = 50.0;
        // ===================================================================

        public void Execute(ScriptContext context, Window window)
        {
            var log = new StringBuilder();
            try
            {
                // ---------- 1. Validação de contexto ----------
                if (context.Patient == null)
                    throw new ApplicationException("Carregue um paciente.");

                StructureSet ss = (context.PlanSetup != null && context.PlanSetup.StructureSet != null)
                    ? context.PlanSetup.StructureSet
                    : context.StructureSet;
                if (ss == null)
                    throw new ApplicationException("Carregue um plano ou um conjunto de estruturas.");

                // ---------- 2. Localizar as fontes ----------
                Structure ptvAlto  = FindStructure(ss, ID_PTV_ALTO,  ALIAS_PTV_ALTO);
                Structure ptvBaixo = FindStructure(ss, ID_PTV_BAIXO, ALIAS_PTV_BAIXO);

                if (ptvAlto == null)
                    throw new ApplicationException("PTV de alta dose (PTV_60) não encontrado ou vazio.");
                if (ptvBaixo == null)
                    throw new ApplicationException("PTV de baixa dose (PTV_44) não encontrado ou vazio.");

                log.AppendLine("Fontes:");
                log.AppendLine("  Alto  (60Gy): '" + ptvAlto.Id + "'");
                log.AppendLine("  Baixo (44Gy): '" + ptvBaixo.Id + "'");
                log.AppendLine();

                ValidarMargem(ANEL1_INTERNO); ValidarMargem(ANEL1_EXTERNO);
                ValidarMargem(ANEL2_INTERNO); ValidarMargem(ANEL2_EXTERNO);
                ValidarMargem(OPT_SUB_MARGIN);

                // ---------- 3. Habilitar escrita ----------
                context.Patient.BeginModifications();

                // ---------- 4. PTV_44_opt = PTV_44 - (PTV_60 + OPT_SUB_MARGIN) ----------
                Structure ptvOpt = GetOrCreateStructure(ss, ID_PTV_OPT, TIPO_PTV_OPT, log);
                SegmentVolume subtraendo = (OPT_SUB_MARGIN > 0.0)
                    ? ptvAlto.SegmentVolume.Margin(OPT_SUB_MARGIN)
                    : ptvAlto.SegmentVolume;
                ptvOpt.SegmentVolume = ptvBaixo.SegmentVolume.Sub(subtraendo);
                ReportarEstrutura(ptvOpt, log);

                // ---------- 5. Soma (união) dos PTVs ----------
                SegmentVolume soma = ptvAlto.SegmentVolume.Or(ptvBaixo.SegmentVolume);

                // contorno externo (para recorte opcional dos anéis)
                Structure body = CROP_TO_BODY ? FindStructure(ss, null, ALIAS_BODY) : null;
                if (CROP_TO_BODY && body == null)
                    log.AppendLine("Aviso: External/Body não encontrado - anéis NÃO serão recortados pelo corpo.");

                // ---------- 6. anel_1-20 ----------
                Structure anel1 = GetOrCreateStructure(ss, ID_ANEL_1, TIPO_ANEL, log);
                anel1.SegmentVolume = soma.Margin(ANEL1_EXTERNO).Sub(soma.Margin(ANEL1_INTERNO));
                if (body != null) anel1.SegmentVolume = anel1.SegmentVolume.And(body.SegmentVolume);
                ReportarEstrutura(anel1, log);

                // ---------- 7. anel_20-40 ----------
                Structure anel2 = GetOrCreateStructure(ss, ID_ANEL_2, TIPO_ANEL, log);
                anel2.SegmentVolume = soma.Margin(ANEL2_EXTERNO).Sub(soma.Margin(ANEL2_INTERNO));
                if (body != null) anel2.SegmentVolume = anel2.SegmentVolume.And(body.SegmentVolume);
                ReportarEstrutura(anel2, log);

                // ---------- 8. Conclusão ----------
                log.AppendLine();
                log.AppendLine("Concluído. Revise as estruturas no Eclipse e salve.");
                MessageBox.Show(log.ToString(), "Estruturas de otimização - concluído");
            }
            catch (Exception ex)
            {
                log.AppendLine();
                log.AppendLine("ERRO: " + ex.Message);
                MessageBox.Show(log.ToString(), "Estruturas de otimização - exceção");
            }
        }

        // ------------------------------------------------------------------
        // Busca por Id (e aliases), retornando a primeira estrutura não vazia.
        // primaryId pode ser null (busca apenas pelos aliases).
        // ------------------------------------------------------------------
        private Structure FindStructure(StructureSet ss, string primaryId, string[] aliases)
        {
            var ids = new List<string>();
            if (!string.IsNullOrWhiteSpace(primaryId)) ids.Add(primaryId);
            if (aliases != null) ids.AddRange(aliases);

            foreach (var id in ids.Where(x => !string.IsNullOrWhiteSpace(x)).Select(x => x.Trim()))
            {
                var s = ss.Structures.FirstOrDefault(x =>
                    x.Id.Equals(id, StringComparison.OrdinalIgnoreCase));
                if (s != null && !s.IsEmpty) return s;
            }
            return null;
        }

        // ------------------------------------------------------------------
        // Reaproveita a estrutura se já existir (será sobrescrita); senão cria.
        // ------------------------------------------------------------------
        private Structure GetOrCreateStructure(StructureSet ss, string id, string dicomType, StringBuilder log)
        {
            var existing = ss.Structures.FirstOrDefault(s =>
                s.Id.Equals(id, StringComparison.OrdinalIgnoreCase));
            if (existing != null)
            {
                log.AppendLine("Estrutura '" + id + "' já existe - será sobrescrita.");
                return existing;
            }
            if (!ss.CanAddStructure(dicomType, id))
                throw new ApplicationException(
                    "Não foi possível criar a estrutura '" + id + "' (tipo " + dicomType + ").");
            Structure ns = ss.AddStructure(dicomType, id);
            log.AppendLine("Estrutura criada: '" + id + "' (" + dicomType + ").");
            return ns;
        }

        private void ReportarEstrutura(Structure s, StringBuilder log)
        {
            if (s.IsEmpty)
                log.AppendLine("  -> ATENÇÃO: '" + s.Id + "' ficou VAZIA.");
            else
                log.AppendLine("  -> '" + s.Id + "': " + string.Format("{0:0.0} cc", s.Volume));
        }

        private void ValidarMargem(double mm)
        {
            if (mm < 0.0 || mm > MAX_MARGIN)
                throw new ApplicationException(
                    "Margem inválida: " + mm + " mm (permitido 0 a " + MAX_MARGIN + " mm).");
        }
    }
}
