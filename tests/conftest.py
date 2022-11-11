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

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def test_dir() -> Path:
    test_dir = Path(__file__).parent / "data"
    test_dir.mkdir(exist_ok=True)
    yield test_dir
    for f in test_dir.iterdir():
        try:
            f.unlink()
        except IsADirectoryError:
            shutil.rmtree(f)


@pytest.fixture
def resources_dir() -> Path:
    resources_dir = Path(__file__).parent / "resources"
    return resources_dir
