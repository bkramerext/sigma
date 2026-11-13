"""Curated sample promotion: Git isolation, attribution and full evidence copies."""

import hashlib
import json
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sigma import project_bundle, projects, recents, samples
from sigma.project_copy import _canonical
from sigma.sample_promotion import promote_bundle


class CuratedSamplePromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sigma-curated-sample-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = self.root / "samples"
        self.projects = self.root / "projects"
        self.state = self.root / "state"
        for path in (self.catalog, self.projects, self.state):
            path.mkdir()
        for target, key, value in (
            (samples, "SAMPLES", self.catalog),
            (samples, "projects_root", lambda: self.projects),
            (projects, "projects_root", lambda: self.projects),
            (recents, "state_directory", lambda: self.state),
        ):
            patcher = patch.object(target, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.git("init", "-q")
        self.git("config", "user.name", "SIGMA fixture")
        self.git("config", "user.email", "fixture@example.test")
        (self.root / "README").write_text("baseline\n")
        self.git("add", "README")
        self.git("commit", "-qm", "Baseline")

        self.source = self.projects / "fixture.sigma"
        view = projects.initialize_project(self.source, "Curated Research v12", "Research subject")
        self.source_id = view.project.id
        self.session_id = str(uuid4())
        self.paper_id = uuid4().hex
        session = {
            "id": self.session_id,
            "project_id": self.source_id,
            "project_path": str(self.source),
            "status": "complete",
            "session_number": 1,
            "created_by": "sample.author@gmail.com",
            "model": "gpt-6.1-sol",
            "reasoning_effort": "high",
            "steps": [],
            "artifacts": [],
            "events": [],
        }
        sessions = self.source / "research-sessions"
        sessions.mkdir()
        (sessions / f"{self.session_id}.json").write_text(json.dumps(session))
        pdf = (Path(__file__).parent / "fixtures" / "sigma-valid-sample-paper.pdf").read_bytes()
        tex = (Path(__file__).parent / "fixtures" / "sigma-valid-sample-paper.tex").read_text()
        frozen = {
            "schema": "sigma-paper-evidence-v2",
            "project_id": self.source_id,
            "created_by": "sample.author@gmail.com",
            "session_id": self.session_id,
            "source": "Research methods and results",
        }
        digest = hashlib.sha256(_canonical(frozen)).hexdigest()
        paper_dir = self.source / "papers"
        paper_dir.mkdir()
        archive = paper_dir / ".snapshots"
        archive.mkdir()
        (archive / f"{digest}.json.zlib").write_bytes(zlib.compress(_canonical(frozen)))
        record = {
            "paper_id": self.paper_id,
            "project_id": self.source_id,
            "created_by": "sample.author@gmail.com",
            "research_session_id": self.session_id,
            "draft": {"title": "Curated research result"},
            "paper_version": 1,
            "created_at": "2026-11-13T18:00:00+00:00",
            "snapshot_sha256": digest,
            "snapshot_ref": digest,
            "tex_source": tex,
            "tex_sha256": hashlib.sha256(tex.encode()).hexdigest(),
            "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
            "pdf_size_bytes": len(pdf),
            "generation": {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
        }
        (paper_dir / f"{self.paper_id}.json").write_text(json.dumps(record))
        (paper_dir / f"{self.paper_id}.pdf").write_bytes(pdf)
        self.input = self.root / "source.bundle.json"
        self.input.write_bytes(project_bundle.encode(self.source))

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    def test_promote_replaces_matching_sample_and_commits_only_sample_files(self):
        source_before = self.input.read_bytes()
        (self.root / "unrelated.txt").write_text("Unrelated staged work\n")
        self.git("add", "unrelated.txt")

        result = promote_bundle(self.input)
        self.assertEqual(result["sample"], "curated-research")
        self.assertEqual(result["title"], "Curated Research")
        self.assertEqual(result["paper_count"], 1)
        self.assertEqual(result["session_count"], 1)
        self.assertEqual(self.input.read_bytes(), source_before)
        changed = self.git("show", "--pretty=format:", "--name-only", "HEAD").splitlines()
        self.assertEqual(
            set(changed),
            {
                "samples/curated-research/project.json",
                "samples/curated-research/sample-curation.json",
                "samples/curated-research/sample-snapshot.json",
            },
        )
        self.assertIn("unrelated.txt", self.git("diff", "--cached", "--name-only"))

        catalog = samples.sample_projects()["projects"]
        self.assertEqual(len(catalog), 1)
        self.assertTrue(catalog[0]["curated"])
        self.assertEqual(catalog[0]["featured_paper_id"], self.paper_id)
        self.assertIsNone(catalog[0]["best_paper_score"])
        first = samples.open_sample_project("curated-research")
        second = samples.open_sample_project("curated-research")
        self.assertEqual(first.project.title, "Curated Research v1")
        self.assertEqual(second.project.title, "Curated Research v2")
        self.assertNotEqual(first.project.id, second.project.id)
        self.assertTrue(first.path.endswith(".json"))

        for copied in (first, second):
            data = project_bundle._decode(json.loads(Path(copied.path).read_text()))
            stored = json.loads(data[f"artifacts/papers/{self.paper_id}.json"])
            self.assertEqual(data[f"artifacts/papers/{self.paper_id}.pdf"],
                             (self.source / "papers" / f"{self.paper_id}.pdf").read_bytes())
            self.assertEqual(stored["created_by"], "")
            self.assertEqual(stored["generation"]["model"], "gpt-6.1-sol")
            self.assertNotEqual(stored["project_id"], self.source_id)
            self.assertNotEqual(stored["research_session_id"], self.session_id)
            new_digest = stored["snapshot_ref"]
            self.assertNotEqual(new_digest, hashlib.sha256(
                _canonical({"schema": "sigma-paper-evidence-v2",
                            "project_id": self.source_id,
                            "created_by": "sample.author@gmail.com",
                            "session_id": self.session_id,
                            "source": "Research methods and results"})
            ).hexdigest())
            frozen = json.loads(zlib.decompress(
                data[f"artifacts/papers/snapshots/{new_digest}.json.zlib"]
            ))
            self.assertEqual(frozen["project_id"], copied.project.id)
            self.assertEqual(frozen["created_by"], "")
            self.assertNotIn("sample.author@gmail.com", json.dumps(frozen))
            sessions = [
                json.loads(blob)
                for name, blob in data.items()
                if name.startswith("research-sessions/")
                and name.endswith(".json")
                and name not in {"research-sessions/limits.json",
                                 "research-sessions/sequence.json"}
            ]
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["created_by"], "")
            self.assertEqual(sessions[0]["model"], "gpt-6.1-sol")

        # Replacing a sample uses its existing catalog identity and a new commit.
        self.assertEqual(promote_bundle(self.input)["sample"], "curated-research")
        self.assertEqual(len(samples.sample_projects()["projects"]), 1)
        self.assertEqual(
            self.git("show", "--pretty=format:", "--name-only", "HEAD").splitlines(),
            ["samples/curated-research/project.json", "samples/curated-research/sample-snapshot.json"],
        )

    def test_dirty_target_is_refused_without_touching_it(self):
        promote_bundle(self.input)
        target = self.catalog / "curated-research" / "project.json"
        target.write_text(target.read_text() + "\n")
        before = target.read_bytes()
        with self.assertRaisesRegex(projects.ProjectError, "uncommitted changes"):
            promote_bundle(self.input)
        self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
