using Memoria;
using Memoria.Data;
using System;

namespace Memoria.Scripts.Lexeditor
{
    public sealed class LexeditorRowReworkScriptStart : IOverloadOnBattleScriptStartScript
    {
        public Boolean OnBattleScriptStart(BattleCalculator v)
        {
  if (LexeditorFeatureConfig.RowRework && IsBlockedMelee(v))
  {
      v.Context.Flags |= BattleCalcFlags.Miss;
      return true;
  }

  // ScriptsLoader uses one IOverloadOnBattleScriptStartScript globally.
  // Preserve pinned Memoria's default pre-script behavior exactly when
  // Row Rework does not veto the action.
  if (Configuration.Battle.CustomBattleFlagsMeaning == 1)
  {
      if (v.Command.IsShortRange)
      {
          v.BonusBackstabAndPenaltyLongDistanceVisually();
          if ((v.Command.AbilityCategory & 8) != 0 && v.Target.IsUnderAnyStatus(BattleStatus.Vanish))
              v.Context.Flags |= BattleCalcFlags.Miss;
      }
      if ((v.Command.AbilityType & 0x10) != 0 && v.Caster.IsPlayer)
          v.ApplyElementFullStack(v.Caster.WeaponElement, v.Caster.WeaponElement);
      if ((v.Context.Flags & (BattleCalcFlags.Miss | BattleCalcFlags.Guard)) != 0)
          return true;
  }
  if ((v.Command.AbilityCategory & 8) != 0 && v.Target.TryKillFrozen())
      return true;
  return false;
        }

        internal static Boolean IsBlockedMelee(BattleCalculator v)
        {
  if (v == null || v.Caster == null || v.Target == null || v.Command == null)
      return false;
  Boolean physical = (v.Command.AbilityCategory & 8) != 0;
  if (!physical || !v.Command.IsShortRange)
      return false;
  return (v.Caster.IsPlayer && v.Caster.Row == 0) ||
         (v.Target.IsPlayer && v.Target.Row == 0);
        }
    }
}
