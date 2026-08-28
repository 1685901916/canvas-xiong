import main
from PIL import Image


def test_timeline_reference_timestamps_include_integer_seconds_and_true_tail():
    assert main.timeline_reference_timestamps(3.2) == [0.0, 1.0, 2.0, 3.0, 3.15]


def test_timeline_reference_timestamps_do_not_duplicate_short_tail():
    assert main.timeline_reference_timestamps(0.03) == [0.0]


def test_timeline_reference_label_uses_seconds_only():
    assert main.timeline_reference_time_label(0) == "0.0s"
    assert main.timeline_reference_time_label(3.15) == "3.2s"


def test_timeline_reference_cache_key_changes_with_source_metadata(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"first")
    first = main.timeline_reference_cache_key(str(source), 1.0)
    source.write_bytes(b"changed-media")
    second = main.timeline_reference_cache_key(str(source), 1.0)
    assert first != second


def test_timeline_reference_storyboard_contains_all_frames(tmp_path):
    frame_paths = []
    for index, color in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255))):
        frame_path = tmp_path / f"frame_{index}.jpg"
        Image.new("RGB", (90, 160), color).save(frame_path)
        frame_paths.append(str(frame_path))
    storyboard_path = tmp_path / "storyboard.jpg"
    result = main.build_timeline_reference_storyboard(
        frame_paths,
        ["0.0s", "1.0s", "2.0s"],
        str(storyboard_path),
    )
    assert storyboard_path.is_file()
    assert result["frame_count"] == 3
    with Image.open(storyboard_path) as storyboard:
        assert storyboard.width == result["width"]
        assert storyboard.height == result["height"]
        assert storyboard.width > 90


def test_timeline_reference_storyboard_uses_every_grid_slot_for_eleven_frames(tmp_path):
    frame_paths = []
    for index in range(11):
        frame_path = tmp_path / f"frame_{index}.jpg"
        Image.new("RGB", (54, 96), (index * 20, 80, 120)).save(frame_path)
        frame_paths.append(str(frame_path))
    storyboard_path = tmp_path / "storyboard_11.jpg"
    result = main.build_timeline_reference_storyboard(
        frame_paths,
        [f"{index}.0s" for index in range(11)],
        str(storyboard_path),
    )
    # Pick a near-square grid (4 cols x 3 rows) and pad the final row so the
    # all-frames overview never leaves a large blank block.
    assert result["frame_count"] == 11
    assert result["columns"] == 4
    assert result["rows"] == 3
    assert result["padded_count"] == 12
