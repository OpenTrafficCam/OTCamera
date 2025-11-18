from ftplib import FTP
from pathlib import Path


class FtpIsDirectory:
    """Utility to check whether a remote FTP path is a directory.

    The method attempts to change the working directory to the provided path.
    If it succeeds, the path is considered a directory. The client's original
    working directory is restored before returning, regardless of the outcome.
    """

    def eval(self, client: FTP, directory: Path) -> bool:
        """Return True if the remote path refers to a directory, else False.

        Args:
            client: A connected and authenticated ftplib.FTP client.
            directory: Remote path to check. Can be absolute or relative.

        Returns:
            True if ``directory`` is a directory on the FTP server, False otherwise.
        """
        # Preserve the original working directory to avoid side effects.
        try:
            original_cwd = client.pwd()
        except Exception:
            # If we cannot determine the current directory, we still try the check
            # without being able to restore state reliably.
            original_cwd = None

            # Try to change into the target directory. If it works, it's a directory.
        try:
            client.cwd(str(directory))
            return True
        except Exception:
            return False
        finally:
            # Restore original working directory when possible.
            if original_cwd is not None:
                try:
                    client.cwd(original_cwd)
                except Exception:
                    # Swallow restoration errors: best effort to not mask result.
                    pass
