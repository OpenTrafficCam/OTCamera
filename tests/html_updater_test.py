from pathlib import Path
from typing import Callable

import pytest
from bs4 import BeautifulSoup

from OTCamera import config
from OTCamera.html_updater import (
    ConfigData,
    ConfigHtmlId,
    OTCameraHTMLDataObject,
    OTCameraHTMLUpdater,
    StatusData,
)
from OTCamera.html_updater import StatusHtmlId as status_id


@pytest.fixture
def html_updater() -> OTCameraHTMLUpdater:
    return OTCameraHTMLUpdater(debug_mode_on=True)


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
def status_data() -> StatusData:
    return StatusData(
        time=(status_id.TIME, "2022-05-05T11:26:30"),
        hostname=(status_id.HOSTNAME, "my-hostname"),
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
def config_data() -> ConfigData:
    return ConfigData(
        debug_mode_on=(ConfigHtmlId.DEBUG_MODE_ON, config.DEBUG_MODE_ON),
        start_hour=(ConfigHtmlId.START_HOUR, config.START_HOUR),
        end_hour=(ConfigHtmlId.END_HOUR, config.END_HOUR),
        interval_video_split=(
            ConfigHtmlId.INTERVAL_VIDEO_SPLIT,
            config.INTERVAL_VIDEO_SPLIT,
        ),
        num_intervals=(ConfigHtmlId.NUM_INTERVALS, config.NUM_INTERVALS),
        preview_interval=(ConfigHtmlId.PREVIEW_INTERVAL, config.PREVIEW_INTERVAL),
        min_free_space=(ConfigHtmlId.MIN_FREE_SPACE, config.MIN_FREE_SPACE),
        prefix=(ConfigHtmlId.PREFIX, config.PREFIX),
        video_dir=(ConfigHtmlId.VIDEO_DIR, config.VIDEO_DIR),
        preview_path=(ConfigHtmlId.PREVIEW_PATH, config.PREVIEW_PATH),
        template_html_path=(ConfigHtmlId.TEMPLATE_HTML_PATH, config.TEMPLATE_HTML_PATH),
        index_html_path=(ConfigHtmlId.INDEX_HTML_PATH, config.INDEX_HTML_PATH),
        fps=(ConfigHtmlId.FPS, config.FPS),
        resolution=(ConfigHtmlId.RESOLUTION, config.RESOLUTION),
        exposure_mode=(ConfigHtmlId.EXPOSURE_MODE, config.EXPOSURE_MODE),
        drc_strength=(ConfigHtmlId.DRC_STRENGTH, config.DRC_STRENGTH),
        rotation=(ConfigHtmlId.ROTATION, config.ROTATION),
        awb_mode=(ConfigHtmlId.AWB_MODE, config.AWB_MODE),
        video_format=(ConfigHtmlId.VIDEO_FORMAT, config.VIDEO_FORMAT),
        preview_format=(ConfigHtmlId.PREVIEW_FORMAT, config.PREVIEW_PATH),
        res_of_saved_video_file=(
            ConfigHtmlId.RESOLUTION_SAVED_VIDEO_FILE,
            config.RESOLUTION_SAVED_VIDEO_FILE,
        ),
        h264_profile=(ConfigHtmlId.H264_PROFILE, config.H264_PROFILE),
        h264_bitrate=(ConfigHtmlId.H264_BITRATE, config.H264_BITRATE),
        h264_quality=(ConfigHtmlId.H264_QUALITY, config.H264_QUALITY),
        use_led=(ConfigHtmlId.USE_LED, config.USE_LED),
        use_buttons=(ConfigHtmlId.USE_BUTTONS, config.USE_BUTTONS),
        wifi_delay=(ConfigHtmlId.WIFI_DELAY, config.WIFI_DELAY),
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
    html_updater: OTCameraHTMLUpdater,
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
    html_updater: OTCameraHTMLUpdater,
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
    html_updater: OTCameraHTMLUpdater,
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
            '<div id="status-info"><p id="hostname">my-hostname</p></div>',
        ),
    ],
)
def test_update_by_id(
    html_updater: OTCameraHTMLUpdater,
    html: str,
    expected: str,
    status_data: OTCameraHTMLDataObject,
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
            '<div id="status-info" style="display: revert"><p id="hostname">my-hostname</p></div>',
        ),
    ],
)
def test_update_info(
    html_updater: OTCameraHTMLUpdater,
    create_html_file: Callable[[str, str], Path],
    html: str,
    expected: str,
    status_data: OTCameraHTMLDataObject,
    config_data: OTCameraHTMLDataObject,
):
    html_filepath = create_html_file("test.html", html)
    html_updater.update_info(html_filepath, html_filepath, status_data, config_data)

    result = parse_html(html_filepath)

    assert result == expected


def parse_html(path: Path) -> str:
    with open(path) as html_stream:
        soup = BeautifulSoup(html_stream, "html.parser")
        return str(soup)
