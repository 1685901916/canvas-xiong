import asyncio
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


class AssetLibraryMigrationCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.library_dir = self.root / "assets" / "library"
        self.library_path = self.data_dir / "asset_library.json"
        self.data_dir.mkdir(parents=True)
        self.library_dir.mkdir(parents=True)
        self.saved_globals = {
            "DATA_DIR": main.DATA_DIR,
            "ASSET_LIBRARY_DIR": main.ASSET_LIBRARY_DIR,
            "ASSET_LIBRARY_PATH": main.ASSET_LIBRARY_PATH,
            "GLOBAL_LOOP": main.GLOBAL_LOOP,
        }
        main.DATA_DIR = str(self.data_dir)
        main.ASSET_LIBRARY_DIR = str(self.library_dir)
        main.ASSET_LIBRARY_PATH = str(self.library_path)
        main.GLOBAL_LOOP = None

    def tearDown(self):
        for name, value in self.saved_globals.items():
            setattr(main, name, value)
        self.temp_dir.cleanup()

    @staticmethod
    def asset_url(relative_path):
        return "/assets/library/" + urllib.parse.quote(relative_path, safe="/")

    @staticmethod
    def make_item(item_id, relative_path, legacy_relative_path="", payload_name="test"):
        item = {
            "id": item_id,
            "name": payload_name,
            "url": AssetLibraryMigrationCompatibilityTests.asset_url(relative_path),
            "kind": "image",
            "created_at": 1,
            "registrations": {},
        }
        if legacy_relative_path:
            item["legacy_flat_url"] = AssetLibraryMigrationCompatibilityTests.asset_url(legacy_relative_path)
        return item

    def write_library(self, items, category_dir=None, category_id="characters"):
        category = {
            "id": category_id,
            "name": "角色",
            "type": "image",
            "items": items,
        }
        if category_dir is not None:
            category["dir"] = category_dir
        workflow = {"id": "workflows", "name": "工作流", "type": "workflow", "items": []}
        self.write_categories([category, workflow])

    def write_categories(self, categories):
        document = {
            "active_library_id": "default",
            "libraries": [{
                "id": "default",
                "name": "默认资产库",
                "type": "asset",
                "categories": categories,
            }],
            "categories": categories,
            "updated_at": 1,
        }
        self.library_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    def read_library(self):
        return json.loads(self.library_path.read_text(encoding="utf-8"))

    def read_items(self):
        return self.read_library()["libraries"][0]["categories"][0]["items"]

    def make_nested_with_alias(self, item_id, filename, payload=b"asset", category="角色"):
        categorized = self.library_dir / category / filename
        alias = self.library_dir / filename
        categorized.parent.mkdir(parents=True, exist_ok=True)
        categorized.write_bytes(payload)
        self.assertTrue(main.ensure_asset_library_compat_file(str(categorized), str(alias)))
        return self.make_item(item_id, f"{category}/{filename}", filename), categorized, alias

    def test_flat_asset_migrates_without_breaking_legacy_url(self):
        filename = "lib_test.png"
        payload = b"asset-bytes"
        legacy_path = self.library_dir / filename
        legacy_path.write_bytes(payload)
        self.write_library([self.make_item("asset_test", filename)])

        main.migrate_asset_library_into_dirs()

        category = self.read_library()["libraries"][0]["categories"][0]
        item = category["items"][0]
        self.assertEqual(category["dir"], "角色")
        self.assertEqual(item["url"], self.asset_url(f"角色/{filename}"))
        self.assertEqual(item["legacy_flat_url"], self.asset_url(filename))
        categorized_path = self.library_dir / "角色" / filename
        self.assertEqual(legacy_path.read_bytes(), payload)
        self.assertEqual(categorized_path.read_bytes(), payload)

        first_document = self.library_path.read_bytes()
        main.migrate_asset_library_into_dirs()
        self.assertEqual(self.library_path.read_bytes(), first_document)
        self.assertEqual(legacy_path.read_bytes(), categorized_path.read_bytes())

    def test_unsafe_category_dir_never_creates_outside_asset_root(self):
        filename = "lib_escape.png"
        (self.library_dir / filename).write_bytes(b"escape")
        outside = self.root / "outside"
        self.write_library([self.make_item("asset_escape", filename)], category_dir="../../outside")

        main.migrate_asset_library_into_dirs()

        self.assertFalse(outside.exists())
        self.assertEqual(self.read_items()[0]["url"], self.asset_url(filename))

    def test_new_asset_rejects_damaged_category_subdir(self):
        source = self.root / "source.png"
        source.write_bytes(b"source")
        outside = self.library_dir.parent / "outside"

        for subdir in ("../outside", " ", "角色 ", "角色.", "NUL"):
            with self.subTest(subdir=subdir):
                with self.assertRaises(main.HTTPException) as raised:
                    main.make_asset_library_item(str(source), "source.png", subdir=subdir)
                self.assertEqual(raised.exception.status_code, 400)
        self.assertFalse(outside.exists())

    def test_create_category_sanitizes_windows_reserved_directory_name(self):
        self.write_library([], category_dir="角色")
        payload = main.AssetLibraryCategoryRequest(name="CON", type="image", library_id="default")

        result = asyncio.run(main.create_asset_library_category(payload))

        category_dir = result["category"]["dir"]
        self.assertNotEqual(category_dir.upper(), "CON")
        self.assertEqual(
            main.asset_library_normalize_relative_path(category_dir, single_component=True),
            category_dir,
        )
        self.assertTrue((self.library_dir / category_dir).is_dir())

    def test_safe_path_rejects_ambiguous_or_absolute_components(self):
        unsafe = [
            "../escape.png",
            "角色/../escape.png",
            "./escape.png",
            "角色//escape.png",
            "/absolute.png",
            "C:/escape.png",
            "角色\\..\\escape.png",
            " ",
            ".. ",
            "角色.",
            "NUL",
            "CON.png",
            "角色/COM1.jpg",
            "COM1 .jpg",
        ]
        for relative_path in unsafe:
            with self.subTest(relative_path=relative_path):
                self.assertEqual(main.asset_library_safe_path(relative_path), "")
        safe = main.asset_library_safe_path("角色/test.png")
        self.assertTrue(safe.startswith(os.path.abspath(main.ASSET_LIBRARY_DIR) + os.sep))
        self.assertEqual(main.asset_library_safe_path("角色/test.png", single_component=True), "")
        self.assertEqual(
            main.asset_library_url_relative_path("/assets/library/%2e%2e/escape.png"),
            "",
        )

    def test_safe_path_rejects_symlink_or_junction_escape(self):
        outside = self.root / "outside"
        outside.mkdir()
        linked = self.library_dir / "linked"
        try:
            os.symlink(outside, linked, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlink unavailable: {exc}")

        self.assertEqual(main.asset_library_safe_path("linked/escape.png"), "")

    def test_asset_url_is_decoded_once_and_preserves_literal_percent_sequence(self):
        filename = "literal%2Fname.png"
        literal_path = self.library_dir / filename
        literal_path.write_bytes(b"literal-percent")
        url = self.asset_url(filename)

        relative = main.asset_library_url_relative_path(url, flat_only=True)

        self.assertEqual(relative, filename)
        self.assertEqual(Path(main.asset_library_safe_path(relative, single_component=True)), literal_path)

    def test_categorized_name_conflict_gets_unique_filename(self):
        filename = "lib_collision.png"
        legacy = self.library_dir / filename
        legacy.write_bytes(b"wanted")
        occupied = self.library_dir / "角色" / filename
        occupied.parent.mkdir(parents=True)
        occupied.write_bytes(b"different")
        self.write_library([self.make_item("asset_collision", filename)], category_dir="角色")

        main.migrate_asset_library_into_dirs()

        item = self.read_items()[0]
        self.assertEqual(item["url"], self.asset_url("角色/lib_collision_2.png"))
        self.assertEqual(item["legacy_flat_url"], self.asset_url(filename))
        self.assertEqual(occupied.read_bytes(), b"different")
        self.assertEqual((self.library_dir / "角色" / "lib_collision_2.png").read_bytes(), b"wanted")
        first_document = self.library_path.read_bytes()
        first_tree = sorted(path.relative_to(self.library_dir) for path in self.library_dir.rglob("*") if path.is_file())
        main.migrate_asset_library_into_dirs()
        self.assertEqual(self.library_path.read_bytes(), first_document)
        self.assertEqual(
            sorted(path.relative_to(self.library_dir) for path in self.library_dir.rglob("*") if path.is_file()),
            first_tree,
        )

    def test_equivalent_unclaimed_categorized_file_is_reused_after_interruption(self):
        filename = "lib_orphan.png"
        payload = b"same-content"
        (self.library_dir / filename).write_bytes(payload)
        orphan = self.library_dir / "角色" / filename
        orphan.parent.mkdir(parents=True)
        orphan.write_bytes(payload)
        self.write_library([self.make_item("asset_orphan", filename)], category_dir="角色")

        main.migrate_asset_library_into_dirs()

        self.assertEqual(self.read_items()[0]["url"], self.asset_url(f"角色/{filename}"))
        self.assertFalse((self.library_dir / "角色" / "lib_orphan_2.png").exists())

    def test_flat_url_is_not_switched_when_legacy_confirmation_fails(self):
        filename = "lib_no_switch.png"
        source = self.library_dir / filename
        source.write_bytes(b"source")
        self.write_library([self.make_item("asset_no_switch", filename)], category_dir="角色")
        original_ensure = main.ensure_asset_library_compat_file
        calls = 0

        def fail_second_confirmation(source_path, target_path):
            nonlocal calls
            calls += 1
            if calls == 2:
                return False
            return original_ensure(source_path, target_path)

        with mock.patch.object(main, "ensure_asset_library_compat_file", side_effect=fail_second_confirmation):
            main.migrate_asset_library_into_dirs()

        item = self.read_items()[0]
        self.assertEqual(item["url"], self.asset_url(filename))
        self.assertNotIn("legacy_flat_url", item)

    def test_existing_conflicting_target_is_never_overwritten(self):
        source = self.library_dir / "source.png"
        target = self.library_dir / "group" / "source.png"
        source.write_bytes(b"source")
        target.parent.mkdir(parents=True)
        target.write_bytes(b"target")

        self.assertFalse(main.ensure_asset_library_compat_file(str(source), str(target)))
        self.assertEqual(target.read_bytes(), b"target")

    def test_compat_file_falls_back_to_copy_when_hardlinks_are_unavailable(self):
        source = self.library_dir / "source.png"
        target = self.library_dir / "group" / "source.png"
        source.write_bytes(b"copy-fallback")
        with mock.patch.object(main.os, "link", side_effect=OSError("hard links unavailable")):
            self.assertTrue(main.ensure_asset_library_compat_file(str(source), str(target)))
        self.assertEqual(target.read_bytes(), source.read_bytes())

    def test_interrupted_copy_fallback_leaves_no_partial_target_or_temp_file(self):
        source = self.library_dir / "source.png"
        target = self.library_dir / "group" / "source.png"
        source.write_bytes(b"complete-source")

        def partial_copy(_source, destination):
            Path(destination).write_bytes(b"partial")
            raise OSError("copy interrupted")

        with mock.patch.object(main.os, "link", side_effect=OSError("hard links unavailable")):
            with mock.patch.object(main.shutil, "copy2", side_effect=partial_copy):
                self.assertFalse(main.ensure_asset_library_compat_file(str(source), str(target)))

        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.glob(".*.tmp")), [])

    def test_replace_failure_cleans_copy_temp_file(self):
        source = self.library_dir / "source.png"
        target = self.library_dir / "group" / "source.png"
        source.write_bytes(b"complete-source")

        with mock.patch.object(main.os, "link", side_effect=OSError("hard links unavailable")):
            with mock.patch.object(main.os, "replace", side_effect=OSError("replace failed")):
                self.assertFalse(main.ensure_asset_library_compat_file(str(source), str(target)))

        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.glob(".*.tmp")), [])

    def test_native_nested_asset_does_not_gain_unproven_flat_alias(self):
        filename = "lib_native.png"
        categorized = self.library_dir / "角色" / filename
        categorized.parent.mkdir(parents=True)
        categorized.write_bytes(b"native")
        self.write_library([self.make_item("asset_native", f"角色/{filename}")], category_dir="角色")
        before = self.library_path.read_bytes()

        main.migrate_asset_library_into_dirs()

        self.assertFalse((self.library_dir / filename).exists())
        self.assertNotIn("legacy_flat_url", self.read_items()[0])
        self.assertEqual(self.library_path.read_bytes(), before)

    def test_equal_but_separate_flat_copy_is_not_claimed_as_legacy_alias(self):
        filename = "lib_equal_copy.png"
        categorized = self.library_dir / "角色" / filename
        categorized.parent.mkdir(parents=True)
        categorized.write_bytes(b"same-bytes")
        legacy = self.library_dir / filename
        legacy.write_bytes(b"same-bytes")
        self.assertFalse(os.path.samefile(categorized, legacy))
        self.write_library([self.make_item("asset_equal", f"角色/{filename}")], category_dir="角色")
        before = self.library_path.read_bytes()

        main.migrate_asset_library_into_dirs()

        self.assertNotIn("legacy_flat_url", self.read_items()[0])
        self.assertEqual(self.library_path.read_bytes(), before)

    def test_existing_hardlink_bootstraps_legacy_metadata_and_is_idempotent(self):
        filename = "lib_existing.png"
        categorized = self.library_dir / "角色" / filename
        categorized.parent.mkdir(parents=True)
        categorized.write_bytes(b"already-migrated")
        legacy = self.library_dir / filename
        try:
            os.link(categorized, legacy)
        except OSError as exc:
            self.skipTest(f"hard links unavailable: {exc}")
        self.write_library([self.make_item("asset_existing", f"角色/{filename}")], category_dir="角色")

        main.migrate_asset_library_into_dirs()

        self.assertEqual(self.read_items()[0]["legacy_flat_url"], self.asset_url(filename))
        first_document = self.library_path.read_bytes()
        main.migrate_asset_library_into_dirs()
        self.assertEqual(self.library_path.read_bytes(), first_document)

    def test_tracked_legacy_url_repairs_missing_alias(self):
        filename = "lib_repair.png"
        payload = b"repair-me"
        categorized = self.library_dir / "角色" / filename
        categorized.parent.mkdir(parents=True)
        categorized.write_bytes(payload)
        item = self.make_item("asset_repair", f"角色/{filename}", filename)
        self.write_library([item], category_dir="角色")
        before = self.library_path.read_bytes()

        main.migrate_asset_library_into_dirs()

        self.assertEqual((self.library_dir / filename).read_bytes(), payload)
        self.assertEqual(self.library_path.read_bytes(), before)

    def test_tracked_legacy_conflict_is_not_overwritten(self):
        filename = "lib_conflict.png"
        categorized = self.library_dir / "角色" / filename
        categorized.parent.mkdir(parents=True)
        categorized.write_bytes(b"canonical")
        legacy = self.library_dir / filename
        legacy.write_bytes(b"unrelated")
        item = self.make_item("asset_conflict", f"角色/{filename}", filename)
        self.write_library([item], category_dir="角色")
        before = self.library_path.read_bytes()

        main.migrate_asset_library_into_dirs()

        self.assertEqual(legacy.read_bytes(), b"unrelated")
        self.assertEqual(categorized.read_bytes(), b"canonical")
        self.assertEqual(self.library_path.read_bytes(), before)

    def test_remove_item_file_cleans_canonical_and_exclusive_alias(self):
        item, categorized, alias = self.make_nested_with_alias("asset_delete", "lib_delete.png")
        remaining = {
            "libraries": [{"categories": [{"items": []}]}],
        }

        main.remove_asset_library_file(item, remaining)

        self.assertFalse(categorized.exists())
        self.assertFalse(alias.exists())

    def test_remove_item_file_preserves_alias_referenced_by_another_item(self):
        first, first_path, alias = self.make_nested_with_alias("asset_first", "lib_shared.png", b"shared")
        second_path = self.library_dir / "场景" / "lib_shared_second.png"
        second_path.parent.mkdir(parents=True)
        second_path.write_bytes(b"shared")
        second = self.make_item("asset_second", "场景/lib_shared_second.png", "lib_shared.png")
        remaining = {
            "libraries": [{"categories": [{"items": [second]}]}],
        }

        main.remove_asset_library_file(first, remaining)

        self.assertFalse(first_path.exists())
        self.assertTrue(alias.exists())
        self.assertTrue(second_path.exists())

    def test_remove_item_file_preserves_tampered_alias(self):
        item, categorized, alias = self.make_nested_with_alias("asset_tampered", "lib_tampered.png", b"canonical")
        alias.unlink()
        alias.write_bytes(b"tampered!")
        remaining = {"libraries": [{"categories": [{"items": []}]}]}

        main.remove_asset_library_file(item, remaining)

        self.assertFalse(categorized.exists())
        self.assertTrue(alias.exists())
        self.assertEqual(alias.read_bytes(), b"tampered!")

    def test_single_delete_endpoint_cleans_legacy_alias(self):
        item, categorized, alias = self.make_nested_with_alias("asset_single", "lib_single.png")
        self.write_library([item], category_dir="角色")

        asyncio.run(main.delete_asset_library_item("asset_single"))

        self.assertFalse(categorized.exists())
        self.assertFalse(alias.exists())
        self.assertEqual(self.read_items(), [])

    def test_single_delete_save_failure_leaves_files_and_persisted_item_intact(self):
        item, categorized, alias = self.make_nested_with_alias("asset_save_fail", "lib_save_fail.png")
        self.write_library([item], category_dir="角色")

        with mock.patch.object(main, "save_asset_library", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                asyncio.run(main.delete_asset_library_item("asset_save_fail"))

        self.assertTrue(categorized.exists())
        self.assertTrue(alias.exists())
        self.assertEqual(self.read_items()[0]["id"], "asset_save_fail")

    def test_batch_delete_endpoint_cleans_all_legacy_aliases(self):
        first, first_path, first_alias = self.make_nested_with_alias("asset_batch_1", "lib_batch_1.png")
        second, second_path, second_alias = self.make_nested_with_alias("asset_batch_2", "lib_batch_2.png")
        self.write_library([first, second], category_dir="角色")

        payload = main.AssetLibraryBatchDeleteRequest(ids=["asset_batch_1", "asset_batch_2"])
        asyncio.run(main.batch_delete_asset_library_items(payload))

        for path in (first_path, first_alias, second_path, second_alias):
            self.assertFalse(path.exists())
        self.assertEqual(self.read_items(), [])

    def test_category_delete_endpoint_cleans_aliases_and_empty_folder(self):
        first, first_path, first_alias = self.make_nested_with_alias("asset_cat_1", "lib_cat_1.png")
        second, second_path, second_alias = self.make_nested_with_alias("asset_cat_2", "lib_cat_2.png")
        self.write_library([first, second], category_dir="角色", category_id="delete_me")

        asyncio.run(main.delete_asset_library_category("delete_me"))

        for path in (first_path, first_alias, second_path, second_alias):
            self.assertFalse(path.exists())
        self.assertFalse((self.library_dir / "角色").exists())
        categories = self.read_library()["libraries"][0]["categories"]
        self.assertFalse(any(cat.get("id") == "delete_me" for cat in categories))

    def test_category_delete_preserves_alias_referenced_by_surviving_category(self):
        deleted, deleted_path, alias = self.make_nested_with_alias(
            "asset_deleted", "lib_shared_category.png", b"shared-category", category="角色"
        )
        survivor_path = self.library_dir / "场景" / "lib_shared_survivor.png"
        survivor_path.parent.mkdir(parents=True)
        survivor_path.write_bytes(b"shared-category")
        survivor = self.make_item(
            "asset_survivor", "场景/lib_shared_survivor.png", "lib_shared_category.png"
        )
        self.write_categories([
            {"id": "delete_me", "name": "角色", "type": "image", "dir": "角色", "items": [deleted]},
            {"id": "keep_me", "name": "场景", "type": "image", "dir": "场景", "items": [survivor]},
            {"id": "workflows", "name": "工作流", "type": "workflow", "items": []},
        ])

        asyncio.run(main.delete_asset_library_category("delete_me"))

        self.assertFalse(deleted_path.exists())
        self.assertFalse((self.library_dir / "角色").exists())
        self.assertTrue(alias.exists())
        self.assertTrue(survivor_path.exists())
        categories = self.read_library()["libraries"][0]["categories"]
        self.assertTrue(any(cat.get("id") == "keep_me" for cat in categories))


if __name__ == "__main__":
    unittest.main()
