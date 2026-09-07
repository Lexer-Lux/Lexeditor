using Memoria.Prime;
using System;
using System.IO;
using UnityEngine;

namespace Memoria.Scripts.Lexeditor
{
    [AttributeUsage(AttributeTargets.Class, Inherited = false)]
    public sealed class LexeditorBootstrapAttribute : Attribute
    {
        public LexeditorBootstrapAttribute()
        {
            LexeditorBootstrap.Install();
        }
    }

    [LexeditorBootstrap]
    public sealed class LexeditorRuntimeMarker
    {
    }

    internal static class LexeditorBootstrap
    {
        private static Boolean _installed;
        private static LexeditorRuntime _runtime;

        public static void Install()
        {
            if (_installed)
                return;
            _installed = true;
            // ScriptsLoader scans attributes on a worker thread. Do not touch Unity
            // objects here; GameLoopManager.Update is raised from UIKeyTrigger.Update.
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
                    if (_runtime == null)
                        _runtime = host.AddComponent<LexeditorRuntime>();
                }
                _runtime.GameLoopUpdate();
            }
            catch (Exception ex)
            {
                Log.Error(ex, "[LexeditorFF9] Runtime update failed.");
            }
        }

        private static void OnQuit()
        {
            GameLoopManager.Update -= OnUpdate;
            GameLoopManager.Quit -= OnQuit;
            _installed = false;
            _runtime = null;
        }
    }

    internal static class LexeditorFeatureConfig
    {
        private static String _path;
        private static DateTime _lastWriteUtc;
        private static Single _nextPoll;
        private static Boolean _improvedInterface;
        private static Boolean _betterEat;

        public static Boolean ImprovedInterface
        {
            get { Refresh(); return _improvedInterface; }
        }

        public static Boolean BetterEat
        {
            get { Refresh(); return _betterEat; }
        }

        private static void Refresh()
        {
            if (Time.realtimeSinceStartup < _nextPoll)
                return;
            _nextPoll = Time.realtimeSinceStartup + 1.0f;
            try
            {
                if (String.IsNullOrEmpty(_path))
                {
                    String gameRoot = Path.GetFullPath(Path.Combine(Path.Combine(Application.dataPath, ".."), ".."));
                    _path = Path.Combine(Path.Combine(gameRoot, "Lexeditor"), "lexeditor-ff9.ini");
                }
                if (!File.Exists(_path))
                {
                    _improvedInterface = false;
                    _betterEat = false;
                    return;
                }
                DateTime stamp = File.GetLastWriteTimeUtc(_path);
                if (stamp == _lastWriteUtc)
                    return;
                _lastWriteUtc = stamp;
                Boolean improved = false;
                Boolean eat = false;
                foreach (String sourceLine in File.ReadAllLines(_path))
                {
                    String line = sourceLine.Trim();
                    if (line.Length == 0 || line.StartsWith("#") || line.StartsWith(";") || line.StartsWith("["))
                        continue;
                    Int32 equals = line.IndexOf('=');
                    if (equals <= 0)
                        continue;
                    String key = line.Substring(0, equals).Trim();
                    String value = line.Substring(equals + 1).Trim();
                    Boolean enabled = value == "1" || value.Equals("true", StringComparison.OrdinalIgnoreCase) || value.Equals("yes", StringComparison.OrdinalIgnoreCase);
                    if (key.Equals("ImprovedInterface", StringComparison.OrdinalIgnoreCase))
                        improved = enabled;
                    else if (key.Equals("BetterEat", StringComparison.OrdinalIgnoreCase))
                        eat = enabled;
                }
                _improvedInterface = improved;
                _betterEat = eat;
            }
            catch (Exception ex)
            {
                Log.Error(ex, "[LexeditorFF9] Could not read feature configuration.");
                _improvedInterface = false;
                _betterEat = false;
            }
        }
    }
}
