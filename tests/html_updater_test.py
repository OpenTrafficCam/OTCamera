# Copyright (C) 2022 OpenTrafficCam Contributors
# <https://github.com/OpenTrafficCam>
# <team@opentrafficcam.org>

# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A

# PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program.  If not, see <https://www.gnu.org/licenses/>.

from pathlib import Path
from typing import Callable

import pytest
from bs4 import BeautifulSoup

from OTCamera.html_updater import (
    ConfigDataObject,
    ConfigHtmlId,
    LogDataObject,
    LogHtmlId,
    OTCameraDataObject,
    StatusDataObject,
)
from OTCamera.html_updater import StatusHtmlId as status_id
from OTCamera.html_updater import StatusWebsiteUpdater


@pytest.fixture
def html_updater() -> StatusWebsiteUpdater:
    return StatusWebsiteUpdater(debug_mode_on=True)


@pytest.fixture
def create_html_file(test_dir: Path) -> Callable[[str, str], Path]:
    def _create_html_file(file_name: str, content: str) -> Path:
        print("iam here")
        html_path = test_dir / file_name
        html_path.touch(exist_ok=True)

        with open(html_path, "w") as f:
            f.write(content)

        return html_path

    return _create_html_file


@pytest.fixture
def status_data() -> StatusDataObject:
    return StatusDataObject(
        time=(status_id.TIME, "2022-05-05T11:26:30"),
        hostname=(status_id.HOSTNAME, "my-name"),
        free_diskspace=(status_id.FREE_DISKSPACE, 12),
        num_videos_recorded=(status_id.NUM_VIDEOS_RECORDED, 4),
        currently_recording=(status_id.CURRENTLY_RECORDING, True),
        wifi_active=(status_id.WIFI_ACTIVE, True),
        low_battery=(status_id.LOW_BATTERY, False),
        power_button_active=(status_id.POWER_BUTTON_ACTIVE, True),
        hour_button_active=(status_id.HOUR_BUTTON_ACTIVE, False),
        wifi_ap_on=(status_id.WIFI_AP_ON, False),
    )


@pytest.fixture
def config_data() -> ConfigDataObject:
    return ConfigDataObject(
        debug_mode_on=(ConfigHtmlId.DEBUG_MODE_ON, True),
        start_hour=(ConfigHtmlId.START_HOUR, 6),
        end_hour=(ConfigHtmlId.END_HOUR, 22),
        interval_video_split=(
            ConfigHtmlId.INTERVAL_VIDEO_SPLIT,
            15,
        ),
        num_intervals=(ConfigHtmlId.NUM_INTERVALS, 0),
        preview_interval=(ConfigHtmlId.PREVIEW_INTERVAL, 5),
        min_free_space=(ConfigHtmlId.MIN_FREE_SPACE, 1),
        prefix=(ConfigHtmlId.PREFIX, "my_prefix"),
        video_dir=(ConfigHtmlId.VIDEO_DIR, "path/to/video/dir"),
        preview_path=(ConfigHtmlId.PREVIEW_PATH, "path/to/preview.jpeg"),
        template_html_path=(ConfigHtmlId.TEMPLATE_HTML_PATH, "path/to/template.html"),
        index_html_path=(ConfigHtmlId.INDEX_HTML_PATH, "path/to/index.html"),
        fps=(ConfigHtmlId.FPS, 20),
        resolution=(ConfigHtmlId.RESOLUTION, (1640, 1232)),
        exposure_mode=(ConfigHtmlId.EXPOSURE_MODE, "nightpreview"),
        drc_strength=(ConfigHtmlId.DRC_STRENGTH, "high"),
        rotation=(ConfigHtmlId.ROTATION, 180),
        awb_mode=(ConfigHtmlId.AWB_MODE, "greyworld"),
        video_format=(ConfigHtmlId.VIDEO_FORMAT, "h264"),
        preview_format=(ConfigHtmlId.PREVIEW_FORMAT, "jpeg"),
        res_of_saved_video_file=(
            ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE,
            (800, 600),
        ),
        h264_profile=(ConfigHtmlId.H264_PROFILE, "high"),
        h264_level=(ConfigHtmlId.H264_LEVEL, "4"),
        h264_bitrate=(ConfigHtmlId.H264_BITRATE, 600000),
        h264_quality=(ConfigHtmlId.H264_QUALITY, 30),
        use_led=(ConfigHtmlId.USE_LED, False),
        use_buttons=(ConfigHtmlId.USE_BUTTONS, False),
        wifi_delay=(ConfigHtmlId.WIFI_DELAY, 900),
    )


@pytest.fixture
def log_data() -> LogDataObject:
    return LogDataObject(
        log_data=(LogHtmlId.LOG_DATA, "Log File Number 1\n Log line 1\n Log line 2")
    )


@pytest.mark.parametrize(
    "html, expected",
    [
        (
            '<div id="status-info" style="display: revert"></div>',
            '<div id="status-info" style="display: none"></div>',
        ),
        (
            '<div id="status-info"></div>',
            '<div id="status-info" style="display: none"></div>',
        ),
        (
            '<div id="status-info" style="display: none"></div>',
            '<div id="status-info" style="display: none"></div>',
        ),
        (
            '<div style="display: none"></div>',
            '<div style="display: none"></div>',
        ),
    ],
)
def test_disable_info_visibleHtmlAsParam_returnsDisabledTag(
    html_updater: StatusWebsiteUpdater,
    create_html_file: Callable[[str, str], Path],
    html: str,
    expected: str,
) -> None:
    html_filepath = create_html_file(file_name="test.html", content=html)
    html_updater.disable_info(html_filepath)
    result = parse_html(html_filepath)

    assert result == expected


@pytest.mark.parametrize(
    "html, expected",
    [
        (
            '<div id="status-info" style="display: revert"></div>',
            '<div id="status-info" style="display: revert"></div>',
        ),
        (
            '<div id="status-info"></div>',
            '<div id="status-info" style="display: revert"></div>',
        ),
        (
            '<div id="status-info" style="display: none"></div>',
            '<div id="status-info" style="display: revert"></div>',
        ),
        (
            '<div style="display: none"></div>',
            '<div style="display: none"></div>',
        ),
    ],
)
def test_enable_tag_by_id(
    html_updater: StatusWebsiteUpdater,
    html: str,
    expected: str,
) -> None:

    html_tree = BeautifulSoup(html, "html.parser")

    html_updater._enable_tag_by_id(html_tag=html_tree, id="status-info")
    result = str(html_tree)

    assert result == expected


@pytest.mark.parametrize(
    "html,text, expected",
    [
        (
            '<div id="status-info" style="display: revert"></div>',
            "I am some content.",
            '<div id="status-info" style="display: revert">I am some content.</div>',
        ),
        (
            "<div></div>",
            "I am some content.",
            "<div>I am some content.</div>",
        ),
        (
            '<div id="status-info" style="display: none">Previous</div>',
            "I am some content.",
            '<div id="status-info" style="display: none">I am some content.</div>',
        ),
        (
            '<div style="display: none"></div>',
            "",
            '<div style="display: none"></div>',
        ),
    ],
)
def test_change_content(
    html_updater: StatusWebsiteUpdater,
    html: str,
    text: str,
    expected: str,
):
    html_tree = BeautifulSoup(html, "html.parser")
    html_updater._change_content(html_tag=html_tree.div, content=text)
    result = str(html_tree)

    assert result == expected


@pytest.mark.parametrize(
    "html, expected",
    [
        (
            '<div id="status-info" style="display: revert">I am some content.</div>',
            '<div id="status-info" style="display: revert">I am some content.</div>',
        ),
        (
            '<div id="status-info"><p id="hostname"></p></div>',
            '<div id="status-info"><p id="hostname">my-name</p></div>',
        ),
    ],
)
def test_update_by_id(
    html_updater: StatusWebsiteUpdater,
    html: str,
    expected: str,
    status_data: OTCameraDataObject,
):
    html_tree = BeautifulSoup(html, "html.parser")
    html_updater._update_by_id(html_tree=html_tree, update_info=status_data)
    result = str(html_tree)

    assert result == expected


@pytest.mark.parametrize(
    "html, expected",
    [
        (
            '<div id="status-info" style="display: revert">I am some content.</div>',
            '<div id="status-info" style="display: revert">I am some content.</div>',
        ),
        (
            '<div id="status-info"><p id="hostname"></p></div>',
            (
                '<div id="status-info" style="display: revert">'
                '<p id="hostname">my-name</p></div>'
            ),
        ),
    ],
)
def test_update_info(
    html_updater: StatusWebsiteUpdater,
    create_html_file: Callable[[str, str], Path],
    html: str,
    expected: str,
    status_data: OTCameraDataObject,
    config_data: OTCameraDataObject,
):
    html_filepath = create_html_file("test.html", html)
    html_updater.update_info(html_filepath, html_filepath, status_data, config_data)

    result = parse_html(html_filepath)

    assert result == expected


def test_update_info_htmlWithAllIdsAsParam(
    html_updater: StatusWebsiteUpdater,
    status_data: OTCameraDataObject,
    config_data: OTCameraDataObject,
    test_dir: Path,
    resources_dir: Path,
):
    template_html_filepath = resources_dir / "template.html"
    expected_html_filepath = resources_dir / "expected.html"
    result_save_path = test_dir / "result.html"

    html_updater.update_info(
        template_html_filepath, result_save_path, status_data, config_data
    )
    soup_result = parse_html(result_save_path)
    soup_expected = parse_html(expected_html_filepath)
    str_result = str(soup_result)
    str_expected = str(soup_expected)

    assert str_result == str_expected


def parse_html(path: Path) -> str:
    with open(path) as html_stream:
        soup = BeautifulSoup(html_stream, "html.parser")
        return str(soup)
