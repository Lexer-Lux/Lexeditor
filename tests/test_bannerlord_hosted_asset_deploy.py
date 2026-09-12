from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from games.bannerlord import paths


class BannerlordHostedAssetDeployTests(unittest.TestCase):
    def test_packaged_asset_copy_target_is_suppressed_only_for_hosted_builds(self):
        template = paths.PLUGIN_ROOT / "template" / "BannerlordModule.csproj"
        root = ET.parse(template).getroot()
        target = next(
            child for child in root
            if child.tag.rsplit("}", 1)[-1] == "Target"
            and child.attrib.get("Name") == "CopyModuleFiles"
        )
        condition = target.attrib.get("Condition", "")
        self.assertIn("LexeditorSkipAssetDeploy", condition)
        self.assertIn("!= 'true'", condition)
        tasks = [child.tag.rsplit("}", 1)[-1] for child in target]
        self.assertIn("Copy", tasks)

        # The template does not set the hosted-only flag itself. Therefore a
        # normal external `dotnet build` sees the condition as true and keeps
        # the template's existing asset-copy behavior.
        properties = {
            child.tag.rsplit("}", 1)[-1]
            for group in root
            if group.tag.rsplit("}", 1)[-1] == "PropertyGroup"
            for child in group
        }
        self.assertNotIn("LexeditorSkipAssetDeploy", properties)


if __name__ == "__main__":
    unittest.main()
