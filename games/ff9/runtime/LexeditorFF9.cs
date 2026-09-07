using Assets.Sources.Scripts.UI.Common;
using FF9;
using Memoria;
using Memoria.Data;
using Memoria.Prime;
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEngine;

namespace Memoria.Scripts.Lexeditor
{
    [AttributeUsage(AttributeTargets.Class, Inherited = false)]
    public sealed class LexeditorBootstrapAttribute : Attribute
    {
        public LexeditorBootstrapAttribute() { LexeditorBootstrap.Install(); }
    }

    [LexeditorBootstrap]
    public sealed class LexeditorRuntimeMarker { }

    internal static class LexeditorBootstrap
    {
        private static Boolean _installed;
        private static LexeditorRuntime _runtime;

        public static void Install()
        {
            if (_installed) return;
            _installed = true;
            // ScriptsLoader instantiates attributes on a worker thread. Only subscribe
            // here; every Unity access happens later from UIKeyTrigger.Update.
            GameLoopManager.Update += OnUpdate;
            GameLoopManager.Quit += OnQuit;
        }

        private static void OnUpdate()
        {
            try
            {
                if (_runtime == null)
                {
                    GameObject host = GameObject.Find("Lexeditor FF9 Runtime");
                    if (host == null)
                    {
                        host = new GameObject("Lexeditor FF9 Runtime");
                        UnityEngine.Object.DontDestroyOnLoad(host);
                    }
                    _runtime = host.GetComponent<LexeditorRuntime>();
                    if (_runtime == null) _runtime = host.AddComponent<LexeditorRuntime>();
                }
                _runtime.GameLoopUpdate();
            }
            catch (Exception ex) { Log.Error(ex, "[LexeditorFF9] Runtime update failed."); }
        }

        private static void OnQuit()
        {
            GameLoopManager.Update -= OnUpdate;
            GameLoopManager.Quit -= OnQuit;
            _runtime = null;
            _installed = false;
        }
    }

    internal static class LexeditorFeatureConfig
    {
        private static String _path;
        private static DateTime _stamp;
        private static Single _nextPoll;
        private static Boolean _improved;
        private static Boolean _betterEat;

        public static Boolean ImprovedInterface { get { Refresh(); return _improved; } }
        public static Boolean BetterEat { get { Refresh(); return _betterEat; } }

        private static void Refresh()
        {
            if (Time.realtimeSinceStartup < _nextPoll) return;
            _nextPoll = Time.realtimeSinceStartup + 1f;
            try
            {
                if (String.IsNullOrEmpty(_path))
                {
                    String root = Path.GetFullPath(Path.Combine(Path.Combine(Application.dataPath, ".."), ".."));
                    _path = Path.Combine(Path.Combine(root, "Lexeditor"), "lexeditor-ff9.ini");
                }
                if (!File.Exists(_path)) { _improved = false; _betterEat = false; return; }
                DateTime stamp = File.GetLastWriteTimeUtc(_path);
                if (stamp == _stamp) return;
                _stamp = stamp;
                Boolean improved = false, betterEat = false;
                foreach (String source in File.ReadAllLines(_path))
                {
                    String line = source.Trim();
                    if (line.Length == 0 || line.StartsWith("#") || line.StartsWith(";") || line.StartsWith("[")) continue;
                    Int32 equals = line.IndexOf('=');
                    if (equals <= 0) continue;
                    String key = line.Substring(0, equals).Trim();
                    String raw = line.Substring(equals + 1).Trim();
                    Boolean value = raw == "1" || raw.Equals("true", StringComparison.OrdinalIgnoreCase) || raw.Equals("yes", StringComparison.OrdinalIgnoreCase);
                    if (key.Equals("ImprovedInterface", StringComparison.OrdinalIgnoreCase)) improved = value;
                    else if (key.Equals("BetterEat", StringComparison.OrdinalIgnoreCase)) betterEat = value;
                }
                _improved = improved;
                _betterEat = betterEat;
            }
            catch (Exception ex)
            {
                Log.Error(ex, "[LexeditorFF9] Feature configuration read failed.");
                _improved = false;
                _betterEat = false;
            }
        }
    }

    public sealed class LexeditorRuntime : MonoBehaviour
    {
        private const String GlowName = "Lexeditor Blue Magic Glow";
        private readonly List<String> _history = new List<String>();
        private readonly Dictionary<Int32, String> _captured = new Dictionary<Int32, String>();
        private readonly Dictionary<UInt16, Single> _queuedAt = new Dictionary<UInt16, Single>();
        private Single _nextFastForward;
        private Boolean _eatFilterActive;
        private FieldInfo _opponentIdField;
        private FieldInfo _commandField;
        private FieldInfo _targetPanelField;

        public void GameLoopUpdate()
        {
            if (LexeditorFeatureConfig.ImprovedInterface)
            {
                UpdateDialogue();
                CaptureDialogue();
            }
            if (LexeditorFeatureConfig.BetterEat)
            {
                UpdateBlueMagicGlows();
                UpdateEatTargets();
            }
            else
            {
                if (_eatFilterActive) RestoreTargets();
                RemoveAllGlows();
            }
        }

        private void UpdateDialogue()
        {
            UIManager managerRoot = PersistenSingleton<UIManager>.Instance;
            DialogManager dialogs = managerRoot != null ? managerRoot.Dialogs : null;
            UIKeyTrigger input = UIManager.Input;
            if (dialogs == null || input == null || dialogs.ActiveDialogList.Count == 0) return;
            Boolean choice = false;
            foreach (Dialog dialog in dialogs.ActiveDialogList)
                if (dialog != null && dialog.IsActive && dialog.HasChoices) choice = true;

            // Circle/Cancel reveals the current text only. It never calls OnKeyConfirm,
            // so it cannot select a choice, hide a dialog, resume ETb, or grant rewards.
            if (!choice && input.GetKeyTrigger(Control.Cancel))
            {
                foreach (Dialog dialog in dialogs.ActiveDialogList)
                    if (dialog != null && dialog.IsActive && dialog.CurrentState == Dialog.State.TextAnimation && dialog.CurrentParser != null)
                    {
                        dialog.CurrentParser.AdvanceProgressToMax();
                        dialog.AfterSentenseShown();
                    }
            }

            // Square/Special fast-forwards non-choice dialogue. Keyboard/controller
            // equivalents come from Memoria's normal binding for Control.Special.
            if (!choice && input.GetKey(Control.Special) && Time.realtimeSinceStartup >= _nextFastForward)
            {
                _nextFastForward = Time.realtimeSinceStartup + 0.08f;
                dialogs.OnKeyConfirm(null);
            }
        }

        private void CaptureDialogue()
        {
            UIManager root = PersistenSingleton<UIManager>.Instance;
            DialogManager dialogs = root != null ? root.Dialogs : null;
            if (dialogs == null) return;
            foreach (Dialog dialog in dialogs.ActiveDialogList)
            {
                if (dialog == null || !dialog.IsActive || dialog.CurrentParser == null || dialog.CurrentState != Dialog.State.CompleteAnimation) continue;
                String text = dialog.CurrentParser.ParsedText;
                if (String.IsNullOrEmpty(text)) continue;
                Int32 id = dialog.GetInstanceID();
                String old;
                if (_captured.TryGetValue(id, out old) && old == text) continue;
                _captured[id] = text;
                _history.Add(StripMarkup(text));
                if (_history.Count > 100) _history.RemoveAt(0);
            }
        }

        private static String StripMarkup(String text)
        {
            System.Text.StringBuilder result = new System.Text.StringBuilder(text.Length);
            Boolean tag = false;
            foreach (Char c in text)
            {
                if (c == '[') { tag = true; continue; }
                if (c == ']' && tag) { tag = false; continue; }
                if (!tag) result.Append(c);
            }
            return result.ToString().Trim();
        }

        private static PLAYER FindQuina()
        {
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
                if (unit != null && unit.IsPlayer && unit.PlayerIndex == CharacterId.Quina) return unit.Player;
            return null;
        }

        private static Boolean CanLearn(BattleUnit target, PLAYER quina, Int32 power)
        {
            if (target == null || target.IsPlayer || !target.IsTargetable || target.CurrentHp == 0 || target.HasCategory(EnemyCategory.Humanoid)) return false;
            if (power <= 0 || target.CurrentHp > target.MaximumHp / (UInt32)power) return false;
            Int32 blue = BattleEnemyPrototype.Find(target).BlueMagicId;
            return quina != null && blue != 0 && !ff9abil.FF9Abil_IsMaster(quina, blue);
        }

        private void UpdateBlueMagicGlows()
        {
            UIManager root = PersistenSingleton<UIManager>.Instance;
            if (root == null || root.State != UIManager.UIState.BattleHUD) { RemoveAllGlows(); return; }
            PLAYER quina = FindQuina();
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
            {
                if (unit == null || unit.Data == null || unit.IsPlayer || unit.Data.gameObject == null) continue;
                Boolean eligible = quina != null && unit.IsTargetable && unit.CurrentHp > 0;
                if (eligible)
                {
                    Int32 blue = BattleEnemyPrototype.Find(unit).BlueMagicId;
                    eligible = blue != 0 && !ff9abil.FF9Abil_IsMaster(quina, blue);
                }
                Transform glow = unit.Data.gameObject.transform.Find(GlowName);
                if (eligible && glow == null)
                {
                    GameObject go = new GameObject(GlowName);
                    go.transform.parent = unit.Data.gameObject.transform;
                    go.transform.localPosition = new Vector3(0f, 200f, 0f);
                    Light light = go.AddComponent<Light>();
                    light.type = LightType.Point;
                    light.color = new Color(0.12f, 0.38f, 1f, 1f);
                    light.intensity = 2f;
                    light.range = 650f;
                }
                else if (!eligible && glow != null) UnityEngine.Object.Destroy(glow.gameObject);
            }
        }

        private void UpdateEatTargets()
        {
            BattleHUD hud = UIManager.Battle;
            if (hud == null || ButtonGroupState.ActiveGroup != BattleHUD.TargetGroupButton) { if (_eatFilterActive) RestoreTargets(); return; }
            if (_commandField == null) _commandField = typeof(BattleHUD).GetField("_currentCommandId", BindingFlags.Instance | BindingFlags.NonPublic);
            if (_targetPanelField == null) _targetPanelField = typeof(BattleHUD).GetField("_targetPanel", BindingFlags.Instance | BindingFlags.NonPublic);
            if (_commandField == null || _targetPanelField == null) return;
            BattleCommandId command = (BattleCommandId)_commandField.GetValue(hud);
            if (command != BattleCommandId.Eat && command != BattleCommandId.Cook) { if (_eatFilterActive) RestoreTargets(); return; }
            Array buttons = GetEntries(_targetPanelField.GetValue(hud), "Enemies");
            if (buttons == null) return;
            PLAYER quina = FindQuina();
            Int32 power = command == BattleCommandId.Cook ? 2 : 4;
            Int32 index = 0;
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
            {
                if (unit == null || unit.Id == 0 || !unit.IsTargetable || unit.IsPlayer) continue;
                if (index >= buttons.Length) break;
                GameObject button = GetGameObject(buttons.GetValue(index++));
                if (button != null) ButtonGroupState.SetButtonEnable(button, CanLearn(unit, quina, power));
            }
            _eatFilterActive = true;
        }

        private void RestoreTargets()
        {
            _eatFilterActive = false;
            BattleHUD hud = UIManager.Battle;
            if (hud == null) return;
            if (_targetPanelField == null) _targetPanelField = typeof(BattleHUD).GetField("_targetPanel", BindingFlags.Instance | BindingFlags.NonPublic);
            if (_targetPanelField == null) return;
            Array buttons = GetEntries(_targetPanelField.GetValue(hud), "Enemies");
            if (buttons == null) return;
            Int32 index = 0;
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
            {
                if (unit == null || unit.Id == 0 || !unit.IsTargetable || unit.IsPlayer) continue;
                if (index >= buttons.Length) break;
                GameObject button = GetGameObject(buttons.GetValue(index++));
                if (button != null) ButtonGroupState.SetButtonEnable(button, unit.CurrentHp > 0);
            }
        }

        private static Array GetEntries(System.Object panel, String name)
        {
            if (panel == null) return null;
            FieldInfo field = panel.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            System.Object table = field != null ? field.GetValue(panel) : null;
            if (table == null) return null;
            Type type = table.GetType();
            while (type != null)
            {
                FieldInfo entries = type.GetField("Entries", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (entries != null) return entries.GetValue(table) as Array;
                type = type.BaseType;
            }
            return null;
        }

        private static GameObject GetGameObject(System.Object wrapper)
        {
            if (wrapper == null) return null;
            Type type = wrapper.GetType();
            while (type != null)
            {
                FieldInfo field = type.GetField("GameObject", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (field != null) return field.GetValue(wrapper) as GameObject;
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
                    if (unit == null || unit.Data == null || unit.Data.gameObject == null) continue;
                    Transform glow = unit.Data.gameObject.transform.Find(GlowName);
                    if (glow != null) UnityEngine.Object.Destroy(glow.gameObject);
                }
            }
            catch { }
        }

        private Int32 OpponentId()
        {
            if (_opponentIdField == null) _opponentIdField = typeof(EMinigame).GetField("quadmistOpponentId", BindingFlags.Static | BindingFlags.NonPublic);
            if (_opponentIdField == null) return 0;
            System.Object value = _opponentIdField.GetValue(null);
            return value is Int32 ? (Int32)value : 0;
        }

        private void OnGUI()
        {
            if (!LexeditorFeatureConfig.ImprovedInterface) return;
            DrawBattleInterface();
            DrawHistory();
            DrawTetraPrompt();
        }

        private void DrawBattleInterface()
        {
            UIManager root = PersistenSingleton<UIManager>.Instance;
            if (root == null || root.State != UIManager.UIState.BattleHUD) return;
            List<BattleUnit> players = new List<BattleUnit>();
            foreach (BattleUnit unit in FF9StateSystem.Battle.FF9Battle.EnumerateBattleUnits())
                if (unit != null && unit.IsPlayer && unit.Id != 0) players.Add(unit);
            if (players.Count == 0) return;
            Single width = Math.Max(560f, Screen.width - 40f), rowH = 40f;
            Single y = Screen.height - rowH * players.Count - 26f, x = 20f;
            Color old = GUI.color; GUI.color = new Color(0f, 0f, 0f, 0.72f);
            GUI.Box(new Rect(x - 6f, y - 5f, width + 12f, rowH * players.Count + 10f), String.Empty); GUI.color = old;
            foreach (BattleUnit unit in players)
            {
                Single top = y; y += rowH;
                GUI.Label(new Rect(x, top, 150f, 20f), unit.Name);
                GUI.Label(new Rect(x, top + 18f, 150f, 20f), "HP " + unit.CurrentHp + "/" + unit.MaximumHp + "   MP " + unit.CurrentMp + "/" + unit.MaximumMp);
                Single barX = x + 160f, barW = width - 166f, hpW = Math.Max(100f, barW * .18f), mpW = Math.Max(80f, barW * .12f), atbW = Math.Max(180f, barW - hpW - mpW - 12f);
                DrawBar(new Rect(barX, top + 2f, hpW, 10f), Ratio(unit.CurrentHp, unit.MaximumHp), new Color(.2f,.85f,.25f,1f));
                DrawBar(new Rect(barX + hpW + 6f, top + 2f, mpW, 10f), Ratio(unit.CurrentMp, unit.MaximumMp), new Color(.2f,.55f,1f,1f));
                if (unit.Data.bi.cmd_idle != 0)
                {
                    Single began; if (!_queuedAt.TryGetValue(unit.Id, out began)) { began = Time.realtimeSinceStartup; _queuedAt[unit.Id] = began; }
                    DrawBarRTL(new Rect(barX, top + 19f, atbW, 13f), 1f - Mathf.Clamp01((Time.realtimeSinceStartup - began) / 1.25f), new Color(1f,.75f,.18f,1f));
                }
                else
                {
                    _queuedAt.Remove(unit.Id);
                    DrawBar(new Rect(barX, top + 19f, atbW, 13f), Ratio((UInt32)Math.Max(0,(Int32)unit.CurrentAtb),(UInt32)Math.Max(1,(Int32)unit.MaximumAtb)), new Color(.25f,.75f,1f,1f));
                }
                if (unit.HasTrance) DrawBar(new Rect(barX + atbW + 6f, top + 19f, Math.Max(60f, barW - atbW - 6f), 13f), unit.Trance / 255f, new Color(1f,.35f,.9f,1f));
            }
        }

        private void DrawHistory()
        {
            UIManager root = PersistenSingleton<UIManager>.Instance;
            DialogManager dialogs = root != null ? root.Dialogs : null;
            if (dialogs == null || dialogs.ActiveDialogList.Count == 0 || UIManager.Input == null || !UIManager.Input.GetKey(Control.LeftTrigger)) return;
            Single width = Math.Min(Screen.width - 80f, 900f), height = Math.Min(Screen.height - 80f, 560f);
            Rect box = new Rect((Screen.width-width)/2f, 40f, width, height);
            Color old = GUI.color; GUI.color = new Color(0f,0f,0f,.9f); GUI.Box(box, String.Empty); GUI.color = old;
            GUI.Label(new Rect(box.x+18f,box.y+12f,box.width-36f,24f), "DIALOGUE HISTORY — hold Left Trigger / keyboard equivalent");
            Int32 first = Math.Max(0, _history.Count - 10); String text = String.Empty;
            for (Int32 i=first;i<_history.Count;i++) text += (text.Length==0?String.Empty:"\n\n") + _history[i];
            GUI.TextArea(new Rect(box.x+18f,box.y+40f,box.width-36f,box.height-56f), text);
        }

        private void DrawTetraPrompt()
        {
            Int32 id = OpponentId();
            if (id <= 0 || FF9StateSystem.Achievement == null || FF9StateSystem.Achievement.QuadmistWinList.Contains(id)) return;
            Color old=GUI.color; GUI.color=new Color(.1f,.45f,1f,.95f); GUI.Box(new Rect(Screen.width-290f,20f,270f,38f),"UNBEATEN CARD OPPONENT"); GUI.color=old;
        }

        private static Single Ratio(UInt32 value, UInt32 max) { return max == 0 ? 0f : Mathf.Clamp01((Single)value/max); }
        private static void DrawBar(Rect rect, Single fraction, Color fill)
        {
            Color old=GUI.color; GUI.color=new Color(0f,0f,0f,.8f); GUI.DrawTexture(rect,Texture2D.whiteTexture); GUI.color=fill;
            GUI.DrawTexture(new Rect(rect.x+1f,rect.y+1f,Math.Max(0f,(rect.width-2f)*Mathf.Clamp01(fraction)),Math.Max(0f,rect.height-2f)),Texture2D.whiteTexture); GUI.color=old;
        }
        private static void DrawBarRTL(Rect rect, Single fraction, Color fill)
        {
            Color old=GUI.color; GUI.color=new Color(0f,0f,0f,.8f); GUI.DrawTexture(rect,Texture2D.whiteTexture);
            Single w=Math.Max(0f,(rect.width-2f)*Mathf.Clamp01(fraction)); GUI.color=fill; GUI.DrawTexture(new Rect(rect.xMax-1f-w,rect.y+1f,w,Math.Max(0f,rect.height-2f)),Texture2D.whiteTexture); GUI.color=old;
        }
    }

    [BattleScript(65)]
    public sealed class BetterEatScript : IBattleScript, IEstimateBattleScript
    {
        private readonly BattleCalculator _v;
        public BetterEatScript(BattleCalculator v) { _v = v; }

        public void Perform()
        {
            if (!_v.Target.CheckUnsafetyOrMiss() || !_v.Target.CanBeAttacked() || _v.Target.HasCategory(EnemyCategory.Humanoid))
            { _v.Context.EatResult=EatResult.CannotEat; UiState.SetBattleFollowFormatMessage(BattleMesages.CannotEat); return; }
            if (_v.Target.CurrentHp > _v.Target.MaximumHp / _v.Command.Power)
            { _v.Context.EatResult=EatResult.Failed; UiState.SetBattleFollowFormatMessage(BattleMesages.CannotEatStrong); return; }
            Int32 blue = BattleEnemyPrototype.Find(_v.Target).BlueMagicId;
            if (LexeditorFeatureConfig.BetterEat && (blue == 0 || ff9abil.FF9Abil_IsMaster(_v.Caster.Player, blue)))
            { _v.Context.EatResult=EatResult.TasteBad; UiState.SetBattleFollowFormatMessage(BattleMesages.TasteBad); return; }
            _v.Target.Kill(_v.Caster);
            if (blue == 0 || ff9abil.FF9Abil_IsMaster(_v.Caster.Player, blue))
            { _v.Context.EatResult=EatResult.TasteBad; UiState.SetBattleFollowFormatMessage(BattleMesages.TasteBad); return; }
            _v.Context.EatResult=EatResult.Yummy; ff9abil.FF9Abil_SetMaster(_v.Caster.Player, blue); BattleState.RaiseAbilitiesAchievement(blue);
            if (ff9abil.IsAbilityActive(blue)) UiState.SetBattleFollowFormatMessage(BattleMesages.Learned, FF9TextTool.ActionAbilityName(ff9abil.GetActiveAbilityFromAbilityId(blue)));
            else UiState.SetBattleFollowFormatMessage(BattleMesages.Learned, FF9TextTool.SupportAbilityName(ff9abil.GetSupportAbilityFromAbilityId(blue)));
        }

        public Single RateTarget()
        {
            if (!_v.Target.CheckUnsafetyOrMiss() || !_v.Target.CanBeAttacked() || _v.Target.HasCategory(EnemyCategory.Humanoid)) return 0f;
            if (_v.Target.CurrentHp > _v.Target.MaximumHp / _v.Command.Power) return 0f;
            Int32 blue = BattleEnemyPrototype.Find(_v.Target).BlueMagicId;
            return blue != 0 && !ff9abil.FF9Abil_IsMaster(_v.Caster.Player, blue) ? 1f : 0f;
        }
    }
}
