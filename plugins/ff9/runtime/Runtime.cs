using FF9;
using Memoria;
using Memoria.Data;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace Memoria.Scripts.Lexeditor
{
    public sealed class LexeditorRuntime : MonoBehaviour
    {
        private const String GlowName = "Lexeditor Blue Magic Glow";
        private readonly List<String> _history = new List<String>();
        private readonly Dictionary<Int32, String> _capturedDialogText = new Dictionary<Int32, String>();
        private readonly Dictionary<UInt16, Single> _queuedAt = new Dictionary<UInt16, Single>();
        private Single _nextFastForward;
        private Boolean _targetFilterWasActive;
        private readonly Dictionary<BTL_DATA, Single> _rowExtraZ = new Dictionary<BTL_DATA, Single>();
        private readonly Dictionary<Int32, Byte> _menuRows = new Dictionary<Int32, Byte>();
        private Boolean _menuRowsInitialized;
        private Boolean _frontCollapseLatched;
        private MethodInfo _displayCharacterMethod;
        private FieldInfo _opponentIdField;
        private FieldInfo _currentCommandIdField;
        private FieldInfo _targetPanelField;

        public void GameLoopUpdate()
        {
            Boolean improvedInterface = LexeditorFeatureConfig.ImprovedInterface;
            Boolean betterEat = LexeditorFeatureConfig.BetterEat;
            Boolean rowRework = LexeditorFeatureConfig.RowRework;
            if (!improvedInterface && !betterEat && !rowRework)
            {
                if (_targetFilterWasActive)
                    RestoreTargetButtons();
                RemoveAllGlows();
                ResetRowRework();
                return;
            }
            if (improvedInterface)
            {
                UpdateDialogueControls();
                CaptureDialogueHistory();
            }
            if (betterEat)
                UpdateBlueMagicGlows();
            else
                RemoveAllGlows();
            if (betterEat || rowRework)
                UpdateTargetAvailability();
            else if (_targetFilterWasActive)
                RestoreTargetButtons();
            if (rowRework)
                UpdateRowRework();
            else
                ResetRowRework();
        }

        private void UpdateDialogueControls()
        {
            DialogManager manager = PersistenSingleton<UIManager>.Instance != null ? PersistenSingleton<UIManager>.Instance.Dialogs : null;
            UIKeyTrigger input = UIManager.Input;
            if (manager == null || input == null || manager.ActiveDialogList.Count == 0)
                return;
            Boolean hasChoice = false;
            foreach (Dialog dialog in manager.ActiveDialogList)
                if (dialog != null && dialog.IsActive && dialog.HasChoices)
                    hasChoice = true;
            if (input.GetKeyTrigger(Control.Cancel) && !hasChoice)
            {
                foreach (Dialog dialog in manager.ActiveDialogList)
                {
                    if (dialog != null && dialog.IsActive && dialog.CurrentState == Dialog.State.TextAnimation)
                    {
                        dialog.CurrentParser.AdvanceProgressToMax();
                        dialog.AfterSentenseShown();
                    }
                }
            }
            // Special = Square/B by default. Holding it advances only non-choice
            // dialogue; choices are never confirmed by the fast-forward path.
            if (!hasChoice && input.GetKey(Control.Special) && Time.realtimeSinceStartup >= _nextFastForward)
            {
                _nextFastForward = Time.realtimeSinceStartup + 0.08f;
                manager.OnKeyConfirm(null);
            }
        }

        private void CaptureDialogueHistory()
        {
            DialogManager manager = PersistenSingleton<UIManager>.Instance != null ? PersistenSingleton<UIManager>.Instance.Dialogs : null;
            if (manager == null)
                return;
            foreach (Dialog dialog in manager.ActiveDialogList)
            {
                if (dialog == null || !dialog.IsActive || dialog.CurrentParser == null || dialog.CurrentState != Dialog.State.CompleteAnimation)
                    continue;
                String text = dialog.CurrentParser.ParsedText;
                if (String.IsNullOrEmpty(text))
                    continue;
                Int32 id = dialog.GetInstanceID();
                String previous;
                if (_capturedDialogText.TryGetValue(id, out previous) && previous == text)
                    continue;
                _capturedDialogText[id] = text;
                _history.Add(StripMarkup(text));
                if (_history.Count > 100)
                    _history.RemoveAt(0);
            }
        }

        private static String StripMarkup(String text)
        {
            // History is a rendered-text snapshot only. Never replay ETb text,
            // callbacks, Hide(), or event scripts.
            if (String.IsNullOrEmpty(text))
                return String.Empty;
            System.Text.StringBuilder sb = new System.Text.StringBuilder(text.Length);
            Boolean tag = false;
            for (Int32 i = 0; i < text.Length; i++)
            {
                Char c = text[i];
                if (c == '[') { tag = true; continue; }
                if (c == ']' && tag) { tag = false; continue; }
                if (!tag) sb.Append(c);
            }
            return sb.ToString().Trim();
        }

        private void UpdateBlueMagicGlows()
        {
            if (PersistenSingleton<UIManager>.Instance == null || PersistenSingleton<UIManager>.Instance.State != UIManager.UIState.BattleHUD)
            {
                RemoveAllGlows();
                return;
            }
            PLAYER quina = FindQuinaPlayer();
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
            {
                if (unit == null || unit.Data == null || unit.IsPlayer || unit.Data.gameObject == null)
                    continue;
                Boolean eligible = quina != null && unit.IsTargetable && unit.CurrentHp > 0;
                if (eligible)
                {
                    Int32 blueMagic = BattleEnemyPrototype.Find(unit).BlueMagicId;
                    eligible = blueMagic != 0 && !ff9abil.FF9Abil_IsMaster(quina, blueMagic);
                }
                Transform existing = unit.Data.gameObject.transform.Find(GlowName);
                if (eligible && existing == null)
                {
                    GameObject glow = new GameObject(GlowName);
                    glow.transform.parent = unit.Data.gameObject.transform;
                    glow.transform.localPosition = new Vector3(0f, 200f, 0f);
                    Light light = glow.AddComponent<Light>();
                    light.type = LightType.Point;
                    light.color = new Color(0.12f, 0.38f, 1.0f, 1.0f);
                    light.intensity = 2.0f;
                    light.range = 650f;
                }
                else if (!eligible && existing != null)
                {
                    UnityEngine.Object.Destroy(existing.gameObject);
                }
            }
        }

        private static PLAYER FindQuinaPlayer()
        {
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
                if (unit != null && unit.IsPlayer && unit.PlayerIndex == CharacterId.Quina)
                    return unit.Player;
            return null;
        }

        private static Boolean CanLearnFrom(BattleUnit target, PLAYER quina, Int32 power)
        {
            if (target == null || target.IsPlayer || !target.IsTargetable || target.CurrentHp == 0 || target.HasCategory(EnemyCategory.Humanoid))
                return false;
            if (power <= 0 || target.CurrentHp > target.MaximumHp / (UInt32)power)
                return false;
            Int32 blueMagic = BattleEnemyPrototype.Find(target).BlueMagicId;
            return quina != null && blueMagic != 0 && !ff9abil.FF9Abil_IsMaster(quina, blueMagic);
        }

        private void UpdateTargetAvailability()
        {
            BattleHUD hud = UIManager.Battle;
            if (hud == null || ButtonGroupState.ActiveGroup != BattleHUD.TargetGroupButton)
            {
                if (_targetFilterWasActive)
                    RestoreTargetButtons();
                return;
            }
            if (_currentCommandIdField == null)
                _currentCommandIdField = typeof(BattleHUD).GetField("_currentCommandId", BindingFlags.Instance | BindingFlags.NonPublic);
            if (_targetPanelField == null)
                _targetPanelField = typeof(BattleHUD).GetField("_targetPanel", BindingFlags.Instance | BindingFlags.NonPublic);
            if (_currentCommandIdField == null || _targetPanelField == null)
                return;
            BattleCommandId command = (BattleCommandId)_currentCommandIdField.GetValue(hud);
            System.Object panel = _targetPanelField.GetValue(hud);
            Array buttons = GetEntries(panel, "Enemies");
            if (buttons == null)
                return;

            if (LexeditorFeatureConfig.RowRework && command == BattleCommandId.Attack)
            {
                BattleUnit caster = CurrentPlayerUnit(hud);
                if (caster != null && caster.Row == 0 && !caster.HasLongRangeWeapon)
                {
                    for (Int32 i = 0; i < buttons.Length; i++)
                    {
                        GameObject go = GetGameObject(buttons.GetValue(i));
                        if (go != null)
                            ButtonGroupState.SetButtonEnable(go, false);
                    }
                    _targetFilterWasActive = true;
                    return;
                }
            }

            if (LexeditorFeatureConfig.BetterEat && (command == BattleCommandId.Eat || command == BattleCommandId.Cook))
            {
                PLAYER quina = FindQuinaPlayer();
                Int32 power = command == BattleCommandId.Cook ? 2 : 4;
                Int32 enemyIndex = 0;
                foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
                {
                    if (unit == null || unit.Id == 0 || !unit.IsTargetable || unit.IsPlayer)
                        continue;
                    if (enemyIndex >= buttons.Length)
                        break;
                    GameObject go = GetGameObject(buttons.GetValue(enemyIndex));
                    if (go != null)
                        ButtonGroupState.SetButtonEnable(go, CanLearnFrom(unit, quina, power));
                    enemyIndex++;
                }
                _targetFilterWasActive = true;
                return;
            }

            if (_targetFilterWasActive)
                RestoreTargetButtons();
        }

        private static BattleUnit CurrentPlayerUnit(BattleHUD hud)
        {
            if (hud == null || hud.CurrentPlayerIndex < 0 || hud.CurrentPlayerIndex > 15)
                return null;
            UInt16 id = (UInt16)(1 << hud.CurrentPlayerIndex);
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
                if (unit != null && unit.IsPlayer && unit.Id == id)
                    return unit;
            return null;
        }

        private void RestoreTargetButtons()
        {
            _targetFilterWasActive = false;
            BattleHUD hud = UIManager.Battle;
            if (hud == null)
                return;
            if (_targetPanelField == null)
                _targetPanelField = typeof(BattleHUD).GetField("_targetPanel", BindingFlags.Instance | BindingFlags.NonPublic);
            if (_targetPanelField == null)
                return;
            System.Object panel = _targetPanelField.GetValue(hud);
            Array buttons = GetEntries(panel, "Enemies");
            if (buttons == null)
                return;
            Int32 enemyIndex = 0;
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
            {
                if (unit == null || unit.Id == 0 || !unit.IsTargetable || unit.IsPlayer)
                    continue;
                if (enemyIndex >= buttons.Length)
                    break;
                GameObject go = GetGameObject(buttons.GetValue(enemyIndex));
                if (go != null)
                    ButtonGroupState.SetButtonEnable(go, unit.CurrentHp > 0);
                enemyIndex++;
            }
        }

        private void UpdateRowRework()
        {
            UpdateMenuFormationRule();
            UpdateBattleRows();
        }

        private void ResetRowRework()
        {
            _menuRows.Clear();
            _menuRowsInitialized = false;
            _frontCollapseLatched = false;
            UIManager manager = PersistenSingleton<UIManager>.Instance;
            if (manager == null || manager.UnityScene != UIManager.Scene.Battle)
            {
                _rowExtraZ.Clear();
                return;
            }
            List<BattleUnit> players = PlayerBattleUnits();
            ApplyBackRowSpacing(players, false);
        }

        private void UpdateMenuFormationRule()
        {
            UIManager manager = PersistenSingleton<UIManager>.Instance;
            if (manager == null || manager.State != UIManager.UIState.MainMenu)
            {
                _menuRows.Clear();
                _menuRowsInitialized = false;
                return;
            }
            PLAYER[] members = FF9StateSystem.Common.FF9.party.member;
            List<PLAYER> party = new List<PLAYER>();
            for (Int32 i = 0; i < members.Length; i++)
                if (members[i] != null)
                    party.Add(members[i]);
            if (party.Count == 0)
                return;

            if (!_menuRowsInitialized)
            {
                _menuRowsInitialized = true;
                if (AllPartyMembersBack(party))
                {
                    party[0].info.row = 1;
                    RejectAllBackFormation(manager.MainMenuScene);
                }
                SnapshotMenuRows(party);
                return;
            }

            if (AllPartyMembersBack(party))
            {
                PLAYER changed = null;
                for (Int32 i = 0; i < party.Count; i++)
                {
                    Byte previous;
                    Int32 key = (Int32)party[i].info.slot_no;
                    if (_menuRows.TryGetValue(key, out previous) && previous == 1 && party[i].info.row == 0)
                    {
                        changed = party[i];
                        break;
                    }
                }
                (changed ?? party[0]).info.row = 1;
                RejectAllBackFormation(manager.MainMenuScene);
            }
            SnapshotMenuRows(party);
        }

        private static Boolean AllPartyMembersBack(List<PLAYER> party)
        {
            for (Int32 i = 0; i < party.Count; i++)
                if (party[i].info.row != 0)
                    return false;
            return party.Count > 0;
        }

        private void SnapshotMenuRows(List<PLAYER> party)
        {
            _menuRows.Clear();
            for (Int32 i = 0; i < party.Count; i++)
                _menuRows[(Int32)party[i].info.slot_no] = party[i].info.row;
        }

        private void RejectAllBackFormation(MainMenuUI menu)
        {
            FF9Sfx.FF9SFX_Play(102);
            if (menu == null)
                return;
            if (_displayCharacterMethod == null)
                _displayCharacterMethod = typeof(MainMenuUI).GetMethod("DisplayCharacter", BindingFlags.Instance | BindingFlags.NonPublic);
            if (_displayCharacterMethod != null)
                _displayCharacterMethod.Invoke(menu, null);
        }

        private void UpdateBattleRows()
        {
            UIManager manager = PersistenSingleton<UIManager>.Instance;
            if (manager == null || manager.UnityScene != UIManager.Scene.Battle)
            {
                _rowExtraZ.Clear();
                _frontCollapseLatched = false;
                return;
            }
            List<BattleUnit> players = PlayerBattleUnits();
            Boolean anyLiving = false;
            Boolean anyLivingFront = false;
            for (Int32 i = 0; i < players.Count; i++)
            {
                BattleUnit unit = players[i];
                if (unit.CurrentHp == 0)
                    continue;
                anyLiving = true;
                if (unit.Row == 1)
                    anyLivingFront = true;
            }

            if (anyLiving && !anyLivingFront)
            {
                if (!_frontCollapseLatched && UIManager.Battle != null)
                    UIManager.Battle.SetBattleMessage("Your enemies close in!", 3);
                for (Int32 i = 0; i < players.Count; i++)
                {
                    BattleUnit unit = players[i];
                    if (unit.Row == 0)
                        btl_para.SwitchPlayerRow(unit.Data, !btl_util.IsBtlBusy(unit.Data, btl_util.BusyMode.CASTER));
                    if (unit.Player != null)
                        unit.Player.info.row = 1;
                }
                _frontCollapseLatched = true;
            }
            else
            {
                _frontCollapseLatched = false;
            }

            ApplyBackRowSpacing(players, true);
        }

        private static List<BattleUnit> PlayerBattleUnits()
        {
            List<BattleUnit> players = new List<BattleUnit>();
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
                if (unit != null && unit.IsPlayer && unit.Id != 0)
                    players.Add(unit);
            return players;
        }

        private void ApplyBackRowSpacing(List<BattleUnit> players, Boolean doubled)
        {
            HashSet<BTL_DATA> active = new HashSet<BTL_DATA>();
            for (Int32 i = 0; i < players.Count; i++)
            {
                BattleUnit unit = players[i];
                active.Add(unit.Data);
                Single previous;
                if (!_rowExtraZ.TryGetValue(unit.Data, out previous))
                    previous = 0f;
                Single desired = doubled && unit.Row == 0 ? -400f : 0f;
                Single delta = desired - previous;
                if (Mathf.Abs(delta) > 0.01f)
                {
                    unit.Data.base_pos[2] += delta;
                    if (!btl_util.IsBtlBusy(unit.Data, btl_util.BusyMode.CASTER))
                        unit.Data.pos[2] += delta;
                }
                if (desired == 0f)
                    _rowExtraZ.Remove(unit.Data);
                else
                    _rowExtraZ[unit.Data] = desired;
            }
            List<BTL_DATA> stale = new List<BTL_DATA>();
            foreach (BTL_DATA data in _rowExtraZ.Keys)
                if (!active.Contains(data))
                    stale.Add(data);
            for (Int32 i = 0; i < stale.Count; i++)
                _rowExtraZ.Remove(stale[i]);
        }

        private static Array GetEntries(System.Object panel, String fieldName)
        {
            if (panel == null)
                return null;
            FieldInfo tableField = panel.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            System.Object table = tableField != null ? tableField.GetValue(panel) : null;
            if (table == null)
                return null;
            Type type = table.GetType();
            while (type != null)
            {
                FieldInfo entries = type.GetField("Entries", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (entries != null)
                    return entries.GetValue(table) as Array;
                type = type.BaseType;
            }
            return null;
        }

        private static GameObject GetGameObject(System.Object wrapper)
        {
            if (wrapper == null)
                return null;
            Type type = wrapper.GetType();
            while (type != null)
            {
                FieldInfo field = type.GetField("GameObject", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (field != null)
                    return field.GetValue(wrapper) as GameObject;
                type = type.BaseType;
            }
            return null;
        }

        private static void RemoveAllGlows()
        {
            try
            {
                foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
                {
                    if (unit == null || unit.Data == null || unit.Data.gameObject == null)
                        continue;
                    Transform glow = unit.Data.gameObject.transform.Find(GlowName);
                    if (glow != null)
                        UnityEngine.Object.Destroy(glow.gameObject);
                }
            }
            catch { }
        }

        private Int32 CurrentOpponentId()
        {
            if (_opponentIdField == null)
                _opponentIdField = typeof(EMinigame).GetField("quadmistOpponentId", BindingFlags.Static | BindingFlags.NonPublic);
            if (_opponentIdField == null)
                return 0;
            System.Object value = _opponentIdField.GetValue(null);
            return value is Int32 ? (Int32)value : 0;
        }

        private void OnGUI()
        {
            if (!LexeditorFeatureConfig.ImprovedInterface)
                return;
            DrawBattleInterface();
            DrawDialogueHistory();
            DrawTetraPrompt();
        }

        private void DrawBattleInterface()
        {
            if (PersistenSingleton<UIManager>.Instance == null || PersistenSingleton<UIManager>.Instance.State != UIManager.UIState.BattleHUD)
                return;
            List<BattleUnit> players = new List<BattleUnit>();
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
                if (unit != null && unit.IsPlayer && unit.Id != 0)
                    players.Add(unit);
            if (players.Count == 0)
                return;
            Single width = Math.Max(560f, Screen.width - 40f);
            Single rowH = 40f;
            Single totalH = rowH * players.Count + 8f;
            Single x = 20f;
            Single y = Screen.height - totalH - 18f;
            Color oldColor = GUI.color;
            GUI.color = new Color(0f, 0f, 0f, 0.72f);
            GUI.Box(new Rect(x - 6f, y - 5f, width + 12f, totalH + 10f), String.Empty);
            GUI.color = oldColor;
            for (Int32 i = 0; i < players.Count; i++)
            {
                BattleUnit unit = players[i];
                Single top = y + i * rowH;
                GUI.Label(new Rect(x, top, 150f, 20f), unit.Name);
                GUI.Label(new Rect(x, top + 18f, 150f, 20f), "HP " + unit.CurrentHp + "/" + unit.MaximumHp + "   MP " + unit.CurrentMp + "/" + unit.MaximumMp);
                Single barX = x + 160f;
                Single barW = width - 166f;
                Single hpW = Math.Max(100f, barW * 0.18f);
                Single mpW = Math.Max(80f, barW * 0.12f);
                Single atbW = Math.Max(180f, barW - hpW - mpW - 12f);
                DrawBar(new Rect(barX, top + 2f, hpW, 10f), Ratio(unit.CurrentHp, unit.MaximumHp), new Color(0.2f, 0.85f, 0.25f, 1f));
                DrawBar(new Rect(barX + hpW + 6f, top + 2f, mpW, 10f), Ratio(unit.CurrentMp, unit.MaximumMp), new Color(0.2f, 0.55f, 1f, 1f));
                Boolean queued = unit.Data.bi.cmd_idle != 0;
                if (queued)
                {
                    Single began;
                    if (!_queuedAt.TryGetValue(unit.Id, out began))
                    {
                        began = Time.realtimeSinceStartup;
                        _queuedAt[unit.Id] = began;
                    }
                    Single remaining = 1f - Mathf.Clamp01((Time.realtimeSinceStartup - began) / 1.25f);
                    DrawBarRightToLeft(new Rect(barX, top + 19f, atbW, 13f), remaining, new Color(1f, 0.75f, 0.18f, 1f));
                    GUI.Label(new Rect(barX + atbW + 6f, top + 15f, 80f, 20f), "QUEUED");
                }
                else
                {
                    _queuedAt.Remove(unit.Id);
                    DrawBar(new Rect(barX, top + 19f, atbW, 13f), Ratio((UInt32)Math.Max(0, (Int32)unit.CurrentAtb), (UInt32)Math.Max(1, (Int32)unit.MaximumAtb)), new Color(0.25f, 0.75f, 1f, 1f));
                }
                if (unit.HasTrance)
                    DrawBar(new Rect(barX + atbW + 86f, top + 19f, Math.Max(60f, barW - atbW - 86f), 13f), unit.Trance / 255f, new Color(1f, 0.35f, 0.9f, 1f));
            }
        }

        private void DrawDialogueHistory()
        {
            DialogManager manager = PersistenSingleton<UIManager>.Instance != null ? PersistenSingleton<UIManager>.Instance.Dialogs : null;
            if (manager == null || manager.ActiveDialogList.Count == 0 || UIManager.Input == null || !UIManager.Input.GetKey(Control.LeftTrigger))
                return;
            Single width = Math.Min(Screen.width - 80f, 900f);
            Single height = Math.Min(Screen.height - 80f, 560f);
            Rect box = new Rect((Screen.width - width) / 2f, 40f, width, height);
            Color old = GUI.color;
            GUI.color = new Color(0f, 0f, 0f, 0.90f);
            GUI.Box(box, String.Empty);
            GUI.color = old;
            GUI.Label(new Rect(box.x + 18f, box.y + 12f, box.width - 36f, 24f), "DIALOGUE HISTORY — hold Left Trigger / keyboard equivalent");
            Int32 shown = Math.Min(10, _history.Count);
            String text = String.Empty;
            for (Int32 i = _history.Count - shown; i < _history.Count; i++)
                if (i >= 0)
                    text += (text.Length == 0 ? String.Empty : "\n\n") + _history[i];
            GUI.TextArea(new Rect(box.x + 18f, box.y + 40f, box.width - 36f, box.height - 56f), text);
        }

        private void DrawTetraPrompt()
        {
            Int32 opponent = CurrentOpponentId();
            if (opponent <= 0 || FF9StateSystem.Achievement == null || FF9StateSystem.Achievement.QuadmistWinList.Contains(opponent))
                return;
            Color old = GUI.color;
            GUI.color = new Color(0.1f, 0.45f, 1f, 0.95f);
            GUI.Box(new Rect(Screen.width - 290f, 20f, 270f, 38f), "UNBEATEN CARD OPPONENT");
            GUI.color = old;
        }

        private static Single Ratio(UInt32 value, UInt32 maximum)
        {
            if (maximum == 0) return 0f;
            return Mathf.Clamp01((Single)value / maximum);
        }

        private static void DrawBar(Rect rect, Single fraction, Color fill)
        {
            Color old = GUI.color;
            GUI.color = new Color(0f, 0f, 0f, 0.8f);
            GUI.DrawTexture(rect, Texture2D.whiteTexture);
            GUI.color = fill;
            GUI.DrawTexture(new Rect(rect.x + 1f, rect.y + 1f, Math.Max(0f, (rect.width - 2f) * Mathf.Clamp01(fraction)), Math.Max(0f, rect.height - 2f)), Texture2D.whiteTexture);
            GUI.color = old;
        }

        private static void DrawBarRightToLeft(Rect rect, Single fraction, Color fill)
        {
            Color old = GUI.color;
            GUI.color = new Color(0f, 0f, 0f, 0.8f);
            GUI.DrawTexture(rect, Texture2D.whiteTexture);
            Single width = Math.Max(0f, (rect.width - 2f) * Mathf.Clamp01(fraction));
            GUI.color = fill;
            GUI.DrawTexture(new Rect(rect.xMax - 1f - width, rect.y + 1f, width, Math.Max(0f, rect.height - 2f)), Texture2D.whiteTexture);
            GUI.color = old;
        }
    }
}
