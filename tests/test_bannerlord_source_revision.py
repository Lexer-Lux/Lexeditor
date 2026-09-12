from pathlib import Path
import tempfile
import unittest

from games.bannerlord.source_revision import attach_source_revision, require_source_revision, source_revision


class BannerlordSourceRevisionTests(unittest.TestCase):
    def test_revision_is_exact_file_bytes_and_rejects_stale_save(self):
        with tempfile.TemporaryDirectory() as name:
            source=Path(name)/"source.cs"
            source.write_bytes(b"before\r\n")
            token=source_revision(source)
            self.assertEqual(len(token),64)
            require_source_revision(source,token)
            source.write_bytes(b"after\n")
            with self.assertRaisesRegex(ValueError,"changed on disk"):
                require_source_revision(source,token)

    def test_missing_revision_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            source=Path(name)/"source.cs";source.write_text("x",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"loaded source revision"):
                require_source_revision(source,"")

    def test_attach_revision_uses_payload_path(self):
        with tempfile.TemporaryDirectory() as name:
            source=Path(name)/"source.cs";source.write_text("x",encoding="utf-8")
            payload=attach_source_revision({"path":str(source),"available":True})
            self.assertEqual(payload["sourceHash"],source_revision(source))

    def test_frontend_sends_saved_revision_for_every_structured_source(self):
        root=Path(__file__).resolve().parents[1]/"games"/"bannerlord"
        core=(root/"editor_core.js").read_text(encoding="utf-8")
        boot=(root/"editor_boot.js").read_text(encoding="utf-8")
        self.assertIn('sourceHash:baseline?.sourceHash||""',core)
        for token in (
            'sourceHash:state.savedProject.projectFile?.sourceHash||""',
            'sourceHash:state.savedSkills.sourceHash||""',
            'sourceHash:state.savedEffects.sourceHash||""',
            'sourceHash:state.savedPerks.sourceHash||""',
            'sourceHash:state.savedXpSources.sourceHash||""',
            'sourceHash:state.savedMcmDefaults.sourceHash||""',
        ):
            self.assertIn(token,boot)


if __name__ == "__main__":
    unittest.main()
