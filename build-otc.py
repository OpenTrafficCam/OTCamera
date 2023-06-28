import os
import shutil
import zipfile
from abc import ABC, abstractmethod
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile


class File(ABC):
    @abstractmethod
    def source(self) -> Path:
        pass

    @abstractmethod
    def destination(self) -> Path:
        pass


@dataclass(frozen=True)
class SameNameFile(File):
    _path: Path

    def source(self) -> Path:
        return self._path

    def destination(self) -> Path:
        return self._path


@dataclass(frozen=True)
class DifferentNameFile(File):
    _source: Path
    _destination: Path

    def source(self) -> Path:
        return self._source

    def destination(self) -> Path:
        return self._destination


ENCODING: str = "UTF-8"


@dataclass(frozen=True)
class CliArguments:
    package_version: str


class CliArgumentParser:
    """OT build command line interface argument parser.

    Acts as a wrapper to `argparse.ArgumentParser`.

    Args:
        arg_parser (ArgumentParser, optional): the argument parser.
            Defaults to ArgumentParser("OT build").
    """

    def __init__(self, arg_parser: ArgumentParser = ArgumentParser("OT build")) -> None:
        self._parser = arg_parser
        self._setup()

    def _setup(self) -> None:
        """Sets up the argument parser by defining the command line arguments."""
        self._parser.add_argument(
            "--package_version",
            type=str,
            help="Version of the package. Defaults to 0.0",
            required=False,
            default="0.0",
        )

    def parse(self) -> CliArguments:
        """Parse and checks for cli arg

        Returns:
            CliArguments: _description_
        """
        args = self._parser.parse_args()
        return CliArguments(args.package_version)


def collect_files(
    base_path: Path,
    file_extension: str = ".py",
) -> list[File]:
    """Collect all files in the file tree.

    Args:
        base_path (Path): base path to start searching files
        file_extension (str, optional): only files with this extension will be
            collected. Defaults to ".py".

    Returns:
        list[Path]: list of collected files.
    """
    paths: list[File] = []
    for folder_name, subfolders, file_names in os.walk(base_path):
        for file_name in file_names:
            if file_name.endswith(file_extension):
                file_path = Path(folder_name, file_name)
                paths.append(SameNameFile(file_path))
    return paths


def zip_output_folder(input_folder: Path, zip_file: Path) -> None:
    """Zip a whole directory into a zip file. The directory structure (subdirectories)
        will remain in the zip file.

    Args:
        input_folder (Path): folder to zip
        zip_file (Path): zipped folder as file
    """
    with ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as output:
        for root, dirs, files in os.walk(input_folder):
            for file in files:
                file_path = Path(root, file)
                base_path = Path(input_folder, ".")
                output_path = file_path.relative_to(base_path)
                output.write(file_path, output_path)


def clean_directory(directory: Path) -> None:
    """Clean the given directory.

    Args:
        directory (Path): directory to clean.
    """
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(exist_ok=True)


@dataclass(frozen=True)
class Configuration:
    """Configuration for deployment. It contains all files required on the given
    platform (suffix)
    """

    _package_version: str
    _package_path: Path
    _files: list[File]
    _additional_files: list[File]
    _suffix: str

    def create_zip(
        self, file_name: str, output_directory: Path, temp_directory: Path
    ) -> None:
        """Create a zip file with the given name in the given output directory.
        Store temporal artifacts in the temp_folder.

        Args:
            file_name (str): name of the zip file.
            output_directory (Path): directory to store the zip file in.
            temp_directory (Path): directory for temporal artifacts.
        """
        clean_directory(build_path)
        zip_file = Path(output_directory, self._build_file_name(file_name))
        self._copy_to_output_directory(temp_directory)
        # self._update_version_file_in(temp_directory)
        # TODO: enable version file
        zip_output_folder(temp_directory, zip_file)
        clean_directory(build_path)

    def _build_file_name(self, file_name: str) -> str:
        return f"{file_name}-{self._suffix}-{self._package_version}.zip"

    def _copy_to_output_directory(self, output_directory: Path) -> None:
        files = collect_files(base_path=self._package_path, file_extension=".py")
        # TODO dont copy just py files, at least for pcb and printables
        self._copy_files(files, output_directory=output_directory)

        self._copy_files(self._files, output_directory=output_directory)
        self._copy_files(self._additional_files, output_directory=output_directory)

    def _copy_files(self, files: list[File], output_directory: Path) -> None:
        """Copies all files into the output directory. The directory structure will
        remain.

        Args:
            files (list[Path]): files to copy.
            output_directory (Path): directory to copy the files to.
        """
        for file in files:
            output_file = Path(output_directory, file.destination())
            output_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(file.source(), output_file)

    def _update_version_file_in(self, directory: Path) -> None:
        version_file = Path(directory, self._package_path, "version.txt")
        content = f'__version__ = "{self._package_version}"'
        with open(version_file, "wt", encoding=ENCODING) as file:
            file.write(content)


cli_args = CliArgumentParser().parse()

build_path = Path("build")
distribution_path = Path("dist")
output_file_name = "otcamera"

package_path = Path("OTCamera")
printables_path = Path("hardware_parts/3dprints")
pcb_path = Path("hardware_parts/pcb")

package_version = cli_args.package_version
printables_version = "0.0"
pcb_version = "0.0"
# TODO: read version from files

base_files: list[File] = [
    SameNameFile(Path("LICENSE")),
    SameNameFile(Path("README.md")),
]

pizerow_files: list[File] = [
    SameNameFile(Path("hardware_test.py")),
    SameNameFile(Path("requirements.txt")),
    SameNameFile(Path("run.py")),
    SameNameFile(Path("usb_flash_drive_copy.py")),
    DifferentNameFile(Path("user_config.example.yaml"), Path("user_config.yaml")),
    # TODO: move wifistart to raspi-files root
    SameNameFile(Path("./raspi-files/usr/local/bin/wifistart")),
    # TODO: use these files in ansible
    SameNameFile(Path("./raspi-files/install_sshrelay.sh")),
    SameNameFile(Path("./raspi-files/otcamera.service")),
    SameNameFile(Path("./raspi-files/sshrelay.service")),
    SameNameFile(Path("./raspi-files/uninstall_otcamera.sh")),
    # SameNameFile(Path("./webfiles/**")),
    # TODO: add path
]

printable_files: list[File] = []

pcb_files: list[File] = []

configurations: list[Configuration] = [
    Configuration(
        _package_version=package_version,
        _package_path=package_path,
        _files=base_files,
        _additional_files=pizerow_files,
        _suffix="pizerow",
    ),
    Configuration(
        _package_version=printables_version,
        _package_path=printables_path,
        _files=base_files,
        _additional_files=printable_files,
        _suffix="3dprints",
    ),
    Configuration(
        _package_version=pcb_version,
        _package_path=pcb_path,
        _files=base_files,
        _additional_files=pcb_files,
        _suffix="pcb",
    ),
]

clean_directory(distribution_path)
for configuration in configurations:
    configuration.create_zip(
        output_file_name,
        output_directory=distribution_path,
        temp_directory=build_path,
    )
