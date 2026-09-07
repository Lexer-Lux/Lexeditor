using System;
using System.Collections;
using System.Reflection;
using UnityEngine;
using Object = System.Object;

namespace Memoria.Scripts.Lexeditor
{
    /// <summary>Small visual-only FF9 UI additions that anchor to Memoria's real widgets.</summary>
    public sealed class LexeditorUIEnhancements : MonoBehaviour
    {
        private FieldInfo _dialogChoiceListField;
        private FieldInfo _battlePartyField;
        private FieldInfo _resultHudListField;

        private void OnGUI()
        {
            if (LexeditorFeatureConfig.ImprovedInterface)
                DrawMognetRecipientHighlight();
            if (LexeditorFeatureConfig.XPBars)
                DrawXPBars();
            if (LexeditorFeatureConfig.HPMPBars)
                DrawHPMPBars();
        }

        private void DrawMognetRecipientHighlight()
        {
            UIManager ui = PersistenSingleton<UIManager>.Instance;
            DialogManager dialogs = ui != null ? ui.Dialogs : null;
            Dialog dialog = dialogs != null ? dialogs.GetChoiceDialog() : null;
            if (dialog == null || !dialog.IsActive || !dialog.HasChoices)
                return;

            // Vanilla Moogle_Make_SpeakBTN builds the top-level Moogle choice mask
            // from 0x47 and adds bit 3 only when VAR_B3_1 >= 0: this Moogle has
            // a letter-delivery option for the player. Mognet is choice index 2
            // in the normal Save / Tent / Mognet / ... / Cancel menu.
            Int32 mask = dialog.ChooseMask;
            if ((mask & 0x47) != 0x47 || (mask & 0x08) == 0)
                return;

            if (_dialogChoiceListField == null)
                _dialogChoiceListField = typeof(Dialog).GetField("choiceList", BindingFlags.Instance | BindingFlags.NonPublic);
            IList choices = _dialogChoiceListField != null ? _dialogChoiceListField.GetValue(dialog) as IList : null;
            if (choices == null || choices.Count <= 2)
                return;

            GameObject mognetChoice = choices[2] as GameObject;
            Rect rect;
            if (mognetChoice == null || !TryGetGuiRect(mognetChoice, out rect))
                return;

            Color accent = new Color(1.0f, 0.74f, 0.12f, 0.95f);
            DrawSolid(new Rect(rect.x - 8f, rect.y + 1f, 4f, Math.Max(2f, rect.height - 2f)), accent);
            DrawSolid(new Rect(rect.x - 2f, rect.yMax - 3f, rect.width + 4f, 3f), accent);
        }

        private void DrawXPBars()
        {
            UIManager ui = PersistenSingleton<UIManager>.Instance;
            if (ui == null || ui.State != UIManager.UIState.BattleResult || ui.BattleResultScene == null)
                return;

            if (_resultHudListField == null)
                _resultHudListField = typeof(BattleResultUI).GetField("characterBRInfoHudList", BindingFlags.Instance | BindingFlags.NonPublic);
            IList huds = _resultHudListField != null ? _resultHudListField.GetValue(ui.BattleResultScene) as IList : null;
            if (huds == null)
                return;

            Int32 count = Math.Min(4, huds.Count);
            for (Int32 i = 0; i < count; i++)
            {
                PLAYER player = FF9StateSystem.Common.FF9.party.member[i];
                if (player == null || huds[i] == null)
                    continue;

                UIWidget avatar = GetMember(huds[i], "AvatarSprite") as UIWidget;
                UIWidget name = GetMember(huds[i], "NameLabel") as UIWidget;
                UIWidget exp = GetMember(huds[i], "ExpLabel") as UIWidget;
                UIWidget next = GetMember(huds[i], "NextLvLabel") as UIWidget;
                Rect block;
                if (!TryUnionWidgets(new UIWidget[] { avatar, name, exp, next }, out block))
                    continue;

                Single fraction = ExperienceFraction(player);
                Rect bar = new Rect(block.x + 3f, block.yMax + 1f, Math.Max(24f, block.width - 6f), 6f);
                DrawBar(bar, fraction, new Color(0.95f, 0.72f, 0.16f, 1f));
            }
        }

        private void DrawHPMPBars()
        {
            UIManager ui = PersistenSingleton<UIManager>.Instance;
            BattleHUD hud = UIManager.Battle;
            if (ui == null || ui.State != UIManager.UIState.BattleHUD || hud == null)
                return;

            if (_battlePartyField == null)
                _battlePartyField = typeof(BattleHUD).GetField("_partyDetail", BindingFlags.Instance | BindingFlags.NonPublic);
            Object party = _battlePartyField != null ? _battlePartyField.GetValue(hud) : null;
            Object table = GetMember(party, "Characters");
            IEnumerable entries = GetMember(table, "Entries") as IEnumerable;
            if (entries == null)
                return;

            foreach (Object character in entries)
            {
                if (character == null)
                    continue;
                Object idValue = GetMember(character, "PlayerId");
                if (!(idValue is Int32))
                    continue;
                Int32 playerId = (Int32)idValue;
                if (playerId < 0)
                    continue;
                BattleUnit unit = FF9StateSystem.Battle.FF9Battle.GetUnit(playerId);
                if (unit == null)
                    continue;

                UILabel hpLabel = GetMember(GetMember(character, "HP"), "Label") as UILabel;
                UILabel mpLabel = GetMember(GetMember(character, "MP"), "Label") as UILabel;
                Rect hpRect;
                Rect mpRect;
                if (hpLabel != null && TryGetGuiRect(hpLabel, out hpRect))
                    DrawBar(new Rect(hpRect.x, hpRect.yMax + 1f, Math.Max(24f, hpRect.width), 5f), Ratio(unit.CurrentHp, unit.MaximumHp), new Color(0.92f, 0.18f, 0.18f, 1f));
                if (mpLabel != null && TryGetGuiRect(mpLabel, out mpRect))
                    DrawBar(new Rect(mpRect.x, mpRect.yMax + 1f, Math.Max(24f, mpRect.width), 5f), Ratio(unit.CurrentMp, unit.MaximumMp), new Color(0.18f, 0.48f, 1.0f, 1f));
            }
        }

        private static Single ExperienceFraction(PLAYER player)
        {
            if (player == null)
                return 0f;
            if (player.level >= ff9level.LEVEL_COUNT)
                return 1f;
            Int32 currentIndex = Math.Max(0, (Int32)player.level - 1);
            UInt32 currentLevelExp = ff9level.CharacterLevelUps[currentIndex].ExperienceToLevel;
            UInt32 nextLevelExp = ff9level.CharacterLevelUps[player.level].ExperienceToLevel;
            if (nextLevelExp <= currentLevelExp)
                return 1f;
            UInt64 gained = player.exp > currentLevelExp ? (UInt64)player.exp - currentLevelExp : 0UL;
            UInt64 needed = (UInt64)nextLevelExp - currentLevelExp;
            return Mathf.Clamp01((Single)gained / needed);
        }

        private static Single Ratio(UInt32 value, UInt32 maximum)
        {
            if (maximum == 0)
                return 0f;
            return Mathf.Clamp01((Single)value / maximum);
        }

        private static void DrawBar(Rect rect, Single fraction, Color fill)
        {
            DrawSolid(rect, new Color(0f, 0f, 0f, 0.82f));
            Single innerWidth = Math.Max(0f, (rect.width - 2f) * Mathf.Clamp01(fraction));
            DrawSolid(new Rect(rect.x + 1f, rect.y + 1f, innerWidth, Math.Max(0f, rect.height - 2f)), fill);
        }

        private static void DrawSolid(Rect rect, Color color)
        {
            Color old = GUI.color;
            GUI.color = color;
            GUI.DrawTexture(rect, Texture2D.whiteTexture);
            GUI.color = old;
        }

        private static Boolean TryUnionWidgets(UIWidget[] widgets, out Rect result)
        {
            result = new Rect();
            Boolean any = false;
            for (Int32 i = 0; i < widgets.Length; i++)
            {
                Rect rect;
                if (widgets[i] == null || !widgets[i].gameObject.activeInHierarchy || !TryGetGuiRect(widgets[i], out rect))
                    continue;
                if (!any)
                {
                    result = rect;
                    any = true;
                }
                else
                {
                    Single xMin = Math.Min(result.xMin, rect.xMin);
                    Single yMin = Math.Min(result.yMin, rect.yMin);
                    Single xMax = Math.Max(result.xMax, rect.xMax);
                    Single yMax = Math.Max(result.yMax, rect.yMax);
                    result = Rect.MinMaxRect(xMin, yMin, xMax, yMax);
                }
            }
            return any;
        }

        private static Boolean TryGetGuiRect(GameObject go, out Rect result)
        {
            result = new Rect();
            if (go == null || !go.activeInHierarchy)
                return false;
            UIWidget widget = go.GetComponent<UIWidget>();
            if (widget != null)
                return TryGetGuiRect(widget, out result);
            return TryUnionWidgets(go.GetComponentsInChildren<UIWidget>(true), out result);
        }

        private static Boolean TryGetGuiRect(UIWidget widget, out Rect result)
        {
            result = new Rect();
            if (widget == null)
                return false;
            Camera camera = NGUITools.FindCameraForLayer(widget.gameObject.layer);
            if (camera == null)
                return false;
            Vector3[] corners = widget.worldCorners;
            if (corners == null || corners.Length < 4)
                return false;
            Vector3 first = camera.WorldToScreenPoint(corners[0]);
            Single xMin = first.x;
            Single xMax = first.x;
            Single yMin = first.y;
            Single yMax = first.y;
            for (Int32 i = 1; i < corners.Length; i++)
            {
                Vector3 point = camera.WorldToScreenPoint(corners[i]);
                xMin = Math.Min(xMin, point.x);
                xMax = Math.Max(xMax, point.x);
                yMin = Math.Min(yMin, point.y);
                yMax = Math.Max(yMax, point.y);
            }
            if (xMax <= xMin || yMax <= yMin)
                return false;
            result = Rect.MinMaxRect(xMin, Screen.height - yMax, xMax, Screen.height - yMin);
            return true;
        }

        private static Object GetMember(Object target, String name)
        {
            if (target == null)
                return null;
            Type type = target.GetType();
            while (type != null)
            {
                FieldInfo field = type.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (field != null)
                    return field.GetValue(target);
                PropertyInfo property = type.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (property != null && property.GetIndexParameters().Length == 0)
                    return property.GetValue(target, null);
                type = type.BaseType;
            }
            return null;
        }
    }
}
