"""Import title collision regression: shared Saved projects reserve visible names."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from sigma.api import ImportBundleRequest, import_project_bundle


class ProjectImportTitleTests(TestCase):
    def _import(self, visible_titles: list[str], title: str = "TestProject v1"):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            renamed = []
            destinations = []

            def rename(_bundle, candidate):
                renamed.append(candidate)
                return {"renamed_to": candidate}

            def save(_bundle, destination):
                destinations.append(destination)
                return destination

            visible = [
                {"title": name, "available": True, "id": f"shared-{index}"}
                for index, name in enumerate(visible_titles)
            ]
            with (
                patch("sigma.project_bundle.bundle_project_document", return_value={
                    "id": "source-project", "title": title
                }),
                patch("sigma.project_bundle.rename_bundle_project", side_effect=rename),
                patch("sigma.project_bundle.import_independent_bundle", side_effect=save),
                patch("sigma.projects.projects_root", return_value=root),
                patch("sigma.projects._occupied_titles", return_value=set()),
                patch("sigma.recents.recent_projects", return_value={"projects": visible}),
                patch("sigma.recents.record_access"),
                patch("sigma.api.inspect_project", side_effect=lambda path: SimpleNamespace(
                    path=str(path), project=SimpleNamespace(title=renamed[-1] if renamed else title)
                )),
                patch("sigma.api.asdict", side_effect=lambda view: {"title": view.project.title}),
            ):
                result = import_project_bundle(ImportBundleRequest(bundle={"sample": True}))
            return result, renamed, [path.name for path in destinations]

    def test_shared_original_reserves_name_on_import(self):
        result, renamed, paths = self._import(["TestProject v1"])
        self.assertEqual(result["title"], "TestProject v2")
        self.assertEqual(renamed, ["TestProject v2"])
        self.assertEqual(paths, ["testproject-v2.json"])

    def test_import_skips_all_visible_versions(self):
        result, renamed, _ = self._import(["TestProject v1", "TestProject v2"])
        self.assertEqual(result["title"], "TestProject v3")
        self.assertEqual(renamed, ["TestProject v3"])

    def test_import_keeps_title_when_it_is_not_taken(self):
        result, renamed, _ = self._import(["Unrelated shared project"])
        self.assertEqual(result["title"], "TestProject v1")
        self.assertEqual(renamed, [])


if __name__ == "__main__":
    main()
