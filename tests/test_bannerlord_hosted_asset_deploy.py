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


if __name__ == "__main__":
    unittest.main()
