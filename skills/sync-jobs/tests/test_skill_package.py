import json
from pathlib import Path
import re
import unittest

SKILL=Path(__file__).resolve().parents[1]


class SkillPackage(unittest.TestCase):
    def test_trigger_and_version_cover_source_neutral_acquisition(self):
        text=(SKILL/"SKILL.md").read_text()
        front=text.split("---",2)[1]
        for term in ("LinkedIn","employer","ATS","Indeed","job-board","owner-selected"):
            self.assertIn(term,front)
        self.assertIn('version: "2.4.0"',front)

    def test_skill_references_are_discoverable_and_exist(self):
        text=(SKILL/"SKILL.md").read_text()
        links=re.findall(r"\]\((references/[^)]+)\)",text)
        self.assertIn("references/source_acquisition.md",links)
        for link in links:
            self.assertTrue((SKILL/link).is_file(),link)

    def test_public_package_contains_only_a_synthetic_profile(self):
        profiles=sorted(path.name for path in (SKILL/"profiles").iterdir() if path.is_dir())
        self.assertEqual(profiles,["example"])
        profile=json.loads((SKILL/"profiles/example/profile.json").read_text())
        self.assertEqual(profile["id"],"example")
        self.assertTrue(profile["synthetic_fixture"])
        self.assertNotIn("preferences",profile)

    def test_private_profile_markers_and_local_paths_are_absent(self):
        text="\n".join(
            path.read_text(errors="ignore")
            for path in SKILL.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix!=".pyc"
        ).casefold()
        private_name="".join(chr(value) for value in (98,101,110,106,97,109,105,110))
        private_name_accented="".join(chr(value) for value in (98,101,110,106,97,109,237,110))
        for forbidden in (
            private_name, private_name_accented, "profiles/"+private_name,
            "/"+"users/", "/"+"volumes/", "candidate"+"_facts.md",
            "personal"+"_preferences.md", "target"+"_tracks.md",
            "reconciliation"+"_sources.json", "multi"+"plica",
            "wel"+"tio", "bb"+"va",
        ):
            self.assertNotIn(forbidden,text)

    def test_runtime_has_no_retired_pipeline_or_scraper_dependency(self):
        modules=[]
        for path in (SKILL/"scripts").glob("*.py"):
            modules.extend(line for line in path.read_text(errors="ignore").splitlines() if re.match(r"\s*(?:from|import)\s",line))
        imports="\n".join(modules)
        for forbidden in ("prompts", "apply_pipeline", "JobSpy", "jobspy", "linkedin_api"):
            self.assertNotIn(forbidden,imports)
        acquisition=(SKILL/"scripts/source_acquisition.py").read_text()
        self.assertNotIn("/"+"Volumes/",acquisition)
        self.assertEqual((SKILL/"requirements.txt").read_text().strip(),"openpyxl==3.1.5")
        scripts="\n".join(
            path.read_text(errors="ignore")
            for path in (SKILL/"scripts").glob("*")
            if path.is_file()
        )
        for forbidden in ("document.cookie", "/voyager/api/", "voyagerSearchDashClusters"):
            self.assertNotIn(forbidden,scripts)

    def test_source_acquisition_reference_routes_provider_details(self):
        source=(SKILL/"references/source_acquisition.md").read_text()
        self.assertIn("providers/public_ats.md",source)
        self.assertTrue((SKILL/"references/providers/public_ats.md").is_file())


if __name__=="__main__":
    unittest.main()
