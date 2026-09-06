using Assets.Sources.Scripts.UI.Common;
using FF9;
using Memoria;
using Memoria.Data;
using System;

namespace Memoria.Scripts.Lexeditor
{
    /// <summary>Eat/Cook that refuses to consume a target when it cannot teach anything.</summary>
    [BattleScript(65)]
    public sealed class BetterEatScript : IBattleScript, IEstimateBattleScript
    {
        private readonly BattleCalculator _v;

        public BetterEatScript(BattleCalculator v)
        {
            _v = v;
        }

        public void Perform()
        {
            if (!LexeditorFeatureConfig.BetterEat)
            {
                PerformVanilla();
                return;
            }
            if (!_v.Target.CheckUnsafetyOrMiss() || !_v.Target.CanBeAttacked() || _v.Target.HasCategory(EnemyCategory.Humanoid))
            {
                _v.Context.EatResult = EatResult.CannotEat;
                UiState.SetBattleFollowFormatMessage(BattleMesages.CannotEat);
                return;
            }
            if (_v.Target.CurrentHp > _v.Target.MaximumHp / _v.Command.Power)
            {
                _v.Context.EatResult = EatResult.Failed;
                UiState.SetBattleFollowFormatMessage(BattleMesages.CannotEatStrong);
                return;
            }
            BattleEnemyPrototype enemy = BattleEnemyPrototype.Find(_v.Target);
            Int32 blueMagic = enemy.BlueMagicId;
            if (blueMagic == 0 || ff9abil.FF9Abil_IsMaster(_v.Caster.Player, blueMagic))
            {
                _v.Context.EatResult = EatResult.TasteBad;
                UiState.SetBattleFollowFormatMessage(BattleMesages.TasteBad);
                return;
            }
            _v.Target.Kill(_v.Caster);
            Learn(blueMagic);
        }

        private void PerformVanilla()
        {
            if (!_v.Target.CheckUnsafetyOrMiss() || !_v.Target.CanBeAttacked() || _v.Target.HasCategory(EnemyCategory.Humanoid))
            {
                _v.Context.EatResult = EatResult.CannotEat;
                UiState.SetBattleFollowFormatMessage(BattleMesages.CannotEat);
                return;
            }
            if (_v.Target.CurrentHp > _v.Target.MaximumHp / _v.Command.Power)
            {
                _v.Context.EatResult = EatResult.Failed;
                UiState.SetBattleFollowFormatMessage(BattleMesages.CannotEatStrong);
                return;
            }
            BattleEnemyPrototype enemy = BattleEnemyPrototype.Find(_v.Target);
            Int32 blueMagic = enemy.BlueMagicId;
            _v.Target.Kill(_v.Caster);
            if (blueMagic == 0 || ff9abil.FF9Abil_IsMaster(_v.Caster.Player, blueMagic))
            {
                _v.Context.EatResult = EatResult.TasteBad;
                UiState.SetBattleFollowFormatMessage(BattleMesages.TasteBad);
                return;
            }
            Learn(blueMagic);
        }

        private void Learn(Int32 blueMagic)
        {
            _v.Context.EatResult = EatResult.Yummy;
            ff9abil.FF9Abil_SetMaster(_v.Caster.Player, blueMagic);
            BattleState.RaiseAbilitiesAchievement(blueMagic);
            if (ff9abil.IsAbilityActive(blueMagic))
                UiState.SetBattleFollowFormatMessage(BattleMesages.Learned, FF9TextTool.ActionAbilityName(ff9abil.GetActiveAbilityFromAbilityId(blueMagic)));
            else
                UiState.SetBattleFollowFormatMessage(BattleMesages.Learned, FF9TextTool.SupportAbilityName(ff9abil.GetSupportAbilityFromAbilityId(blueMagic)));
        }

        public Single RateTarget()
        {
            if (!_v.Target.CheckUnsafetyOrMiss() || !_v.Target.CanBeAttacked() || _v.Target.HasCategory(EnemyCategory.Humanoid))
                return 0f;
            if (_v.Target.CurrentHp > _v.Target.MaximumHp / _v.Command.Power)
                return 0f;
            BattleEnemyPrototype enemy = BattleEnemyPrototype.Find(_v.Target);
            Int32 blueMagic = enemy.BlueMagicId;
            if (blueMagic == 0 || ff9abil.FF9Abil_IsMaster(_v.Caster.Player, blueMagic))
                return 0f;
            return 1f;
        }
    }
}
