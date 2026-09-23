from pathlib import Path
import tempfile
import unittest

from games.bannerlord.project_data import save_project_properties


class BannerlordMsbuildCommentSpanTests(unittest.TestCase):
    def test_commented_property_is_not_edited_instead_of_live_property(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "Mod.csproj"
            path.write_text('''<Project Sdk="Microsoft.NET.Sdk">
  <!-- <OutputPath>commented\\</OutputPath> -->
  <PropertyGroup><OutputPath>live\\</OutputPath></PropertyGroup>
</Project>''', encoding="utf-8")
            save_project_properties(path, {"OutputPath": "changed\\"})
            text = path.read_text(encoding="utf-8")
            self.assertIn('<!-- <OutputPath>commented\\</OutputPath> -->', text)
            self.assertIn('<OutputPath>changed\\</OutputPath>', text)
            self.assertNotIn('<OutputPath>live\\</OutputPath>', text)

    def test_commented_property_group_is_not_used_for_insertion(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "Mod.csproj"
            path.write_text('''<Project Sdk="Microsoft.NET.Sdk">
  <!-- <PropertyGroup><AssemblyName>Fake</AssemblyName></PropertyGroup> -->
  <PropertyGroup><TargetFramework>net472</TargetFramework></PropertyGroup>
</Project>''', encoding="utf-8")
            save_project_properties(path, {"AssemblyName": "Real.Mod"})
            text = path.read_text(encoding="utf-8")
            self.assertIn('<!-- <PropertyGroup><AssemblyName>Fake</AssemblyName></PropertyGroup> -->', text)
            self.assertGreater(text.index('<AssemblyName>Real.Mod</AssemblyName>'), text.index('-->'))

    def test_cdata_tag_like_text_is_ignored(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "Mod.csproj"
            path.write_text('''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><Description><![CDATA[example <OutputPath>fake</OutputPath>]]></Description><OutputPath>live\\</OutputPath></PropertyGroup>
</Project>''', encoding="utf-8")
            save_project_properties(path, {"OutputPath": "changed\\"})
            text = path.read_text(encoding="utf-8")
            self.assertIn('<![CDATA[example <OutputPath>fake</OutputPath>]]>', text)
            self.assertIn('<OutputPath>changed\\</OutputPath>', text)


if __name__ == "__main__":
    unittest.main()
