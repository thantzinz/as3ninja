# -*- coding: utf-8 -*-
"""Gitget provides a minimal interface to 'git' to clone a repository with a specific branch, tag or commit id."""
import shlex
import shutil
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError, SubprocessError, TimeoutExpired, run
from tempfile import mkdtemp
from typing import Optional, Union

from .settings import NINJASETTINGS

__all__ = ["Gitget", "GitgetException"]


class GitgetException(SubprocessError):
    """Gitget Exception, subclassed SubprocessError Exception"""


class Gitget:
    """Gitget context manager clones a git repoistory. Raises GitgetException on failure.
        Exports:
        `info` dict property with information about the cloned repository
        `repodir` str property with the filesystem path to the temporary directory
        Gitget creates a shall clone of the specified repository using the specified and optional depth.
        A branch can be selected, if not specified the git server default branch is used (usually master).

        A specific commit id in long format can be selected, depth can be used to reach back into the past in case the commit id isn't available through a shallow clone.

            :param repository: Git Repository URL.
            :param depth: Optional. Depth to clone. (Default value = 1)
            :param branch: Optional. Branch or Tag to clone. If None, default remote branch will be cloned. (Default value = None)
            :param commit: Optional. Commit ID (long format!) (Default value = None)
            :param repodir: Optional. Target directory for repositroy. This directory will persist on disk, Gitget will not remove it for you. (Default value = None)
            :param force: Optional. Forces removal of an existing repodir before cloning (use with care). (Default value = False)
    """

    def __init__(
        self,
        repository: str,
        depth: int = 1,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
        repodir: Optional[str] = None,
        force: bool = False,
    ):
        if depth < 0:
            raise ValueError("depth must be 0 or a positive number.")
        if commit and len(commit) < 40:
            raise ValueError(
                "commit id is too short. full commit id is required, abreviated (7 char) format is not supported."
            )
        self._depth = depth
        self._branch = branch
        self._commit = commit
        self._repo = repository
        self._repodir = repodir
        if repodir:
            self._repodir_perist = True
        else:
            self._repodir = str(mkdtemp(suffix=".ninja.git"))
            self._repodir_perist = False
        self._force = force
        self._gitlog: dict = {"branch": self._branch, "commit": {}, "author": {}}
        self._gitcmd = [
            "git",
            "-c",
            f"http.sslVerify={NINJASETTINGS.GITGET_SSL_VERIFY}",
            "-c",
            f"http.proxy={NINJASETTINGS.GITGET_PROXY}",
        ]

    def __enter__(self):
        _repodir = Path(self._repodir)
        if _repodir.exists() and self._force:
            # git clone aborts if a directory exists and is not empty. recursively remove existing directory if _force is True.
            shutil.rmtree(_repodir)
        _repodir.mkdir(mode=0o700, parents=True, exist_ok=True)

        self._clone()
        if self._commit:
            self._checkout_commit()
        self._get_gitlog()

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if not self._repodir_perist:
            shutil.rmtree(path=self._repodir)

    def rmrepodir(self) -> None:
        """Method: Removes the repodir.

        This method is useful if repodir has been specified in :meth:`__init__`.
        """
        if Path(self._repodir).exists():
            shutil.rmtree(Path(self._repodir))

    @property
    def info(self) -> dict:
        """Property: returns dict with git log information"""
        return self._gitlog

    @property
    def repodir(self) -> str:
        """Property: returns the (temporary) directory of the repository"""
        return self._repodir

    @staticmethod
    def _datetime_format(epoch: Union[int, str]) -> str:
        """Private Method: returns a human readable UTC format (%Y-%m-%dT%H:%M:%SZ) of the unix epoch

        :param epoch: Unixt epoch
        """
        return datetime.utcfromtimestamp(int(epoch)).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _sh_quote(arg) -> str:
        """Private Method: returns a shell escaped version of arg, where arg can by any type convertible to str. uses shlex.quote

            :param arg: Argument to pass to `shlex.quote`
        """
        return shlex.quote(str(arg))

    def _clone(self):
        """Private Method: clones git repository"""
        self._run_command(
            [
                "clone",
                self._depth and "--depth" or None,
                self._depth and self._sh_quote(self._depth) or None,
                self._branch and "--branch" or None,
                self._branch and self._sh_quote(self._branch) or None,
                self._sh_quote(self._repo),
                self._sh_quote(self._repodir),
            ]
        )

    def _checkout_commit(self):
        """Private Method: checks out specific commit id

        Note: short ID (example: 2b54d17) is not allowed, must be the long commit id
        Note: when the commit is far back in the past, the remote server might not allow fetching it directly.
        In that case the depth parameter must be specified and the depth must include the commit id
        otherwise the following error occurs:
        error: Server does not allow request for unadvertised object ...comitid...
        """
        self._run_command(
            ["fetch", "--depth", "1", "origin", self._sh_quote(self._commit)]
        )
        self._run_command(["checkout", self._sh_quote(self._commit)])

    def _get_gitlog(self) -> None:
        """Private Method: parses the git log to a dict"""
        # git log -n 1 --pretty=commit_id:%H%nauthor:%an%nauthor_email:%aE%nauthor_date:%at%ncommit_date:%ct%ncommit_subject:%s
        result = self._run_command(
            ["log", "-n", "1", "--pretty=%H%n%ct%n%s%n%an%n%aE%n%at"]
        )
        (
            self._gitlog["commit"]["id"],
            self._gitlog["commit"]["epoch"],
            self._gitlog["commit"]["subject"],
            self._gitlog["author"]["name"],
            self._gitlog["author"]["email"],
            self._gitlog["author"]["epoch"],
        ) = result.splitlines(keepends=False)

        self._gitlog["commit"]["id_short"] = self._gitlog["commit"]["id"][0:7]
        self._gitlog["commit"]["date"] = self._datetime_format(
            self._gitlog["commit"]["epoch"]
        )
        self._gitlog["author"]["date"] = self._datetime_format(
            int(self._gitlog["author"]["epoch"])
        )
        if not self._branch:
            # git branch --show-current
            result = self._run_command(["branch", "--show-current"])
            self._gitlog["branch"] = result.rstrip()

    def _run_command(self, cmd: list) -> str:
        """Private Method: runs a shell command and handles/raises exceptions based on the command return code

            :param cmd: list of command + argmunets
        """
        result = None
        try:
            # exclude None types from command
            cmd = [command for command in cmd if command]
            result = run(
                self._gitcmd + cmd,
                cwd=self._repodir,
                capture_output=True,
                timeout=NINJASETTINGS.GITGET_TIMEOUT,
            )
            result.check_returncode()
        except (TimeoutExpired, CalledProcessError) as exc:
            if isinstance(exc, CalledProcessError):
                _exception = "CalledProcessError"
                _stderr = result.stderr.decode("utf8")
                _stderr = _stderr.replace("\n", "\\n")
            elif isinstance(exc, TimeoutExpired):
                _exception = "TimeoutExpired"
                _stderr = str(exc.stderr.decode("utf8"))

            raise GitgetException(
                f"Gitget failed due to exception:{_exception}, STDERR: {_stderr}"
            )
        return result.stdout.decode("utf8")
