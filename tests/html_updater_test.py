# Copyright (C) 2023 OpenTrafficCam Contributors
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
    StatusHtmlId,
    StatusWebsiteUpdater,
)


@pytest.fixture
def template_html_path() -> Path:
    return Path("webfiles/template.html")


@pytest.fixture
def offline_html_path() -> Path:
    return Path("webfiles/offline.html")


@pytest.fixture
def html_save_path(test_dir: Path) -> Path:
    return test_dir / "index.html"


@pytest.fixture
def html_updater(
    template_html_path: Path,
    offline_html_path: Path,
    html_save_path: Path,
) -> StatusWebsiteUpdater:
    return StatusWebsiteUpdater(
        template_html_path=template_html_path,
        offline_html_path=offline_html_path,
        html_save_path=html_save_path,
        debug_mode_on=True,
    )


@pytest.fixture
def create_html_file(test_dir: Path) -> Callable[[str, str], Path]:
    def _create_html_file(file_name: str, content: str) -> Path:
        html_path = test_dir / file_name
        html_path.write_text(content, encoding="utf-8")
        return html_path

    return _create_html_file


@pytest.fixture
def status_data() -> StatusDataObject:
    return StatusDataObject(
        free_diskspace=(StatusHtmlId.FREE_DISKSPACE, "12 GB"),
        num_videos_recorded=(StatusHtmlId.NUM_VIDEOS_RECORDED, 4),
        currently_recording=(StatusHtmlId.CURRENTLY_RECORDING, True),
        low_battery=(StatusHtmlId.LOW_BATTERY, False),
        hour_button_active=(StatusHtmlId.HOUR_BUTTON_ACTIVE, False),
        external_power_supply_connected=(
            StatusHtmlId.EXT_POWER_SUPPLY_CONNECTED,
            True,
        ),
        ms_teams_webhook_enabled=(StatusHtmlId.MS_TEAMS_WEBHOOK_ENABLED, False),
        time_until_wifi_off=(StatusHtmlId.TIME_UNTIL_WIFI_OFF, "300s"),
    )


@pytest.fixture
def config_data(template_html_path: Path, html_save_path: Path) -> ConfigDataObject:
    return ConfigDataObject(
        debug_mode_on=(ConfigHtmlId.DEBUG_MODE_ON, True),
        start_hour=(ConfigHtmlId.START_HOUR, 6),
        end_hour=(ConfigHtmlId.END_HOUR, 22),
        interval_video_split=(ConfigHtmlId.INTERVAL_VIDEO_SPLIT, 15),
        num_intervals=(ConfigHtmlId.NUM_INTERVALS, 0),
        preview_interval=(ConfigHtmlId.PREVIEW_INTERVAL, 5),
        min_free_space=(ConfigHtmlId.MIN_FREE_SPACE, 1),
        prefix=(ConfigHtmlId.PREFIX, "my_prefix"),
        video_dir=(ConfigHtmlId.VIDEO_DIR, "path/to/video/dir"),
        preview_path=(ConfigHtmlId.PREVIEW_PATH, "path/to/preview.jpeg"),
        template_html_path=(ConfigHtmlId.TEMPLATE_HTML_PATH, str(template_html_path)),
        index_html_path=(ConfigHtmlId.INDEX_HTML_PATH, str(html_save_path)),
        fps=(ConfigHtmlId.FPS, 20),
        resolution=(ConfigHtmlId.RESOLUTION, (1640, 1232)),
        exposure_mode=(ConfigHtmlId.EXPOSURE_MODE, "nightpreview"),
        drc_strength=(ConfigHtmlId.DRC_STRENGTH, "high"),
        rotation=(ConfigHtmlId.ROTATION, 180),
        awb_mode=(ConfigHtmlId.AWB_MODE, "greyworld"),
        video_format=(ConfigHtmlId.VIDEO_FORMAT, "h264"),
        preview_format=(ConfigHtmlId.PREVIEW_FORMAT, "jpeg"),
        res_of_saved_video_file=(ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE, (800, 600)),
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
        log_data=(LogHtmlId.LOG_DATA, "Log File Number 1\nLog line 1\nLog line 2")
    )


@pytest.mark.parametrize(
    ("html", "expected"),
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
def test_disable_tag_by_id(
    html_updater: StatusWebsiteUpdater,
    html: str,
    expected: str,
) -> None:
    html_tree = BeautifulSoup(html, "html.parser")

    html_updater._disable_tag_by_id(html_tree, "status-info")

    assert str(html_tree) == expected


@pytest.mark.parametrize(
    ("html", "expected"),
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

    html_updater._enable_tag_by_id(html_tree, "status-info")

    assert str(html_tree) == expected


@pytest.mark.parametrize(
    ("html", "text", "expected"),
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
) -> None:
    html_tree = BeautifulSoup(html, "html.parser")

    html_updater._change_content(html_tree.div, text)

    assert str(html_tree) == expected


def test_update_by_id(
    html_updater: StatusWebsiteUpdater,
    status_data: OTCameraDataObject,
) -> None:
    html_tree = BeautifulSoup(
        (
            '<div id="status-info">'
            '<p id="free-diskspace"></p>'
            '<p id="num-videos"></p>'
            "</div>"
        ),
        "html.parser",
    )

    html_updater._update_by_id(html_tree, status_data)

    assert html_tree.find(id="free-diskspace").string == "12 GB"
    assert html_tree.find(id="num-videos").string == "4"


def test_disable_info_writes_hidden_sections(
    html_updater: StatusWebsiteUpdater,
    html_save_path: Path,
) -> None:
    html_updater.disable_info()

    soup = parse_html(html_save_path)

    assert soup.find(id="status-info")["style"] == "display: none"
    assert soup.find(id="config-info")["style"] == "display: none"


def test_update_info_builds_status_and_config_tables(
    html_updater: StatusWebsiteUpdater,
    status_data: OTCameraDataObject,
    config_data: OTCameraDataObject,
    html_save_path: Path,
) -> None:
    html_updater.update_info(
        status_info=status_data,
        config_info=config_data,
        currently_recording=True,
        always_recording=False,
        external_power_supply_connected=False,
    )

    soup = parse_html(html_save_path)

    assert soup.find(id="status-info")["style"] == "display: revert"
    assert soup.find(id="config-info")["style"] == "display: revert"
    assert soup.find(id="recording-banner").get_text(strip=True) == (
        "Currently recording (not 24/7)"
    )
    assert soup.find(id="ext-power-supply-banner").get_text(strip=True) == (
        "Not connected to external power supply"
    )
    assert soup.find(id="free-diskspace").find_all("td")[1].get_text(strip=True) == (
        "12 GB"
    )
    assert soup.find(id="debug-mode-on").find_all("td")[1].get_text(strip=True) == (
        "True"
    )


def test_display_offline_info_includes_log_output(
    html_updater: StatusWebsiteUpdater,
    log_data: LogDataObject,
    html_save_path: Path,
) -> None:
    html_updater.display_offline_info(log_data)

    soup = parse_html(html_save_path)

    assert soup.find(id="log-info") is not None
    assert "Log File Number 1" in soup.find(id="log-data").get_text()


def parse_html(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
