from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.terraria.localization import parse_localization_text
from games.terraria.source_text import source_file_state
from games.terraria.structured_content import create_structured_content, default_values, render_structured_source, update_structured_content, validate_values


class TerrariaStructuredSystemsTests(unittest.TestCase):
    def test_rarity_color(self):
        source=render_structured_source("ExampleMod","rarity","Electric",{"colorR":12,"colorG":200,"colorB":240})
        self.assertIn("public sealed class Electric : ModRarity",source)
        self.assertIn("RarityColor => new Color(12, 200, 240)",source)

    def test_biome_is_disabled_by_default_and_generates_safe_conditions(self):
        source=render_structured_source("ExampleMod","biome","StormForest",{})
        self.assertIn("IsBiomeActive(Player player) => false;",source)
        values=default_values("biome")
        values.update({"enabled":True,"zone":"Jungle","depth":"Overworld","time":"Night","hardmode":"Hardmode","rain":"Raining","music":42,"priority":"BiomeMedium","torchItemType":8,"campfireItemType":9,"backgroundColorEnabled":True,"backgroundR":10,"backgroundG":20,"backgroundB":30})
        source=render_structured_source("ExampleMod","biome","StormForest",values)
        self.assertIn("Music => 42;",source)
        self.assertIn("SceneEffectPriority.BiomeMedium",source)
        self.assertIn("player.ZoneJungle",source)
        self.assertIn("player.ZoneOverworldHeight",source)
        self.assertIn("!Main.dayTime",source)
        self.assertIn("Main.hardMode",source)
        self.assertIn("Main.raining",source)
        self.assertIn("AdditionalCondition(player)",source)
        self.assertIn("private bool AdditionalCondition(Player player) => true;",source)

    def test_biome_creation_writes_icon_background_and_display_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"ExampleMod"; root.mkdir()
            result=create_structured_content(root,"biome","StormForest",{},"Storm Forest","")
            self.assertIsNone(result["texture"])
            self.assertEqual({asset["path"] for asset in result["assets"]},{"Content/Biomes/StormForest_Icon.png","Content/Biomes/StormForest_Background.png"})
            self.assertEqual((root/"Content/Biomes/StormForest_Icon.png").read_bytes()[16:20],(30).to_bytes(4,"big"))
            values={entry.key:entry.value for entry in parse_localization_text((root/"Localization/en-US.hjson").read_text(encoding="utf-8")).entries}
            self.assertEqual(values["Mods.ExampleMod.Biomes.StormForest.DisplayName"],"Storm Forest")

    def test_config_typed_field_dsl(self):
        values={"scope":"ServerSide","reloadRequired":True,"fields":"bool:EnableFeature=true\nint:Count=5\nfloat:Scale=1.25\nstring:Greeting=Howdy"}
        source=render_structured_source("ExampleMod","config","GameplayConfig",values)
        self.assertIn("public sealed class GameplayConfig : ModConfig",source)
        self.assertIn("ConfigScope.ServerSide",source)
        self.assertEqual(source.count("[ReloadRequired]"),4)
        self.assertIn("[DefaultValue(true)]",source)
        self.assertIn("public int Count { get; set; } = 5;",source)
        self.assertIn("public float Scale { get; set; } = 1.25f;",source)
        self.assertIn('public string Greeting { get; set; } = "Howdy";',source)
        with self.assertRaisesRegex(ValueError,"duplicated"):
            validate_values("config",{"fields":"bool:Same=true\nint:Same=2"})
        with self.assertRaisesRegex(ValueError,"type must be"):
            validate_values("config",{"fields":"vector:Position=1"})

    def test_command_safe_metadata_and_preserved_custom_hook(self):
        values={"command":"hello","commandType":"World","caseSensitive":True,"usage":"/hello [name]","description":"Say hello","replyText":"Hello!","echoArguments":True}
        source=render_structured_source("ExampleMod","command","HelloCommand",values)
        self.assertIn('Command => "hello";',source)
        self.assertIn("CommandType.World",source)
        self.assertIn('Usage => "/hello [name]";',source)
        self.assertIn('caller.Reply("Hello!");',source)
        self.assertIn('caller.Reply(string.Join(" ", args));',source)
        self.assertIn("CustomAction(caller, input, args);",source)
        self.assertIn("private void CustomAction",source)
        with self.assertRaisesRegex(ValueError,"omit the slash"):
            validate_values("command",{"command":"/bad command"})

    def test_command_custom_hook_survives_structured_save(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"ExampleMod"; root.mkdir()
            created=create_structured_content(root,"command","PingCommand",{"command":"ping","replyText":"pong"})
            state=source_file_state(root,created["path"])
            customized=state["text"].replace("    {\n    }\n}","    {\n        caller.Reply(\"custom\");\n    }\n}")
            (root/created["path"]).write_text(customized,encoding="utf-8")
            external=source_file_state(root,created["path"])
            values=dict(created["values"]); values["replyText"]="PONG"
            update_structured_content(root,created["path"],values,external["sha256"])
            final=source_file_state(root,created["path"])["text"]
            self.assertIn('caller.Reply("PONG");',final)
            self.assertIn('caller.Reply("custom");',final)


if __name__ == "__main__":
    unittest.main()
