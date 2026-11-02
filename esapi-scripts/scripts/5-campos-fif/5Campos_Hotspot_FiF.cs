using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Reflection;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Media3D;
using VMS.TPS.Common.Model.API;
using VMS.TPS.Common.Model.Types;

[assembly: ESAPIScript(IsWriteable = true)]

// Eclipse Script Administration registers scripts by name + version.
// The wildcard gives every build a new version, so a rebuilt DLL can be registered again.
[assembly: AssemblyVersion("24.4.*")]

namespace VMS.TPS
{
    // V24.4 - Nested field-in-field (V24.3 behaviour plus % / cGy dose handling) with a variable number of subfields per field.
    //         Machines: 600CD, 6EX, TrueBeamSN1001.
    //
    // For each field that should receive field-in-field, the planner creates manual copies in Eclipse
    // named <original>.0, <original>.1, <original>.2 ... (copying in Eclipse keeps the MLC).
    // Fields without copies are left unchanged (their weight is kept and their dose is included).
    //
    // With n subfields, subfield .i blocks the region above 107% + (Dmax - 107%) * i / n,
    // so .0 always blocks >= 107% and the last one blocks the hottest core.
    //
    //   Calc 1  open reference: subfields get the original aperture -> hotspot levels and structures.
    //   Calc 2  all subfields blocked -> per-beam doses (Beam.Dose) give the dose per unit weight
    //           of every original and subfield. Dose is linear in the weights, so any split is
    //           simulated and renormalized to PTV D95 = 100%. Weights are searched independently
    //           per field (total weight per field kept, minimum MU per beam respected).
    //           If the beam doses do not add up to the plan dose, extra calculations give one
    //           common split for all fields instead.
    //   Calc 3  final dose, renormalization to D95 = 100%, MU check (and fix if needed).
    //
    // Nothing is saved. The planner reviews BEV, isodoses and DVH and decides whether to save.
    public class Script
    {
        private const string ScriptTitle = "5 Campos Hotspot MLC V24.4 - FiF";

        // Treatment units this script was prepared for (Eclipse machine IDs; spaces, "-" and "_" ignored).
        private static readonly string[] SupportedMachines =
        {
            "600CD", "6EX", "TrueBeamSN1001"
        };

        // Subfields are <original>.0 ... <original>.(MaxSubfields - 1).
        private const int MaxSubfields = 5;

        // Hotspot level relative to the total prescribed dose (.0 block).
        private const double HotspotFraction = 1.07;

        // Coverage objective used for renormalization: D95 of the target = 100% of prescription.
        private const double CoverageVolumePercent = 95.0;

        // Weight of each subfield during the probe calculations (fraction of the total field weight).
        private const double ProbeFraction = 0.10;

        // Weight search (fractions of the total field weight).
        private const double SearchStep = 0.025;
        private const double CoarseStep = 0.05;
        private const double SearchMax = 0.30;
        private const double SearchMaxTotal = 0.50;
        private const int SearchMaxPasses = 100;

        // Beam doses must reproduce the plan dose within this relative RMS error (voxels >= 50% Rx).
        private const double BeamDoseMaxRelativeError = 0.01;

        // MU linearity: every beam (original and subfields) must keep at least this many MU.
        private const double MinBeamMu = 5.0;

        // The weight search aims slightly above the minimum; the final MU are then checked and fixed.
        private const double MuPlanningMargin = 1.05;
        private const int MaxMuRepairs = 2;

        // Only voxels above this fraction of prescription (open reference) can hold Dmax / V107.
        private const double CandidateDoseFraction = 0.80;

        // Temporary hotspot structures; every structure with this prefix is removed when the script ends.
        private const string ControlStructurePrefix = "zFIF_";
        private const string HotStructureId = ControlStructurePrefix + "HOT107";

        private const double GantryToleranceDeg = 0.5;
        private const double GeometryToleranceMm = 0.1;
        private const double AngleToleranceDeg = 0.1;
        private const double WeightRelativeTolerance = 0.01;

        // Leaf pairs with an opening at or below this value are treated as closed.
        private const double ClosedGapMm = 1.0;

        // Fractions of the requested leaf travel tried when a row is rejected (1.0 already failed).
        private static readonly double[] PartialTravelFractions = { 0.75, 0.5, 0.25 };

        // Opening left in a row when a fully closed row is rejected.
        private const float FallbackGapMm = 0.5f;

        public Script()
        {
        }

        private sealed class FieldSet
        {
            public Beam Original;
            public List<Beam> Subs = new List<Beam>();
            public double TotalWeight;
            public bool FreshCopies;
            public double MuPerWeightOriginal = double.NaN;
            public double[] MuPerWeightSubs;
            public float[][,] BlockedLeaves;

            public int Count
            {
                get { return Subs.Count; }
            }
        }

        private sealed class BeamState
        {
            public Beam Beam;
            public float[,] Leaves;
            public VRect<double> Jaws;
            public double Weight;
        }

        private sealed class LeafApplyResult
        {
            public float[,] Leaves;
            public bool FullShapeAccepted;
            public int RowsRequested;
            public int RowsFull;
            public int RowsPartial;
            public int RowsSkipped;
        }

        private sealed class PlanMetrics
        {
            public double DmaxPercent = double.NaN;
            public string DmaxText = "n/a";
            public double BodyHotCc = double.NaN;
            public double TargetD95Percent = double.NaN;
            public double TargetV95Percent = double.NaN;
            public double TargetV100Percent = double.NaN;
        }

        private sealed class WeightCandidate
        {
            public double[] X;
            public double MeanSubfieldFraction;
            public double D95Raw;
            public double DmaxRenormPercent;
            public double HotCcRenorm;
            public double MinMu = double.NaN;
            public double MuDeficit;
        }

        // Dose on the evaluation voxels = Base + sum_v X[v] * Gradients[v].
        // VarIndex[k][i] is the variable that holds the fraction of subfield i of field k.
        private sealed class LinearModel
        {
            public string Description;
            public double[] Base;
            public List<float[]> Gradients = new List<float[]>();
            public int[][] VarIndex;
            public int[] TargetPos;
            public int[] CandidatePos;
        }

        public void Execute(ScriptContext context, Window window)
        {
            StringBuilder report = new StringBuilder();
            SetHostWindowStatus(window);

            try
            {
                // ---------------------------------------------------------------
                // Read-only validation
                // ---------------------------------------------------------------
                if (context == null || context.Patient == null)
                {
                    Warn("No patient is currently available.");
                    return;
                }

                ExternalPlanSetup plan = context.ExternalPlanSetup;

                if (plan == null)
                {
                    Warn("No ExternalPlanSetup is active.");
                    return;
                }

                if (plan.ApprovalStatus != PlanSetupApprovalStatus.UnApproved)
                {
                    Warn("The active plan is '" + plan.ApprovalStatus +
                        "'. Run this script only on an unapproved plan (preferably a copy of the clinical plan).");
                    return;
                }

                if (!context.Patient.CanModifyData())
                {
                    Warn("The current patient cannot be modified. Run this as a write-enabled ESAPI script.");
                    return;
                }

                StructureSet structureSet = plan.StructureSet;

                if (structureSet == null)
                {
                    Warn("The plan has no structure set.");
                    return;
                }

                DoseValue prescription = plan.TotalDose;

                if (!prescription.IsAbsoluteDoseValue || prescription.Dose <= 0.0)
                {
                    Warn("The plan total prescribed dose is not defined as an absolute dose.");
                    return;
                }

                Structure target = FindStructure(structureSet, plan.TargetVolumeID);
                Structure body = FindBody(structureSet);

                if (target == null || target.IsEmpty)
                {
                    Warn("The plan target volume ('" + plan.TargetVolumeID + "') was not found or is empty. " +
                        "The script needs the target to renormalize coverage.");
                    return;
                }

                DoseValue hotLevel = new DoseValue(prescription.Dose * HotspotFraction, prescription.Unit);

                report.AppendLine(ScriptTitle.ToUpperInvariant());
                report.AppendLine("==================================================");
                report.AppendLine();
                report.AppendLine("Plan: " + plan.Id);
                report.AppendLine("Total prescribed dose: " + FormatDose(prescription));
                report.AppendLine("Hotspot level (" + FormatNumber(HotspotFraction * 100.0, "F0") + "%): " + FormatDose(hotLevel));
                report.AppendLine("Target volume: " + target.Id + " (" + FormatNumber(target.Volume, "F1") + " cm3)");
                report.AppendLine("Body: " + (body == null ? "<not found>" : body.Id));
                report.AppendLine("Coverage objective: D" + FormatNumber(CoverageVolumePercent, "F0") + " = 100% Rx (renormalized)");
                report.AppendLine("Normalization: " + plan.PlanNormalizationMethod +
                    " (value " + FormatNumber(plan.PlanNormalizationValue, "F2") + ")");
                report.AppendLine("Minimum MU per beam: " + FormatNumber(MinBeamMu, "F0"));
                report.AppendLine();

                List<string> errors = new List<string>();
                List<Beam> fixedBeams = new List<Beam>();
                List<FieldSet> fields = ResolveFieldSets(plan, report, errors, fixedBeams);

                if (errors.Count > 0 || fields.Count == 0)
                {
                    report.AppendLine("VALIDATION FAILED - NOTHING WAS CHANGED");
                    report.AppendLine("---------------------------------------");

                    foreach (string error in errors)
                        report.AppendLine("  - " + error);

                    if (fields.Count == 0)
                        report.AppendLine("  - No field with subfield copies (<original>.0, .1, ...) was found.");

                    report.AppendLine();
                    report.AppendLine("How to prepare the plan:");
                    report.AppendLine("  In Eclipse, copy each field that needs field-in-field and rename the copies");
                    report.AppendLine("  <original ID>.0, <original ID>.1, ... (e.g. 2_G270.0, 2_G270.1, 2_G270.2).");
                    report.AppendLine("  Up to " + MaxSubfields + " subfields per field, numbered without gaps.");
                    report.AppendLine("  Supported machines: " + String.Join(", ", SupportedMachines) + ".");
                    report.AppendLine("  Do not change geometry, energy or MLC of the copies.");

                    ShowReport(report.ToString(), ScriptTitle + " - NOT READY", window, false);
                    return;
                }

                // ---------------------------------------------------------------
                // Confirmation
                // ---------------------------------------------------------------
                report.AppendLine("FIELD WEIGHTS");
                report.AppendLine("-------------");

                foreach (FieldSet field in fields)
                {
                    report.AppendLine(field.Original.Id + ": " + field.Count + " subfield(s), total field weight " +
                        FormatNumber(field.TotalWeight, "F4") +
                        (field.FreshCopies ? " (fresh copies)" : " (existing split - original apertures restored first)"));
                }

                foreach (Beam beam in fixedBeams)
                    report.AppendLine(beam.Id + ": no subfields - weight " + FormatNumber(beam.WeightFactor, "F4") + " kept");

                report.AppendLine();
                report.AppendLine("WORKFLOW (3 dose calculations + MU fix if needed)");
                report.AppendLine("-------------------------------------------------");
                report.AppendLine("1. Open reference: subfields get the original aperture -> hotspot structures.");
                report.AppendLine("2. With n subfields, .i blocks the region above 107% + (Dmax - 107%) * i / n -> calculate.");
                report.AppendLine("   Weights are simulated from the per-beam doses and searched per field");
                report.AppendLine("   (each subfield " + FormatPercent(SearchStep) + " - " + FormatPercent(SearchMax) +
                    ", all subfields of a field <= " + FormatPercent(SearchMaxTotal) + ", >= " +
                    FormatNumber(MinBeamMu, "F0") + " MU per beam).");
                report.AppendLine("3. Final calculation, renormalization to D95 = 100%, MU check.");
                report.AppendLine();
                report.AppendLine("Temporary structures '" + ControlStructurePrefix + "*' are created and removed at the end.");
                report.AppendLine("The plan normalization value WILL change. NOTHING is saved automatically.");
                report.AppendLine();

                if (!ShowReport(report.ToString() + "Proceed?", ScriptTitle + " - CONFIRM", window, true))
                    return;

                // ---------------------------------------------------------------
                // Write stage
                // ---------------------------------------------------------------
                context.Patient.BeginModifications();

                try
                {
                    plan.DoseValuePresentation = DoseValuePresentation.Absolute;
                }
                catch (Exception presentationException)
                {
                    // The grid may stay in %; every dose read is converted with the prescription.
                    report.AppendLine("Note: dose presentation stays relative (" + presentationException.Message + ").");
                    report.AppendLine();
                }

                PlanMetrics originalMetrics = MeasurePlan(plan, body, target, prescription, hotLevel);
                double originalNormalization = plan.PlanNormalizationValue;

                List<BeamState> snapshots = new List<BeamState>();

                foreach (FieldSet field in fields)
                {
                    snapshots.Add(CaptureState(field.Original));

                    foreach (Beam sub in field.Subs)
                        snapshots.Add(CaptureState(sub));
                }

                try
                {
                    RunFieldInField(plan, fields, fixedBeams, snapshots, target, body, prescription, hotLevel,
                        structureSet, originalMetrics, report);
                }
                catch (Exception writeException)
                {
                    report.AppendLine();
                    report.AppendLine("WRITE STAGE FAILED");
                    report.AppendLine(writeException.ToString());
                    report.AppendLine();
                    report.AppendLine("Restoring original leaves, jaws, weights and normalization...");

                    bool restored = RestoreAll(snapshots, report);

                    try
                    {
                        plan.PlanNormalizationValue = originalNormalization;
                    }
                    catch (Exception normalizationException)
                    {
                        restored = false;
                        report.AppendLine("!!! Could not restore normalization: " + normalizationException.Message);
                    }

                    report.AppendLine(restored
                        ? "All beams restored. Dose is invalid: recalculate or close without saving."
                        : "!!! RESTORE INCOMPLETE - DO NOT SAVE THE PLAN. Close the patient without saving.");

                    RemoveControlStructures(structureSet, report);
                    ShowReport(report.ToString(), ScriptTitle + " - FAILED", window, false);
                    return;
                }

                RemoveControlStructures(structureSet, report);
                ShowReport(report.ToString(), ScriptTitle + " - RESULT", window, false);
            }
            catch (Exception ex)
            {
                ShowReport(
                    report.ToString() +
                    Environment.NewLine +
                    "The script stopped because an unexpected error occurred." +
                    Environment.NewLine +
                    "If any beam was changed, close the patient WITHOUT saving." +
                    Environment.NewLine +
                    Environment.NewLine +
                    ex.ToString(),
                    ScriptTitle + " - ERROR",
                    window,
                    false);
            }
        }

        // -------------------------------------------------------------------
        // Field-in-field workflow
        // -------------------------------------------------------------------

        private static void RunFieldInField(
            ExternalPlanSetup plan,
            List<FieldSet> fields,
            List<Beam> fixedBeams,
            List<BeamState> snapshots,
            Structure target,
            Structure body,
            DoseValue prescription,
            DoseValue hotLevel,
            StructureSet structureSet,
            PlanMetrics originalMetrics,
            StringBuilder report)
        {
            // Step 1 - open reference: subfields carry the original aperture.
            foreach (FieldSet field in fields)
            {
                BeamState original = FindState(snapshots, field.Original);
                double t = field.TotalWeight;

                ApplyBeam(field.Original, original.Leaves, original.Jaws, t * (1.0 - field.Count * ProbeFraction));

                foreach (Beam sub in field.Subs)
                    ApplyBeam(sub, original.Leaves, original.Jaws, t * ProbeFraction);
            }

            report.AppendLine("DOSE CALCULATIONS");
            report.AppendLine("-----------------");
            Calculate(plan, "1 open reference", report);

            float[] open = ReadDose(plan.Dose, prescription);
            double openDmaxPercent = MaxOf(open) / prescription.Dose * 100.0;

            if (openDmaxPercent < HotspotFraction * 100.0)
            {
                report.AppendLine();
                report.AppendLine("Open reference Dmax is " + FormatNumber(openDmaxPercent, "F1") +
                    "% (< " + FormatNumber(HotspotFraction * 100.0, "F0") + "%). No field-in-field needed.");
                report.AppendLine("Subfields carry the original aperture (plan dose equals the original shape).");
                return;
            }

            // Voxel masks need a valid dose grid: build them before any beam is modified (edits invalidate plan.Dose).
            int[] targetVoxels = BuildStructureMask(plan.Dose, target);

            if (targetVoxels.Length < 20)
                throw new InvalidOperationException("Too few dose voxels inside " + target.Id + " (" + targetVoxels.Length + ").");

            int[] candidateVoxels = BuildCandidateMask(open, prescription.Dose * CandidateDoseFraction);
            int[] evalVoxels = SortedUnion(targetVoxels, candidateVoxels);
            double voxelCc = plan.Dose.XRes * plan.Dose.YRes * plan.Dose.ZRes / 1000.0;

            // Hotspot structures per subfield level.
            report.AppendLine();
            report.AppendLine("HOTSPOT LEVELS (open reference Dmax " + FormatNumber(openDmaxPercent, "F1") + "%)");
            report.AppendLine("-----------------------------------------------");

            Dictionary<string, Structure> levelStructures = new Dictionary<string, Structure>();
            double openDmaxFraction = openDmaxPercent / 100.0;

            foreach (FieldSet field in fields)
            {
                int n = field.Count;
                Structure previous = null;

                for (int i = 0; i < n; i++)
                {
                    string id = i == 0 ? HotStructureId : "zFIF_L" + n + "_" + i;
                    Structure region;

                    if (!levelStructures.TryGetValue(id, out region))
                    {
                        double fraction = HotspotFraction + (openDmaxFraction - HotspotFraction) * i / n;
                        DoseValue level = LevelFor(plan.Dose, prescription.Dose * fraction, prescription);
                        region = PrepareDoseStructure(structureSet, id, plan.Dose, level);

                        report.AppendLine("  " + id.PadRight(14) + " >= " + (FormatNumber(fraction * 100.0, "F1") + "%").PadLeft(7) +
                            "  " + FormatNumber(region.IsEmpty ? 0.0 : region.Volume, "F1") + " cm3" +
                            (region.IsEmpty ? " (empty - previous level used)" : ""));

                        levelStructures[id] = region;
                    }

                    if (region.IsEmpty && previous != null)
                        region = previous;

                    levelStructures[field.Original.Id + "#" + i] = region;
                    previous = region;
                }
            }

            // Step 2 - every subfield blocks its level.
            report.AppendLine();
            report.AppendLine("SUBFIELD SHAPES");
            report.AppendLine("---------------");

            foreach (FieldSet field in fields)
            {
                BeamState original = FindState(snapshots, field.Original);
                double probeWeight = field.TotalWeight * ProbeFraction;
                field.BlockedLeaves = new float[field.Count][,];

                for (int i = 0; i < field.Count; i++)
                {
                    Beam sub = field.Subs[i];
                    Structure region = levelStructures[field.Original.Id + "#" + i];

                    float[,] requested = FitAndBlock(sub, region, original);
                    LeafApplyResult result = ApplyLeavesWithValidation(sub, original.Leaves, requested, original.Jaws, probeWeight);
                    field.BlockedLeaves[i] = result.Leaves;

                    report.AppendLine(DescribeLeafResult(sub.Id + " (" + region.Id + ")", result));
                }
            }

            Calculate(plan, "2 subfields blocked", report);
            CaptureMuPerWeight(fields);

            // Step 3 - linear dose model.
            report.AppendLine();
            report.AppendLine("DOSE MODEL");
            report.AppendLine("----------");

            LinearModel model = TryBuildPerBeamModel(plan, fields, fixedBeams, prescription, evalVoxels, report);

            if (model == null)
            {
                report.AppendLine("Falling back to one common split for all fields (extra calculations).");
                model = BuildCommonModel(plan, fields, snapshots, prescription, open, evalVoxels, report);
            }

            model.TargetPos = PositionsIn(evalVoxels, targetVoxels);
            model.CandidatePos = PositionsIn(evalVoxels, candidateVoxels);

            report.AppendLine("Model: " + model.Description + " | target voxels " + targetVoxels.Length +
                " | candidate voxels " + candidateVoxels.Length);

            // Step 4 - weight search.
            report.AppendLine();
            report.AppendLine("WEIGHT SEARCH (simulated, renormalized to D95 = 100%)");
            report.AppendLine("-----------------------------------------------------");

            WeightCandidate best = SearchWeights(model, fields, prescription.Dose, voxelCc, report);
            double[][] fractions = FieldFractions(model, fields, best.X);

            // Step 5 - final weights and dose.
            report.AppendLine();
            report.AppendLine("CHOSEN WEIGHTS (fraction of the total weight of each field)");
            report.AppendLine("------------------------------------------------------------");

            for (int k = 0; k < fields.Count; k++)
            {
                FieldSet field = fields[k];
                double t = field.TotalWeight;
                double originalFraction = 1.0 - Sum(fractions[k]);
                StringBuilder line = new StringBuilder();

                SetWeight(field.Original, t * originalFraction);
                line.Append(field.Original.Id.PadRight(12) + "orig " + FormatPercent(originalFraction).PadLeft(6));

                for (int i = 0; i < field.Count; i++)
                {
                    SetWeight(field.Subs[i], t * fractions[k][i]);
                    line.Append("  ." + i + " " + FormatPercent(fractions[k][i]).PadLeft(6));
                }

                report.AppendLine(line.ToString());
            }

            report.AppendLine();
            Calculate(plan, "3 final", report);

            report.AppendLine();
            report.AppendLine("RENORMALIZATION");
            report.AppendLine("---------------");
            Renormalize(plan, target, prescription, report);

            EnforceMinimumMu(plan, fields, target, prescription, report);

            PlanMetrics after = MeasurePlan(plan, body, target, prescription, hotLevel);

            report.AppendLine();
            report.AppendLine("ORIGINAL PLAN / FINAL PLAN");
            report.AppendLine("--------------------------");
            report.AppendLine(Row("Metric", "Original", "Final"));
            report.AppendLine(Row("Dmax", originalMetrics.DmaxText, after.DmaxText));
            report.AppendLine(Row("Dmax (% Rx)", FormatNumber(originalMetrics.DmaxPercent, "F1"), FormatNumber(after.DmaxPercent, "F1")));
            report.AppendLine(Row("Body V107% (cm3)", FormatNumber(originalMetrics.BodyHotCc, "F1"), FormatNumber(after.BodyHotCc, "F1")));
            report.AppendLine(Row("Target D95 (% Rx)", FormatNumber(originalMetrics.TargetD95Percent, "F1"), FormatNumber(after.TargetD95Percent, "F1")));
            report.AppendLine(Row("Target V95% (%)", FormatNumber(originalMetrics.TargetV95Percent, "F1"), FormatNumber(after.TargetV95Percent, "F1")));
            report.AppendLine(Row("Target V100% (%)", FormatNumber(originalMetrics.TargetV100Percent, "F1"), FormatNumber(after.TargetV100Percent, "F1")));
            report.AppendLine();
            report.AppendLine("Predicted renormalized Dmax: " + FormatNumber(best.DmaxRenormPercent, "F1") + "%");

            report.AppendLine();
            report.AppendLine("REVIEW BEFORE SAVING");
            report.AppendLine("--------------------");
            report.AppendLine("- Check each subfield aperture in BEV (hotspot levels are listed above).");
            report.AppendLine("- Check coverage, isodoses, DVH, OARs and MU.");
            report.AppendLine("- To discard everything, close the patient WITHOUT saving.");
        }

        private static void Calculate(ExternalPlanSetup plan, string label, StringBuilder report)
        {
            Stopwatch watch = Stopwatch.StartNew();
            CalculationResult result = plan.CalculateDose();
            watch.Stop();

            report.AppendLine("  Calc " + label + ": " +
                (result != null && result.Success ? "OK" : "FAILED") +
                " (" + FormatNumber(watch.Elapsed.TotalSeconds, "F0") + " s)");

            if (result == null || !result.Success || plan.Dose == null)
                throw new InvalidOperationException("Dose calculation '" + label + "' failed.");
        }

        private static void Renormalize(ExternalPlanSetup plan, Structure target, DoseValue prescription, StringBuilder report)
        {
            double oldValue = plan.PlanNormalizationValue;
            double d95 = TargetD95(plan, target, prescription);

            report.AppendLine("D95 before renormalization: " + FormatNumber(d95 / prescription.Dose * 100.0, "F2") + "% Rx");
            report.AppendLine("Normalization value before: " + FormatNumber(oldValue, "F2"));

            if (double.IsNaN(d95) || d95 <= 0.0)
                throw new InvalidOperationException("Could not read target D95 for renormalization.");

            // The direction of the normalization value is verified by measuring D95 after each attempt.
            double ratio = d95 / prescription.Dose;
            double[] attempts = { oldValue * ratio, oldValue / ratio };

            foreach (double value in attempts)
            {
                plan.PlanNormalizationValue = value;
                double check = TargetD95(plan, target, prescription) / prescription.Dose * 100.0;

                if (Math.Abs(check - 100.0) <= 0.5)
                {
                    report.AppendLine("Normalization value after: " + FormatNumber(value, "F2") +
                        " -> D95 = " + FormatNumber(check, "F2") + "% Rx");
                    return;
                }
            }

            plan.PlanNormalizationValue = oldValue;
            report.AppendLine("!!! Automatic renormalization did not reach D95 = 100%. Value restored to " +
                FormatNumber(oldValue, "F2") + ".");
            report.AppendLine("    Normalize manually in Eclipse (100% covering " +
                FormatNumber(CoverageVolumePercent, "F0") + "% of " + target.Id + ").");
        }

        private static double TargetD95(PlanSetup plan, Structure target, DoseValue prescription)
        {
            try
            {
                DoseValue absolute = plan.GetDoseAtVolume(
                    target, CoverageVolumePercent, VolumePresentation.Relative, DoseValuePresentation.Absolute);
                return ToAbsolute(absolute, prescription);
            }
            catch (Exception)
            {
                DoseValue relative = plan.GetDoseAtVolume(
                    target, CoverageVolumePercent, VolumePresentation.Relative, DoseValuePresentation.Relative);
                return ToAbsolute(relative, prescription);
            }
        }

        // -------------------------------------------------------------------
        // Dose models
        // -------------------------------------------------------------------

        // Per-beam doses of the current calculation: independent variables for every subfield of every field.
        private static LinearModel TryBuildPerBeamModel(
            ExternalPlanSetup plan,
            List<FieldSet> fields,
            List<Beam> fixedBeams,
            DoseValue prescription,
            int[] evalVoxels,
            StringBuilder report)
        {
            double rx = prescription.Dose;
            int n = evalVoxels.Length;
            float[] planDose;
            float[][] originalRaw = new float[fields.Count][];
            float[][][] subRaw = new float[fields.Count][][];
            List<float[]> fixedRaw = new List<float[]>();

            try
            {
                planDose = ReadDoseSubset(plan.Dose, plan.Dose, evalVoxels, null, prescription);

                for (int k = 0; k < fields.Count; k++)
                {
                    originalRaw[k] = ReadBeamDose(fields[k].Original, plan.Dose, evalVoxels, prescription);
                    subRaw[k] = new float[fields[k].Count][];

                    for (int i = 0; i < fields[k].Count; i++)
                        subRaw[k][i] = ReadBeamDose(fields[k].Subs[i], plan.Dose, evalVoxels, prescription);
                }

                foreach (Beam beam in fixedBeams)
                {
                    if (beam.WeightFactor > 0.0)
                        fixedRaw.Add(ReadBeamDose(beam, plan.Dose, evalVoxels, prescription));
                }
            }
            catch (Exception ex)
            {
                report.AppendLine("Per-beam dose not usable: " + ex.Message);
                return null;
            }

            // Calibrate: the beam doses must add up to the plan dose (one common scale factor).
            double[] sum = new double[n];
            List<float[]> all = new List<float[]>(fixedRaw);
            all.AddRange(originalRaw);

            foreach (float[][] subs in subRaw)
                all.AddRange(subs);

            foreach (float[] beam in all)
                for (int j = 0; j < n; j++)
                    sum[j] += beam[j];

            double sumPM = 0.0, sumMM = 0.0, sumPP = 0.0;

            for (int j = 0; j < n; j++)
            {
                if (planDose[j] < 0.5 * rx)
                    continue;

                sumPM += planDose[j] * sum[j];
                sumMM += sum[j] * sum[j];
                sumPP += (double)planDose[j] * planDose[j];
            }

            if (sumMM <= 0.0 || sumPP <= 0.0)
            {
                report.AppendLine("Per-beam dose check failed: no voxels >= 50% Rx.");
                return null;
            }

            double scale = sumPM / sumMM;
            double residual = 0.0;

            for (int j = 0; j < n; j++)
            {
                if (planDose[j] < 0.5 * rx)
                    continue;

                double d = planDose[j] - scale * sum[j];
                residual += d * d;
            }

            double relativeError = Math.Sqrt(residual / sumPP);

            report.AppendLine("Sum of beam doses vs plan dose: scale " + FormatNumber(scale, "G4") +
                ", RMS error " + FormatNumber(relativeError * 100.0, "F2") + "% (limit " +
                FormatNumber(BeamDoseMaxRelativeError * 100.0, "F1") + "%)");

            if (!(scale > 0.0) || relativeError > BeamDoseMaxRelativeError)
            {
                report.AppendLine("Beam doses do not reproduce the plan dose.");
                return null;
            }

            // Dose = fixed + sum_k t_k * [O_k + sum_i f_ki * (S_ki - O_k)], O/S per unit weight.
            LinearModel model = new LinearModel
            {
                Description = "per-beam doses, independent weights per field",
                Base = new double[n],
                VarIndex = new int[fields.Count][]
            };

            foreach (float[] beam in fixedRaw)
                for (int j = 0; j < n; j++)
                    model.Base[j] += scale * beam[j];

            for (int k = 0; k < fields.Count; k++)
            {
                FieldSet field = fields[k];
                double t = field.TotalWeight;
                double so = scale / field.Original.WeightFactor;
                double[] o = new double[n];

                for (int j = 0; j < n; j++)
                {
                    o[j] = originalRaw[k][j] * so;
                    model.Base[j] += t * o[j];
                }

                model.VarIndex[k] = new int[field.Count];

                for (int i = 0; i < field.Count; i++)
                {
                    double ss = scale / field.Subs[i].WeightFactor;
                    float[] g = new float[n];

                    for (int j = 0; j < n; j++)
                        g[j] = (float)(t * (subRaw[k][i][j] * ss - o[j]));

                    model.VarIndex[k][i] = model.Gradients.Count;
                    model.Gradients.Add(g);
                }
            }

            return model;
        }

        // Fallback: cumulative calculations give the dose change of subfield index i (all fields together).
        private static LinearModel BuildCommonModel(
            ExternalPlanSetup plan,
            List<FieldSet> fields,
            List<BeamState> snapshots,
            DoseValue prescription,
            float[] open,
            int[] evalVoxels,
            StringBuilder report)
        {
            int levels = 0;

            foreach (FieldSet field in fields)
                levels = Math.Max(levels, field.Count);

            // cumulative[i] = dose with subfield indices <= i blocked; the current dose has all blocked.
            float[][] cumulative = new float[levels][];
            cumulative[levels - 1] = Subset(ReadDose(plan.Dose, prescription), evalVoxels);

            for (int i = levels - 1; i >= 1; i--)
            {
                foreach (FieldSet field in fields)
                {
                    if (field.Count <= i)
                        continue;

                    BeamState original = FindState(snapshots, field.Original);
                    ApplyBeam(field.Subs[i], original.Leaves, original.Jaws, field.TotalWeight * ProbeFraction);
                }

                Calculate(plan, "extra: subfields ." + i + "+ open", report);
                cumulative[i - 1] = Subset(ReadDose(plan.Dose, prescription), evalVoxels);
            }

            // Blocked shapes back in place for the final calculation.
            foreach (FieldSet field in fields)
            {
                BeamState original = FindState(snapshots, field.Original);

                for (int i = 0; i < field.Count; i++)
                    ApplyBeam(field.Subs[i], field.BlockedLeaves[i], original.Jaws, field.TotalWeight * ProbeFraction);
            }

            int n = evalVoxels.Length;
            float[] openSubset = Subset(open, evalVoxels);

            LinearModel model = new LinearModel
            {
                Description = "cumulative calculations, one split for all fields",
                Base = new double[n],
                VarIndex = new int[fields.Count][]
            };

            for (int j = 0; j < n; j++)
                model.Base[j] = openSubset[j];

            for (int i = 0; i < levels; i++)
            {
                float[] previous = i == 0 ? openSubset : cumulative[i - 1];
                float[] g = new float[n];

                for (int j = 0; j < n; j++)
                    g[j] = (float)((cumulative[i][j] - previous[j]) / ProbeFraction);

                model.Gradients.Add(g);
            }

            for (int k = 0; k < fields.Count; k++)
            {
                model.VarIndex[k] = new int[fields[k].Count];

                for (int i = 0; i < fields[k].Count; i++)
                    model.VarIndex[k][i] = i;
            }

            return model;
        }

        // -------------------------------------------------------------------
        // Weight search
        // -------------------------------------------------------------------

        private static WeightCandidate SearchWeights(
            LinearModel model,
            List<FieldSet> fields,
            double rx,
            double voxelCc,
            StringBuilder report)
        {
            int n = model.Base.Length;
            int vars = model.Gradients.Count;
            double[] targetBuffer = new double[model.TargetPos.Length];
            int d95Index = (int)Math.Floor((100.0 - CoverageVolumePercent) / 100.0 * (model.TargetPos.Length - 1));
            double hotThreshold = rx * HotspotFraction;

            double totalWeight = 0.0;
            int totalSubs = 0;

            foreach (FieldSet field in fields)
            {
                totalWeight += field.TotalWeight;
                totalSubs += field.Count;
            }

            WeightCandidate Score(double[] dose, double[] x)
            {
                for (int j = 0; j < model.TargetPos.Length; j++)
                    targetBuffer[j] = dose[model.TargetPos[j]];

                Array.Sort(targetBuffer);
                double d95 = targetBuffer[d95Index];
                double renorm = d95 > 0.0 ? rx / d95 : double.NaN;

                double max = 0.0;
                int hotCount = 0;

                foreach (int p in model.CandidatePos)
                {
                    double value = dose[p] * renorm;

                    if (value > max)
                        max = value;

                    if (value >= hotThreshold)
                        hotCount++;
                }

                WeightCandidate candidate = new WeightCandidate
                {
                    X = (double[])x.Clone(),
                    D95Raw = d95 / rx * 100.0,
                    DmaxRenormPercent = max / rx * 100.0,
                    HotCcRenorm = hotCount * voxelCc
                };

                EvaluateMu(model, fields, x, renorm, candidate);

                double weighted = 0.0;

                for (int k = 0; k < fields.Count; k++)
                    for (int i = 0; i < fields[k].Count; i++)
                        weighted += fields[k].TotalWeight * x[model.VarIndex[k][i]];

                candidate.MeanSubfieldFraction = totalSubs > 0 ? weighted / totalWeight : 0.0;
                return candidate;
            }

            double[] Compose(double[] x)
            {
                double[] dose = (double[])model.Base.Clone();

                for (int v = 0; v < vars; v++)
                {
                    if (x[v] == 0.0)
                        continue;

                    float[] g = model.Gradients[v];

                    for (int j = 0; j < n; j++)
                        dose[j] += x[v] * g[j];
                }

                return dose;
            }

            bool Feasible(double[] x)
            {
                for (int k = 0; k < fields.Count; k++)
                {
                    double total = 0.0;

                    for (int i = 0; i < fields[k].Count; i++)
                    {
                        double f = x[model.VarIndex[k][i]];

                        if (f < SearchStep - 1e-9 || f > SearchMax + 1e-9)
                            return false;

                        total += f;
                    }

                    if (total > SearchMaxTotal + 1e-9)
                        return false;
                }

                return true;
            }

            // Variable -> subfield index (for the common coarse start).
            int[] varSubIndex = new int[vars];
            int levels = 0;

            for (int k = 0; k < fields.Count; k++)
            {
                levels = Math.Max(levels, fields[k].Count);

                for (int i = 0; i < fields[k].Count; i++)
                    varSubIndex[model.VarIndex[k][i]] = i;
            }

            WeightCandidate baseline = Score(model.Base, new double[vars]);

            // Coarse start: the same fraction per subfield index for all fields.
            WeightCandidate best = null;
            int coarseSteps = (int)Math.Round(SearchMax / CoarseStep);
            int[] counter = new int[levels];

            for (int i = 0; i < levels; i++)
                counter[i] = 1;

            while (true)
            {
                double[] x = new double[vars];

                for (int v = 0; v < vars; v++)
                    x[v] = counter[varSubIndex[v]] * CoarseStep;

                if (Feasible(x))
                {
                    WeightCandidate candidate = Score(Compose(x), x);

                    if (best == null || CompareCandidates(candidate, best) < 0)
                        best = candidate;
                }

                int position = 0;

                while (position < levels && ++counter[position] > coarseSteps)
                {
                    counter[position] = 1;
                    position++;
                }

                if (position >= levels)
                    break;
            }

            if (best == null)
            {
                double[] x = new double[vars];

                for (int v = 0; v < vars; v++)
                    x[v] = SearchStep;

                best = Score(Compose(x), x);
            }

            report.AppendLine(CandidateHeader());
            report.AppendLine(CandidateRow("no FiF", baseline));
            report.AppendLine(CandidateRow("common", best));

            // Refinement: single steps and transfers between subfields of the same field.
            List<int[]> moves = new List<int[]>();

            for (int v = 0; v < vars; v++)
            {
                moves.Add(new[] { v, +1, -1, 0 });
                moves.Add(new[] { v, -1, -1, 0 });
            }

            for (int k = 0; k < fields.Count; k++)
            {
                for (int a = 0; a < fields[k].Count; a++)
                {
                    for (int b = 0; b < fields[k].Count; b++)
                    {
                        int va = model.VarIndex[k][a];
                        int vb = model.VarIndex[k][b];

                        if (va == vb)
                            continue;

                        bool exists = false;

                        foreach (int[] m in moves)
                        {
                            if (m[0] == va && m[1] == +1 && m[2] == vb)
                            {
                                exists = true;
                                break;
                            }
                        }

                        if (!exists)
                            moves.Add(new[] { va, +1, vb, -1 });
                    }
                }
            }

            double[] current = Compose(best.X);
            double[] currentX = (double[])best.X.Clone();
            double[] trial = new double[n];
            double[] bestTrial = new double[n];
            int passes = 0;

            for (; passes < SearchMaxPasses; passes++)
            {
                WeightCandidate passBest = null;

                foreach (int[] move in moves)
                {
                    double[] x = (double[])currentX.Clone();
                    x[move[0]] += move[1] * SearchStep;

                    if (move[2] >= 0)
                        x[move[2]] += move[3] * SearchStep;

                    if (!Feasible(x))
                        continue;

                    float[] ga = model.Gradients[move[0]];
                    double da = move[1] * SearchStep;

                    if (move[2] >= 0)
                    {
                        float[] gb = model.Gradients[move[2]];
                        double db = move[3] * SearchStep;

                        for (int j = 0; j < n; j++)
                            trial[j] = current[j] + da * ga[j] + db * gb[j];
                    }
                    else
                    {
                        for (int j = 0; j < n; j++)
                            trial[j] = current[j] + da * ga[j];
                    }

                    WeightCandidate candidate = Score(trial, x);

                    if (CompareCandidates(candidate, passBest ?? best) < 0)
                    {
                        passBest = candidate;
                        double[] swap = bestTrial;
                        bestTrial = trial;
                        trial = swap;
                    }
                }

                if (passBest == null)
                    break;

                for (int v = 0; v < vars; v++)
                    passBest.X[v] = Math.Round(passBest.X[v] / SearchStep) * SearchStep;

                double[] previous = current;
                current = bestTrial;
                bestTrial = previous;
                currentX = (double[])passBest.X.Clone();
                best = passBest;
            }

            report.AppendLine(CandidateRow("final", best));
            report.AppendLine("Refinement: " + passes + " step(s)" + (passes >= SearchMaxPasses ? " (limit reached)" : ""));

            if (best.DmaxRenormPercent >= baseline.DmaxRenormPercent - 0.1)
            {
                report.AppendLine();
                report.AppendLine("WARNING: at D95 = 100%, field-in-field does not reduce Dmax for this geometry.");
                report.AppendLine("         The blocks remove coverage as fast as they remove the hotspot.");
            }

            if (best.MuDeficit > 0.0)
            {
                report.AppendLine();
                report.AppendLine("WARNING: no split reaches " + FormatNumber(MinBeamMu, "F0") +
                    " MU on every beam within the search limits.");
            }

            return best;
        }

        private static double[][] FieldFractions(LinearModel model, List<FieldSet> fields, double[] x)
        {
            double[][] result = new double[fields.Count][];

            for (int k = 0; k < fields.Count; k++)
            {
                result[k] = new double[fields[k].Count];

                for (int i = 0; i < fields[k].Count; i++)
                    result[k][i] = x[model.VarIndex[k][i]];
            }

            return result;
        }

        private static int CompareCandidates(WeightCandidate a, WeightCandidate b)
        {
            // Minimum MU first, then lower renormalized Dmax (0.05% resolution), smaller V107, less subfield weight.
            if (Math.Abs(a.MuDeficit - b.MuDeficit) > 1e-6)
                return a.MuDeficit.CompareTo(b.MuDeficit);

            if (Math.Abs(a.DmaxRenormPercent - b.DmaxRenormPercent) > 0.05)
                return a.DmaxRenormPercent.CompareTo(b.DmaxRenormPercent);

            if (Math.Abs(a.HotCcRenorm - b.HotCcRenorm) > 0.5)
                return a.HotCcRenorm.CompareTo(b.HotCcRenorm);

            return a.MeanSubfieldFraction.CompareTo(b.MeanSubfieldFraction);
        }

        private static string CandidateHeader()
        {
            return "".PadRight(8) + "sub mean".PadLeft(9) + "D95 raw".PadLeft(10) +
                "Dmax@D95=100".PadLeft(14) + "V107 cc".PadLeft(10) + "min MU".PadLeft(8);
        }

        private static string CandidateRow(string label, WeightCandidate c)
        {
            return label.PadRight(8) +
                FormatPercent(c.MeanSubfieldFraction).PadLeft(9) +
                (FormatNumber(c.D95Raw, "F1") + "%").PadLeft(10) +
                (FormatNumber(c.DmaxRenormPercent, "F1") + "%").PadLeft(14) +
                FormatNumber(c.HotCcRenorm, "F1").PadLeft(10) +
                FormatNumber(c.MinMu, "F1").PadLeft(8);
        }

        // -------------------------------------------------------------------
        // Minimum MU per beam
        // -------------------------------------------------------------------

        private static void CaptureMuPerWeight(List<FieldSet> fields)
        {
            foreach (FieldSet field in fields)
            {
                field.MuPerWeightOriginal = MuPerWeight(field.Original);
                field.MuPerWeightSubs = new double[field.Count];

                for (int i = 0; i < field.Count; i++)
                    field.MuPerWeightSubs[i] = MuPerWeight(field.Subs[i]);
            }
        }

        private static double MuPerWeight(Beam beam)
        {
            double mu = BeamMu(beam);
            double weight = beam.WeightFactor;
            return weight > 0.0 && !double.IsNaN(mu) ? mu / weight : double.NaN;
        }

        private static double BeamMu(Beam beam)
        {
            return beam.Meterset.Value;
        }

        // Predicted MU after renormalization: MU = (MU / weight at calc 2) * weight * renormalization factor.
        private static void EvaluateMu(LinearModel model, List<FieldSet> fields, double[] x, double renorm, WeightCandidate candidate)
        {
            double goal = MinBeamMu * MuPlanningMargin;
            double minMu = double.MaxValue;
            double deficit = 0.0;

            for (int k = 0; k < fields.Count; k++)
            {
                FieldSet field = fields[k];
                double t = field.TotalWeight * renorm;
                double subTotal = 0.0;

                for (int i = 0; i < field.Count; i++)
                {
                    double f = x[model.VarIndex[k][i]];
                    subTotal += f;
                    Accumulate(field.MuPerWeightSubs[i] * t * f);
                }

                Accumulate(field.MuPerWeightOriginal * t * (1.0 - subTotal));
            }

            candidate.MinMu = minMu == double.MaxValue ? double.NaN : minMu;
            candidate.MuDeficit = deficit;

            void Accumulate(double mu)
            {
                if (double.IsNaN(mu))
                    return;

                minMu = Math.Min(minMu, mu);

                if (mu < goal)
                    deficit += goal - mu;
            }
        }

        private static void EnforceMinimumMu(
            ExternalPlanSetup plan,
            List<FieldSet> fields,
            Structure target,
            DoseValue prescription,
            StringBuilder report)
        {
            for (int attempt = 0; ; attempt++)
            {
                report.AppendLine();
                report.AppendLine(attempt == 0
                    ? "MU CHECK (minimum " + FormatNumber(MinBeamMu, "F0") + " MU per beam)"
                    : "MU CHECK after fix " + attempt);
                report.AppendLine("--------------------------------------");

                bool anyLow = false;
                bool changed = false;

                foreach (FieldSet field in fields)
                {
                    double muOriginal = BeamMu(field.Original);
                    StringBuilder line = new StringBuilder(field.Original.Id.PadRight(12) + "orig " + FormatNumber(muOriginal, "F1").PadLeft(6));

                    double total = field.Original.WeightFactor;
                    double[] newWeights = new double[field.Count];
                    bool raise = false;

                    for (int i = 0; i < field.Count; i++)
                    {
                        Beam sub = field.Subs[i];
                        double mu = BeamMu(sub);
                        line.Append("  ." + i + " " + FormatNumber(mu, "F1").PadLeft(5));

                        total += sub.WeightFactor;
                        newWeights[i] = sub.WeightFactor;

                        if (!double.IsNaN(mu) && mu > 0.0 && mu < MinBeamMu)
                        {
                            newWeights[i] = sub.WeightFactor * MinBeamMu * MuPlanningMargin / mu;
                            raise = true;
                        }
                    }

                    report.AppendLine(line.ToString());

                    if (muOriginal < MinBeamMu)
                    {
                        anyLow = true;
                        report.AppendLine("  !!! " + field.Original.Id + " is below " + FormatNumber(MinBeamMu, "F0") +
                            " MU; it is not adjusted automatically.");
                    }

                    if (!raise)
                        continue;

                    anyLow = true;
                    double newOriginal = total - Sum(newWeights);

                    if (attempt < MaxMuRepairs && newOriginal > 0.0)
                    {
                        SetWeight(field.Original, newOriginal);

                        for (int i = 0; i < field.Count; i++)
                            SetWeight(field.Subs[i], newWeights[i]);

                        changed = true;
                    }
                }

                if (!anyLow)
                {
                    report.AppendLine("All beams >= " + FormatNumber(MinBeamMu, "F0") + " MU.");
                    return;
                }

                if (!changed)
                {
                    report.AppendLine("!!! Some beams are still below " + FormatNumber(MinBeamMu, "F0") +
                        " MU. Adjust the weights manually before approving.");
                    return;
                }

                report.AppendLine("Subfield weights raised to reach " + FormatNumber(MinBeamMu, "F0") +
                    " MU (total weight per field kept). Recalculating...");
                Calculate(plan, "MU fix " + (attempt + 1), report);
                Renormalize(plan, target, prescription, report);
            }
        }

        // -------------------------------------------------------------------
        // Dose grid access
        // -------------------------------------------------------------------

        private static float[] ReadDose(Dose dose, DoseValue prescription)
        {
            double offset = ToAbsolute(dose.VoxelToDoseValue(0), prescription);
            double scale = (ToAbsolute(dose.VoxelToDoseValue(1000000), prescription) - offset) / 1000000.0;

            int nx = dose.XSize;
            int ny = dose.YSize;
            int nz = dose.ZSize;

            float[] values = new float[nx * ny * nz];
            int[,] buffer = new int[nx, ny];

            for (int z = 0; z < nz; z++)
            {
                dose.GetVoxels(z, buffer);
                int zOffset = z * nx * ny;

                for (int y = 0; y < ny; y++)
                {
                    int rowOffset = zOffset + y * nx;

                    for (int x = 0; x < nx; x++)
                        values[rowOffset + x] = (float)(buffer[x, y] * scale + offset);
                }
            }

            return values;
        }

        // The plan dose grid may be presented in % of prescription; everything else works in absolute dose.
        private static double ToAbsolute(DoseValue value, DoseValue prescription)
        {
            if (value.Unit == prescription.Unit)
                return value.Dose;

            if (value.IsRelativeDoseValue)
                return value.Dose / 100.0 * prescription.Dose;

            throw new InvalidOperationException("Dose grid unit (" + value.UnitAsString +
                ") cannot be converted to the prescription unit (" + prescription.UnitAsString + ").");
        }

        // A dose level in the presentation of the grid (% or absolute), from an absolute value.
        private static DoseValue LevelFor(Dose dose, double absolute, DoseValue prescription)
        {
            DoseValue sample = dose.VoxelToDoseValue(1000000);

            if (sample.IsRelativeDoseValue && sample.Unit != prescription.Unit)
                return new DoseValue(absolute / prescription.Dose * 100.0, sample.Unit);

            return new DoseValue(absolute, prescription.Unit);
        }

        private static float[] ReadBeamDose(Beam beam, Dose planGrid, int[] evalVoxels, DoseValue prescription)
        {
            BeamDose beamDose = beam.Dose;

            if (beamDose == null)
                throw new InvalidOperationException(beam.Id + " has no beam dose.");

            if (!(beam.WeightFactor > 0.0))
                throw new InvalidOperationException(beam.Id + " has zero weight.");

            return ReadDoseSubset(beamDose, planGrid, evalVoxels, beamDose, prescription);
        }

        // Reads only the given voxels (sorted indices). beamDose != null converts relative beam dose to absolute.
        private static float[] ReadDoseSubset(Dose dose, Dose planGrid, int[] sortedVoxels, BeamDose beamDose, DoseValue prescription)
        {
            if (dose.XSize != planGrid.XSize || dose.YSize != planGrid.YSize || dose.ZSize != planGrid.ZSize ||
                Math.Abs(dose.XRes - planGrid.XRes) > 1e-3 || Math.Abs(dose.YRes - planGrid.YRes) > 1e-3 ||
                Math.Abs(dose.ZRes - planGrid.ZRes) > 1e-3 ||
                (dose.Origin - planGrid.Origin).Length > GeometryToleranceMm)
                throw new InvalidOperationException("Beam dose grid differs from the plan dose grid.");

            double offset = DoseNumber(dose.VoxelToDoseValue(0), beamDose, prescription);
            double scale = (DoseNumber(dose.VoxelToDoseValue(1000000), beamDose, prescription) - offset) / 1000000.0;

            int nx = dose.XSize;
            int ny = dose.YSize;
            int sliceSize = nx * ny;

            float[] values = new float[sortedVoxels.Length];
            int[,] buffer = new int[nx, ny];
            int loadedSlice = -1;

            for (int i = 0; i < sortedVoxels.Length; i++)
            {
                int v = sortedVoxels[i];
                int z = v / sliceSize;

                if (z != loadedSlice)
                {
                    dose.GetVoxels(z, buffer);
                    loadedSlice = z;
                }

                int inSlice = v - z * sliceSize;
                values[i] = (float)(buffer[inSlice % nx, inSlice / nx] * scale + offset);
            }

            return values;
        }

        private static double DoseNumber(DoseValue value, BeamDose beamDose, DoseValue prescription)
        {
            if (beamDose == null)
                return ToAbsolute(value, prescription);

            if (value.Unit == DoseValue.DoseUnit.Percent)
            {
                try
                {
                    return beamDose.GetAbsoluteBeamDoseValue(value).Dose;
                }
                catch
                {
                    // Keep the relative value; the common scale factor absorbs it if consistent.
                }
            }

            return value.Dose;
        }

        private static float[] Subset(float[] values, int[] sortedVoxels)
        {
            float[] result = new float[sortedVoxels.Length];

            for (int i = 0; i < sortedVoxels.Length; i++)
                result[i] = values[sortedVoxels[i]];

            return result;
        }

        private static int[] SortedUnion(int[] a, int[] b)
        {
            int[] all = new int[a.Length + b.Length];
            Array.Copy(a, all, a.Length);
            Array.Copy(b, 0, all, a.Length, b.Length);
            Array.Sort(all);

            List<int> unique = new List<int>(all.Length);

            foreach (int v in all)
            {
                if (unique.Count == 0 || unique[unique.Count - 1] != v)
                    unique.Add(v);
            }

            return unique.ToArray();
        }

        private static int[] PositionsIn(int[] sorted, int[] values)
        {
            int[] result = new int[values.Length];

            for (int i = 0; i < values.Length; i++)
                result[i] = Array.BinarySearch(sorted, values[i]);

            return result;
        }

        private static int[] BuildStructureMask(Dose dose, Structure structure)
        {
            int nx = dose.XSize;
            int ny = dose.YSize;

            int x0, x1, y0, y1, z0, z1;
            IndexBounds(dose, structure.MeshGeometry.Bounds, out x0, out x1, out y0, out y1, out z0, out z1);

            List<int> inside = new List<int>();
            int count = x1 - x0 + 1;

            if (count < 2)
                return inside.ToArray();

            BitArray buffer = new BitArray(count);

            for (int z = z0; z <= z1; z++)
            {
                for (int y = y0; y <= y1; y++)
                {
                    VVector start = VoxelPosition(dose, x0, y, z);
                    VVector stop = VoxelPosition(dose, x1, y, z);

                    SegmentProfile profile = structure.GetSegmentProfile(start, stop, buffer);

                    int i = 0;

                    foreach (SegmentProfilePoint point in profile)
                    {
                        if (i >= count)
                            break;

                        if (point.Value)
                            inside.Add(z * nx * ny + y * nx + (x0 + i));

                        i++;
                    }
                }
            }

            return inside.ToArray();
        }

        private static void IndexBounds(
            Dose dose, Rect3D bounds,
            out int x0, out int x1, out int y0, out int y1, out int z0, out int z1)
        {
            double[] xs = { bounds.X, bounds.X + bounds.SizeX };
            double[] ys = { bounds.Y, bounds.Y + bounds.SizeY };
            double[] zs = { bounds.Z, bounds.Z + bounds.SizeZ };

            double minX = double.MaxValue, maxX = double.MinValue;
            double minY = double.MaxValue, maxY = double.MinValue;
            double minZ = double.MaxValue, maxZ = double.MinValue;

            VVector origin = dose.Origin;

            foreach (double cx in xs)
                foreach (double cy in ys)
                    foreach (double cz in zs)
                    {
                        VVector d = new VVector(cx - origin.x, cy - origin.y, cz - origin.z);
                        double ix = d.ScalarProduct(dose.XDirection) / dose.XRes;
                        double iy = d.ScalarProduct(dose.YDirection) / dose.YRes;
                        double iz = d.ScalarProduct(dose.ZDirection) / dose.ZRes;

                        minX = Math.Min(minX, ix); maxX = Math.Max(maxX, ix);
                        minY = Math.Min(minY, iy); maxY = Math.Max(maxY, iy);
                        minZ = Math.Min(minZ, iz); maxZ = Math.Max(maxZ, iz);
                    }

            x0 = Clamp((int)Math.Floor(minX) - 1, 0, dose.XSize - 1);
            x1 = Clamp((int)Math.Ceiling(maxX) + 1, 0, dose.XSize - 1);
            y0 = Clamp((int)Math.Floor(minY) - 1, 0, dose.YSize - 1);
            y1 = Clamp((int)Math.Ceiling(maxY) + 1, 0, dose.YSize - 1);
            z0 = Clamp((int)Math.Floor(minZ) - 1, 0, dose.ZSize - 1);
            z1 = Clamp((int)Math.Ceiling(maxZ) + 1, 0, dose.ZSize - 1);
        }

        private static VVector VoxelPosition(Dose dose, int x, int y, int z)
        {
            VVector origin = dose.Origin;
            VVector dx = dose.XDirection;
            VVector dy = dose.YDirection;
            VVector dz = dose.ZDirection;

            double ox = x * dose.XRes;
            double oy = y * dose.YRes;
            double oz = z * dose.ZRes;

            return new VVector(
                origin.x + dx.x * ox + dy.x * oy + dz.x * oz,
                origin.y + dx.y * ox + dy.y * oy + dz.y * oz,
                origin.z + dx.z * ox + dy.z * oy + dz.z * oz);
        }

        private static int[] BuildCandidateMask(float[] open, double threshold)
        {
            List<int> result = new List<int>();

            for (int i = 0; i < open.Length; i++)
            {
                if (open[i] >= threshold)
                    result.Add(i);
            }

            return result.ToArray();
        }

        private static float MaxOf(float[] values)
        {
            float max = float.MinValue;

            foreach (float value in values)
            {
                if (value > max)
                    max = value;
            }

            return max;
        }

        // -------------------------------------------------------------------
        // Field resolution
        // -------------------------------------------------------------------

        private static List<FieldSet> ResolveFieldSets(
            ExternalPlanSetup plan,
            StringBuilder report,
            List<string> errors,
            List<Beam> fixedBeams)
        {
            List<FieldSet> result = new List<FieldSet>();

            report.AppendLine("FIELD RESOLUTION");
            report.AppendLine("----------------");

            foreach (Beam original in plan.Beams)
            {
                if (original.IsSetupField || IsExcludedFieldId(original.Id) || IsSubfieldOfAnotherBeam(plan, original.Id))
                    continue;

                if (!IsStaticMlcTreatmentBeam(original))
                {
                    if (original.WeightFactor > 0.0)
                        fixedBeams.Add(original);

                    report.AppendLine("  " + original.Id + ": not a static MLC field - left unchanged.");
                    continue;
                }

                string angleText = FormatNumber(original.ControlPoints[0].GantryAngle, "F1") + "°";
                string unitId = original.TreatmentUnit == null ? "<no unit>" : original.TreatmentUnit.Id;
                FieldSet field = new FieldSet { Original = original };

                for (int i = 0; i < MaxSubfields; i++)
                {
                    Beam sub = FindBeam(plan, original.Id + "." + i);

                    if (sub == null)
                        break;

                    field.Subs.Add(sub);
                }

                for (int i = field.Count + 1; i < 10; i++)
                {
                    if (FindBeam(plan, original.Id + "." + i) != null)
                    {
                        errors.Add(original.Id + ": subfield ." + i + " exists but ." + field.Count +
                            " is missing (number the copies .0, .1, ... without gaps, max " + MaxSubfields + ").");
                        break;
                    }
                }

                StringBuilder line = new StringBuilder("  " + original.Id + " (G" + angleText + ", " + unitId +
                    ", MLC " + original.MLC.Model + ")");

                if (field.Count == 0)
                {
                    line.Append(": no subfields - weight kept.");
                    report.AppendLine(line.ToString());
                    fixedBeams.Add(original);
                    continue;
                }

                foreach (Beam sub in field.Subs)
                    line.Append(" | " + sub.Id);

                report.AppendLine(line.ToString());

                if (!IsSupportedMachine(unitId))
                {
                    errors.Add(original.Id + ": treatment unit '" + unitId + "' is not one of " +
                        String.Join(", ", SupportedMachines) + ".");
                    continue;
                }

                if (field.Count * ProbeFraction >= 1.0)
                {
                    errors.Add(original.Id + ": too many subfields.");
                    continue;
                }

                int errorCount = errors.Count;

                foreach (Beam sub in field.Subs)
                    ValidateSubfield(original, sub, errors);

                if (errors.Count != errorCount)
                    continue;

                // Fresh copies carry the same weight as the original; otherwise all weights form a split.
                double w0 = original.WeightFactor;
                double total = w0;
                bool fresh = true;

                foreach (Beam sub in field.Subs)
                {
                    total += sub.WeightFactor;
                    fresh &= IsNear(sub.WeightFactor, w0);
                }

                field.FreshCopies = fresh;
                field.TotalWeight = fresh ? w0 : total;

                if (!(field.TotalWeight > 0.0))
                {
                    errors.Add(original.Id + ": total weight is zero.");
                    continue;
                }

                result.Add(field);
            }

            report.AppendLine();
            return result;
        }

        private static void ValidateSubfield(Beam original, Beam sub, List<string> errors)
        {
            string prefix = sub.Id + ": ";

            if (!IsStaticMlcTreatmentBeam(sub))
            {
                errors.Add(prefix + "must be a static MLC treatment field (not setup, not arc/dynamic).");
                return;
            }

            if (sub.TreatmentUnit == null || original.TreatmentUnit == null ||
                !String.Equals(sub.TreatmentUnit.Id, original.TreatmentUnit.Id, StringComparison.OrdinalIgnoreCase))
                errors.Add(prefix + "treatment unit differs from " + original.Id + ".");

            if (!String.Equals(sub.EnergyModeDisplayName, original.EnergyModeDisplayName, StringComparison.OrdinalIgnoreCase))
                errors.Add(prefix + "energy differs from " + original.Id + ".");

            if (sub.DoseRate != original.DoseRate)
                errors.Add(prefix + "dose rate differs from " + original.Id + ".");

            if (sub.MLC == null || !String.Equals(sub.MLC.Model, original.MLC.Model, StringComparison.OrdinalIgnoreCase))
                errors.Add(prefix + "MLC model differs from " + original.Id + ".");

            ControlPoint a = original.ControlPoints[0];
            ControlPoint b = sub.ControlPoints[0];

            if (AngularDifference(a.GantryAngle, b.GantryAngle) > AngleToleranceDeg ||
                AngularDifference(a.CollimatorAngle, b.CollimatorAngle) > AngleToleranceDeg ||
                AngularDifference(a.PatientSupportAngle, b.PatientSupportAngle) > AngleToleranceDeg)
                errors.Add(prefix + "gantry/collimator/couch angle differs from " + original.Id + ".");

            VVector ia = original.IsocenterPosition;
            VVector ib = sub.IsocenterPosition;

            if (Math.Abs(ia.x - ib.x) > GeometryToleranceMm ||
                Math.Abs(ia.y - ib.y) > GeometryToleranceMm ||
                Math.Abs(ia.z - ib.z) > GeometryToleranceMm)
                errors.Add(prefix + "isocenter differs from " + original.Id + ".");

            VRect<double> ja = a.JawPositions;
            VRect<double> jb = b.JawPositions;

            if (Math.Abs(ja.X1 - jb.X1) > GeometryToleranceMm ||
                Math.Abs(ja.X2 - jb.X2) > GeometryToleranceMm ||
                Math.Abs(ja.Y1 - jb.Y1) > GeometryToleranceMm ||
                Math.Abs(ja.Y2 - jb.Y2) > GeometryToleranceMm)
                errors.Add(prefix + "jaw positions differ from " + original.Id + ".");

            float[,] la = a.LeafPositions;
            float[,] lb = b.LeafPositions;

            if (la == null || lb == null || la.GetLength(0) != 2 ||
                la.GetLength(0) != lb.GetLength(0) || la.GetLength(1) != lb.GetLength(1))
                errors.Add(prefix + "leaf layout differs from " + original.Id + ".");
        }

        private static bool IsStaticMlcTreatmentBeam(Beam beam)
        {
            if (beam.IsSetupField || beam.MLC == null)
                return false;

            if (beam.MLCPlanType != MLCPlanType.Static)
                return false;

            if (beam.ControlPoints == null || beam.ControlPoints.Count == 0)
                return false;

            double first = beam.ControlPoints[0].GantryAngle;
            double last = beam.ControlPoints[beam.ControlPoints.Count - 1].GantryAngle;

            return AngularDifference(first, last) <= GantryToleranceDeg;
        }

        private static bool IsSupportedMachine(string unitId)
        {
            string id = NormalizeMachineId(unitId);

            foreach (string machine in SupportedMachines)
            {
                if (id == NormalizeMachineId(machine))
                    return true;
            }

            return false;
        }

        private static string NormalizeMachineId(string id)
        {
            return (id ?? "").Replace(" ", "").Replace("-", "").Replace("_", "").ToUpperInvariant();
        }

        // Setup/portal images (PORTAL_0, PORTAL_90) are never treated as originals.
        private static bool IsExcludedFieldId(string id)
        {
            return id != null && id.StartsWith("PORTAL", StringComparison.OrdinalIgnoreCase);
        }

        // "<base>.<digit>" is a subfield when a beam named <base> exists in the plan.
        private static bool IsSubfieldOfAnotherBeam(ExternalPlanSetup plan, string id)
        {
            if (id == null || id.Length < 3)
                return false;

            int dot = id.Length - 2;

            if (id[dot] != '.' || !Char.IsDigit(id[id.Length - 1]))
                return false;

            return FindBeam(plan, id.Substring(0, dot)) != null;
        }

        // -------------------------------------------------------------------
        // Leaf computation
        // -------------------------------------------------------------------

        private static float[,] FitAndBlock(Beam subfield, Structure region, BeamState original)
        {
            // Eclipse projects the region onto the subfield; the fitted aperture is the region per leaf row.
            subfield.FitMLCToStructure(
                new FitToStructureMargins(0.0),
                region,
                false,
                JawFitting.None,
                OpenLeavesMeetingPoint.OpenLeavesMeetingPoint_Middle,
                ClosedLeavesMeetingPoint.ClosedLeavesMeetingPoint_Center);

            float[,] projection = (float[,])subfield.ControlPoints[0].LeafPositions.Clone();

            int rowsChanged;
            return ComputeBlockedLeaves(original.Leaves, projection, original.Jaws, out rowsChanged);
        }

        private static float[,] ComputeBlockedLeaves(
            float[,] originalLeaves,
            float[,] regionProjection,
            VRect<double> jaws,
            out int rowsChanged)
        {
            // Bank 0 = X1 leaves, bank 1 = X2 leaves; same indexing for both arrays.
            float[,] result = (float[,])originalLeaves.Clone();
            int pairs = originalLeaves.GetLength(1);
            rowsChanged = 0;

            for (int i = 0; i < pairs; i++)
            {
                double left = originalLeaves[0, i];
                double right = originalLeaves[1, i];

                if (right - left <= ClosedGapMm)
                    continue;

                double regionLeft = regionProjection[0, i];
                double regionRight = regionProjection[1, i];

                if (regionRight - regionLeft <= ClosedGapMm)
                    continue;

                double openLeft = Math.Max(left, jaws.X1);
                double openRight = Math.Min(right, jaws.X2);

                if (openRight - openLeft <= ClosedGapMm)
                    continue;

                double blockLeft = Math.Max(regionLeft, openLeft);
                double blockRight = Math.Min(regionRight, openRight);

                if (blockRight <= blockLeft)
                    continue;

                // Close the leaf on the side nearest to the region.
                double distanceFromLeft = blockLeft - openLeft;
                double distanceFromRight = openRight - blockRight;

                if (distanceFromLeft <= distanceFromRight)
                    result[0, i] = (float)Math.Min(blockRight, right);
                else
                    result[1, i] = (float)Math.Max(blockLeft, left);

                rowsChanged++;
            }

            return result;
        }

        private static LeafApplyResult ApplyLeavesWithValidation(
            Beam beam,
            float[,] originalLeaves,
            float[,] requestedLeaves,
            VRect<double> jaws,
            double weight)
        {
            LeafApplyResult result = new LeafApplyResult();
            int pairs = originalLeaves.GetLength(1);

            for (int i = 0; i < pairs; i++)
            {
                if (requestedLeaves[0, i] != originalLeaves[0, i] || requestedLeaves[1, i] != originalLeaves[1, i])
                    result.RowsRequested++;
            }

            if (TryApplyBeam(beam, requestedLeaves, jaws, weight))
            {
                result.Leaves = requestedLeaves;
                result.FullShapeAccepted = true;
                result.RowsFull = result.RowsRequested;
                return result;
            }

            // Start from the original aperture, which Eclipse already accepts.
            float[,] current = (float[,])originalLeaves.Clone();
            ApplyBeam(beam, current, jaws, weight);

            for (int i = 0; i < pairs; i++)
            {
                int bank =
                    requestedLeaves[0, i] != originalLeaves[0, i] ? 0 :
                    requestedLeaves[1, i] != originalLeaves[1, i] ? 1 : -1;

                if (bank < 0)
                    continue;

                float from = originalLeaves[bank, i];
                float to = requestedLeaves[bank, i];

                if (TryApplyRow(beam, current, i, bank, to, jaws, weight))
                {
                    result.RowsFull++;
                    continue;
                }

                bool accepted = false;
                float opposite = originalLeaves[1 - bank, i];

                if (Math.Abs(to - opposite) < FallbackGapMm)
                {
                    float withGap = bank == 0 ? opposite - FallbackGapMm : opposite + FallbackGapMm;

                    if (TryApplyRow(beam, current, i, bank, withGap, jaws, weight))
                    {
                        result.RowsFull++;
                        accepted = true;
                    }
                }

                if (!accepted)
                {
                    foreach (double fraction in PartialTravelFractions)
                    {
                        float partial = (float)(from + (to - from) * fraction);

                        if (TryApplyRow(beam, current, i, bank, partial, jaws, weight))
                        {
                            result.RowsPartial++;
                            accepted = true;
                            break;
                        }
                    }
                }

                if (!accepted)
                    result.RowsSkipped++;
            }

            ApplyBeam(beam, current, jaws, weight);
            result.Leaves = current;
            return result;
        }

        private static string DescribeLeafResult(string beamId, LeafApplyResult result)
        {
            if (result.RowsRequested == 0)
                return beamId + ": region outside the aperture - same shape as the original.";

            if (result.FullShapeAccepted)
                return beamId + ": " + result.RowsRequested + " row(s) blocked.";

            return beamId + ": " + result.RowsRequested + " row(s) requested -> full " + result.RowsFull +
                " | partial " + result.RowsPartial + " | rejected " + result.RowsSkipped;
        }

        private static bool TryApplyRow(
            Beam beam, float[,] current, int row, int bank, float position, VRect<double> jaws, double weight)
        {
            float previous = current[bank, row];
            current[bank, row] = position;

            if (TryApplyBeam(beam, current, jaws, weight))
                return true;

            current[bank, row] = previous;
            return false;
        }

        private static bool TryApplyBeam(Beam beam, float[,] leaves, VRect<double> jaws, double weight)
        {
            try
            {
                ApplyBeam(beam, leaves, jaws, weight);
                return true;
            }
            catch (ValidationException)
            {
                return false;
            }
        }

        private static void ApplyBeam(Beam beam, float[,] leaves, VRect<double> jaws, double weight)
        {
            BeamParameters parameters = beam.GetEditableParameters();
            parameters.SetJawPositions(jaws);
            parameters.SetAllLeafPositions(leaves);
            parameters.WeightFactor = weight;
            beam.ApplyParameters(parameters);
        }

        private static void SetWeight(Beam beam, double weight)
        {
            BeamParameters parameters = beam.GetEditableParameters();
            parameters.WeightFactor = weight;
            beam.ApplyParameters(parameters);
        }

        private static BeamState CaptureState(Beam beam)
        {
            ControlPoint cp = beam.ControlPoints[0];

            return new BeamState
            {
                Beam = beam,
                Leaves = (float[,])cp.LeafPositions.Clone(),
                Jaws = cp.JawPositions,
                Weight = beam.WeightFactor
            };
        }

        private static BeamState FindState(List<BeamState> states, Beam beam)
        {
            foreach (BeamState state in states)
            {
                if (String.Equals(state.Beam.Id, beam.Id, StringComparison.Ordinal))
                    return state;
            }

            throw new InvalidOperationException("No snapshot for beam " + beam.Id + ".");
        }

        private static bool RestoreAll(List<BeamState> states, StringBuilder report)
        {
            bool allRestored = true;

            foreach (BeamState state in states)
            {
                try
                {
                    ApplyBeam(state.Beam, state.Leaves, state.Jaws, state.Weight);
                }
                catch (Exception restoreException)
                {
                    allRestored = false;
                    report.AppendLine("!!! Could not restore " + state.Beam.Id + ": " + restoreException.Message);
                }
            }

            return allRestored;
        }

        // -------------------------------------------------------------------
        // Structures and metrics
        // -------------------------------------------------------------------

        private static Structure PrepareDoseStructure(
            StructureSet structureSet, string id, Dose dose, DoseValue level)
        {
            Structure structure = FindStructure(structureSet, id);

            if (structure == null)
            {
                if (!structureSet.CanAddStructure("CONTROL", id))
                    throw new InvalidOperationException(
                        "Cannot add structure '" + id + "' to structure set '" + structureSet.Id +
                        "' (structure set may be approved or shared).");

                structure = structureSet.AddStructure("CONTROL", id);
            }

            structure.ConvertDoseLevelToStructure(dose, level);
            return structure;
        }

        private static void RemoveControlStructures(StructureSet structureSet, StringBuilder report)
        {
            List<Structure> toRemove = new List<Structure>();

            foreach (Structure structure in structureSet.Structures)
            {
                if (structure.Id.StartsWith(ControlStructurePrefix, StringComparison.OrdinalIgnoreCase))
                    toRemove.Add(structure);
            }

            if (toRemove.Count == 0)
                return;

            List<string> removed = new List<string>();
            List<string> kept = new List<string>();

            foreach (Structure structure in toRemove)
            {
                string id = structure.Id;

                try
                {
                    if (structureSet.CanRemoveStructure(structure))
                    {
                        structureSet.RemoveStructure(structure);
                        removed.Add(id);
                    }
                    else
                    {
                        kept.Add(id);
                    }
                }
                catch (Exception ex)
                {
                    kept.Add(id + " (" + ex.Message + ")");
                }
            }

            report.AppendLine();
            report.AppendLine("CLEANUP");
            report.AppendLine("-------");

            if (removed.Count > 0)
                report.AppendLine("Removed temporary structures: " + String.Join(", ", removed.ToArray()));

            if (kept.Count > 0)
                report.AppendLine("!!! Could not remove: " + String.Join(", ", kept.ToArray()) + " - delete manually.");
        }

        private static PlanMetrics MeasurePlan(
            ExternalPlanSetup plan,
            Structure body,
            Structure target,
            DoseValue prescription,
            DoseValue hotLevel)
        {
            PlanMetrics metrics = new PlanMetrics();

            if (plan.Dose == null || !plan.IsDoseValid)
                return metrics;

            try
            {
                DoseValue dmax = plan.Dose.DoseMax3D;
                metrics.DmaxText = FormatDose(dmax);

                if (dmax.Unit == prescription.Unit)
                    metrics.DmaxPercent = dmax.Dose / prescription.Dose * 100.0;
                else if (dmax.IsRelativeDoseValue)
                    metrics.DmaxPercent = dmax.Dose;
            }
            catch
            {
            }

            if (body != null)
            {
                try
                {
                    metrics.BodyHotCc = plan.GetVolumeAtDose(
                        body, LevelFor(plan.Dose, hotLevel.Dose, prescription), VolumePresentation.AbsoluteCm3);
                }
                catch
                {
                }
            }

            try
            {
                metrics.TargetD95Percent = TargetD95(plan, target, prescription) / prescription.Dose * 100.0;
            }
            catch
            {
            }

            try
            {
                metrics.TargetV95Percent = plan.GetVolumeAtDose(
                    target, LevelFor(plan.Dose, prescription.Dose * 0.95, prescription), VolumePresentation.Relative);
                metrics.TargetV100Percent = plan.GetVolumeAtDose(
                    target, LevelFor(plan.Dose, prescription.Dose, prescription), VolumePresentation.Relative);
            }
            catch
            {
            }

            return metrics;
        }

        private static Structure FindStructure(StructureSet structureSet, string id)
        {
            if (structureSet == null || String.IsNullOrEmpty(id))
                return null;

            foreach (Structure structure in structureSet.Structures)
            {
                if (String.Equals(structure.Id, id, StringComparison.OrdinalIgnoreCase))
                    return structure;
            }

            return null;
        }

        private static Structure FindBody(StructureSet structureSet)
        {
            foreach (Structure structure in structureSet.Structures)
            {
                if (String.Equals(structure.DicomType, "EXTERNAL", StringComparison.OrdinalIgnoreCase))
                    return structure;
            }

            return null;
        }

        private static Beam FindBeam(ExternalPlanSetup plan, string id)
        {
            foreach (Beam beam in plan.Beams)
            {
                if (String.Equals(beam.Id, id, StringComparison.OrdinalIgnoreCase))
                    return beam;
            }

            return null;
        }

        // -------------------------------------------------------------------
        // Helpers
        // -------------------------------------------------------------------

        private static double Sum(double[] values)
        {
            double total = 0.0;

            foreach (double value in values)
                total += value;

            return total;
        }

        private static bool IsNear(double value, double reference)
        {
            return Math.Abs(value - reference) <= WeightRelativeTolerance * Math.Max(Math.Abs(reference), 1e-9);
        }

        private static double AngularDifference(double a, double b)
        {
            double d = Math.Abs(a - b) % 360.0;
            return d > 180.0 ? 360.0 - d : d;
        }

        private static int Clamp(int value, int min, int max)
        {
            return value < min ? min : value > max ? max : value;
        }

        private static string FormatNumber(double value, string format)
        {
            return double.IsNaN(value) ? "n/a" : value.ToString(format, CultureInfo.InvariantCulture);
        }

        private static string FormatPercent(double fraction)
        {
            return FormatNumber(fraction * 100.0, "F1") + "%";
        }

        private static string FormatDose(DoseValue dose)
        {
            return FormatNumber(dose.Dose, "F1") + " " + dose.UnitAsString;
        }

        private static string Row(string label, string before, string after)
        {
            return label.PadRight(24) + before.PadLeft(14) + after.PadLeft(14);
        }

        private static void Warn(string message)
        {
            MessageBox.Show(message, ScriptTitle, MessageBoxButton.OK, MessageBoxImage.Warning);
        }

        private static void SetHostWindowStatus(Window window)
        {
            // Eclipse shows its own script window while Execute runs; give it a short status instead of a blank area.
            if (window == null)
                return;

            try
            {
                window.Title = ScriptTitle;
                window.Content = new TextBlock
                {
                    Text = ScriptTitle + " running - see the report window." + Environment.NewLine +
                        "Several dose calculations may take a few minutes.",
                    Margin = new Thickness(20),
                    FontSize = 14
                };
                window.SizeToContent = SizeToContent.WidthAndHeight;
            }
            catch
            {
                // Cosmetic only.
            }
        }

        private static bool ShowReport(string message, string title, Window owner, bool askConfirmation)
        {
            // Dedicated WPF window so long reports remain scrollable and buttons stay visible.
            Window dialog = new Window
            {
                Title = title,
                Width = 820,
                Height = 780,
                MinWidth = 600,
                MinHeight = 500,
                WindowStartupLocation = owner != null
                    ? WindowStartupLocation.CenterOwner
                    : WindowStartupLocation.CenterScreen,
                ResizeMode = ResizeMode.CanResize,
                ShowInTaskbar = false
            };

            if (owner != null)
                dialog.Owner = owner;

            Grid root = new Grid { Margin = new Thickness(10) };
            root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

            TextBox reportBox = new TextBox
            {
                Text = message,
                IsReadOnly = true,
                TextWrapping = TextWrapping.NoWrap,
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Auto,
                FontFamily = new FontFamily("Consolas"),
                FontSize = 13,
                Padding = new Thickness(8),
                BorderThickness = new Thickness(1)
            };

            Grid.SetRow(reportBox, 0);
            root.Children.Add(reportBox);

            StackPanel buttonPanel = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                HorizontalAlignment = HorizontalAlignment.Right,
                Margin = new Thickness(0, 10, 0, 0)
            };

            if (askConfirmation)
            {
                // Proceed must be clicked explicitly; Enter/Esc both resolve to Cancel.
                Button proceedButton = new Button
                {
                    Content = "Proceed",
                    Width = 110,
                    Height = 32,
                    Margin = new Thickness(5, 0, 0, 0)
                };

                Button cancelButton = new Button
                {
                    Content = "Cancel",
                    Width = 110,
                    Height = 32,
                    Margin = new Thickness(5, 0, 0, 0),
                    IsDefault = true,
                    IsCancel = true
                };

                proceedButton.Click += delegate { dialog.DialogResult = true; };
                cancelButton.Click += delegate { dialog.DialogResult = false; };

                buttonPanel.Children.Add(proceedButton);
                buttonPanel.Children.Add(cancelButton);

                dialog.Loaded += delegate { cancelButton.Focus(); };
            }
            else
            {
                Button okButton = new Button
                {
                    Content = "OK",
                    Width = 110,
                    Height = 32,
                    Margin = new Thickness(5, 0, 0, 0),
                    IsDefault = true,
                    IsCancel = true
                };

                okButton.Click += delegate { dialog.DialogResult = true; };
                buttonPanel.Children.Add(okButton);
            }

            Grid.SetRow(buttonPanel, 1);
            root.Children.Add(buttonPanel);

            dialog.Content = root;

            bool? result = dialog.ShowDialog();
            return askConfirmation && result == true;
        }
    }
}
