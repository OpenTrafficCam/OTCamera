r"""Contains classes that allow writing metrics to csv files.

Use a `MetricsLogger` thread together with either `FileCsvLogger`
or `DailyRotationCsvLogger` and supply a dict of fieldnames and
callables that return the metrics.

The following code will log the free disk space to a file every 5 seconds.
```
import shutil

mlogger = MetricsLogger(
    logger=FileCsvLogger(file_path="sensors.csv"),
    metrics={
        "disk_free_root_mb": lambda: shutil.disk_usage("/").free / (1024 * 1024)
    },
    interval=5
)

# start the thread.
mlogger.start()


# stop the thread
try:
    mlogger.join()
except KeyboardInterrupt:
    mlogger.stop()
    mlogger.join()

The resulting file will look like this:

datetime,disk_free_root_mb\n
2026-06-09T13:42:13.153427,125345\n
"""

import csv
import logging
from abc import abstractmethod
from collections.abc import Callable, Collection
from contextlib import AbstractContextManager
from datetime import date, datetime
from io import TextIOWrapper
from pathlib import Path
from threading import Event, Thread
from typing import Any

lib_logger = logging.getLogger(__name__)


class CsvLogger(AbstractContextManager):
    """ABC for CsvLoggers.

    Is an AbstractContextManager. It assumes that children will take care of the
    file handles for writing to CSV files and that the underlying resources
    can be safely operated by using a context manager.
    """

    @abstractmethod
    def write(self, row: dict, timestamp: None | str = None) -> None:
        """Write a row of metrics data to the csv file.

        Args:
            row (dict): Dict that maps field names to metric data to write.
            timestamp (str | None): Timestamp to use for the current time column.
                Can be used to overwrite the result of `time_func`, which is
                used by default.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the underlying file handle and csv writer."""
        ...


class FileCsvLogger(CsvLogger):
    r"""Log values to a csv-file with the current time.

    Will open the file passed as an argument in append-mode. Can be used
    in a `with` context to close the underlying file automatically.
    Otherwise, the `.close()` method can be used.

    Usage:

    ```
    with FileCsvLogger(file_path="sensors.csv") as logger:
        logger.write({"sensor_a": 0.1, "sensor_b": 0.2})
        logger.write({"sensor_a": 0.15, "sensor_b": 0.21})
    ```

    The current date and time will always be prependend automatically.
    The above code will result in the following file:

    datetime,sensor_a,sensor_b\n
    2025-12-02T12:00:00,0.1,0.2\n
    2025-12-02T12:00:01,0.15,0.21\n

    The name and content of the first column can be influenced by modifying
    the `time_func` and `time_fieldname` parameters.

    The csv-header row will be written only if the file that is passed
    as `file_path` is either new or empty.
    """

    def __init__(
        self,
        file_path: Path,
        fieldnames: Collection[str] | None = None,
        time_func: Callable[[], str] = lambda: datetime.now().isoformat(),
        time_fieldname: str = "datetime",
    ):
        """Initializes a new FileSensorLogger.

        Args:
            file_path (Path): Path to the file to log to.
            fieldnames: (Collection[str] | None): CSV fieldnames to use for the rows.
                If not given, will be inferred from the first row that is written.
            time_func: (Callable[[]], str]): Function that is called to produce the
                string that serves as the current timestamp. The default will produce
                the current datetime in isoformat: YYYY-MM-DD HH:MM:SS.mmmmmm
            time_fieldname: The fieldname to use for the current time as returned
                by `time_func`
        """
        self.time_fieldname = time_fieldname
        self.fieldnames = list(fieldnames) if fieldnames is not None else None

        self.time_func = time_func

        self._file_path = file_path

        self._file_handle: TextIOWrapper | None = None
        self._writer: csv.DictWriter | None = None

    def _open(self) -> None:
        # Always called from write() after fieldnames is populated
        assert self.fieldnames is not None
        if self._file_handle is not None:
            self._file_handle.close()

        is_new = False
        if not self._file_path.exists() or self._file_path.stat().st_size == 0:
            is_new = True

        self._file_handle = open(self._file_path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(
            self._file_handle, fieldnames=[self.time_fieldname] + self.fieldnames
        )

        if is_new:
            self._writer.writeheader()

    def close(self) -> None:
        """Close the underlying file handle and csv writer."""
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None
        self._writer = None

    def write(self, row: dict, timestamp: str | None = None) -> None:
        """Write a row of metrics data to the csv file.

        Args:
            row (dict): Dict that maps field names to metric data to write.
            timestamp (str | None): Timestamp to use for the current time column.
                Can be used to overwrite the result of `time_func`,
                which is used by default.
        """
        if self._writer is None:
            if self.fieldnames is None:
                self.fieldnames = list(row.keys())
            self._open()

        # _open() always assigns both _writer and _file_handle before returning
        assert self._writer is not None
        assert self._file_handle is not None
        row_to_write = {self.time_fieldname: timestamp or self.time_func(), **row}
        lib_logger.debug(f"Wrote row {row_to_write} to {self._file_path}")

        self._writer.writerow(row_to_write)
        self._file_handle.flush()

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        """Exit the context manager and call `.close()`."""
        self.close()


class DailyRotationCsvLogger(FileCsvLogger):
    """Log values to a csv file that rotates daily.

    Accepts a directory to write csv files to and a prefix to build the
    log-filenames from. Rotation is handled transparently.

    Usage:

    ```
    with DailyRotationCsvLogger(
        directory=Path("/var/log/mylog"),
        prefix="myprefix"
    ) as csv_logger:
        csv_logger.write({"sensor_a": 1, "sensor_b": 2})
        csv_logger.write({"sensor_a": 3, "sensor_b": 4})
    ```

    This result in a file with a name in the format myprefix_YYYY-MM-DD.csv
    in the given directory.
    """

    def __init__(
        self,
        directory: Path,
        prefix: str,
        fieldnames: Collection[str] | None = None,
        time_func: Callable[[], str] = lambda: datetime.today().isoformat(),
        time_fieldname: str = "datetime",
    ):
        """Init a new DailyRotationCsvLoggeer.

        Args:
            directory (Path): The directory the log files will be written to.
                Will be created if it does not exist.
            prefix (str): The prefix that will prepended to all files, followed
                by the date string: <my_prefix>_YYYY-MM-DD.csv
            fieldnames: (Collection[str] | None): CSV fieldnames to use for the csv
                rows. If not given, will be inferred from the first row that is written.
            time_func: (Callable[[]], str]): Function that is called to produce the
                string that serves as the current timestamp. The default will produce
                the current datetime in isoformat: YYYY-MM-DD HH:MM:SS.mmmmmm
            time_fieldname: The fieldname to use for the current time as returned
                by `time_func`
        """
        # keep track of the current day
        self._day = date.today()

        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

        self.prefix = prefix

        self._file_path = self._get_file_path()

        super().__init__(
            file_path=self._file_path,
            fieldnames=fieldnames,
            time_func=time_func,
            time_fieldname=time_fieldname,
        )

    def _get_file_path(self) -> Path:
        return self.directory / f"{self.prefix}_{self._day.isoformat()}.csv"

    def write(self, row: dict, timestamp: str | None = None) -> None:
        """Write a row of data to the csv file.

        **NOTE**: The timestamp value that is passed here does not influence
        the rotation of output files. This will always use the system time
        as returned by `time.time()`.

        Args:
            row (dict): Dict that maps field names to metric data to write.
            timestamp (str | None): Timestamp to use for the current
                time column. Can be used to overwrite the result of `time_func`,
                which is used by the default.
        """
        today = date.today()
        if today != self._day:
            self._day = today
            self._file_path = self._get_file_path()

            if self._file_handle is not None:
                self._file_handle.close()
                self._file_handle = None

            self._writer = None

        super().write(row=row, timestamp=timestamp)


class MetricsLogger(Thread):
    """Thread that continuosly write metrics in CSV format to disk.

    Accepts a `CsvLogger` and a dict of `metrics`, that is a mapping
    from the csv fieldnames to a callable that returns the corresponding metric.
    Each metric callable is called and the results are written using the `CsvLogger`.
    The process is repeated with a wait time of `interval` seconds between runs.
    """

    def __init__(
        self,
        logger: CsvLogger,
        metrics: dict[str, Callable[[], Any]],
        interval: float,
    ):
        """Create a new MetricsLogger thread.

        Call its `start()` method to start the actual logging activity.

        Args:
            logger (CsvLogger): A CsvLogger instace used to write the metrics
                data to a csv file.
            metrics (dict[str, Callable[[], Any]]): A mapping from
                field names to callables that return the metrics to write.
            interval (float): The wait time between one cycle of gathering
                metrics results and writing them.
        """
        super().__init__()
        self._logger = logger
        self._metrics = metrics
        self._interval = interval
        self._shutdown = Event()

    def run(self) -> None:
        """Start the logging activity."""
        with self._logger as logger:
            while True:
                row = {}
                for name, read in self._metrics.items():
                    try:
                        val = str(read())
                    except Exception as e:
                        val = "N/A"
                        lib_logger.warning(
                            f"Exception while getting metric 'name': {e}"
                        )
                    row[name] = val
                logger.write(row)
                if self._shutdown.wait(timeout=self._interval):
                    break

    def stop(self) -> None:
        """Signal the logging thread to stop.

        Will also attempt cleanly close the loggers currently open
        file handle.
        """
        self._shutdown.set()
        self._logger.close()
