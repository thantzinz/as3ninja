# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import mock
import pytest

from as3ninja.gitget import NINJASETTINGS, Gitget, GitgetException
from tests.utils import fixture_tmpdir

# TODO: mock actual git interactions to decrease test time + increase predictability


class Test_Gitget_staticmethods:
    @staticmethod
    def test_datetime_format_returns_string():
        result = Gitget._datetime_format("1234567890")
        assert isinstance(result, str)

    @staticmethod
    def test_datetime_format_string():
        result = Gitget._datetime_format("1234567890")
        assert result == "2009-02-13T23:31:30Z"

    @staticmethod
    def test_datetime_format_int():
        result = Gitget._datetime_format(1234567890)
        assert result == "2009-02-13T23:31:30Z"

    @staticmethod
    def test_sh_quote__no_quote():
        teststring = "abc"
        result = Gitget._sh_quote(teststring)
        assert result == f"{teststring}"

    @staticmethod
    def test_sh_quote__integer():
        teststring = 1234
        result = Gitget._sh_quote(teststring)
        assert result == f"{teststring}"

    @staticmethod
    def test_sh_quote__simple_quote():
        teststring = "a b c"
        result = Gitget._sh_quote(teststring)
        assert result == f"'{teststring}'"

    @staticmethod
    def test_sh_quote__command_injection():
        teststring = "'; ls /; echo"
        result = Gitget._sh_quote(teststring)
        assert result == "''\"'\"'; ls /; echo'"


class Test_Gitget_subprocess_security:
    @staticmethod
    def test_shell_false(mocker):
        """test that subprocess.run is using shell=False"""
        mocked_run = mocker.patch("as3ninja.gitget.run")
        Gitget._run_command(mock.MagicMock(), "ls")
        print(mocked_run.call_args)
        assert "shell=False" in str(mocked_run.call_args)


class Test_Gitget_interface:
    @staticmethod
    def test_Gitget_simple():
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo", branch="master"
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)
            assert gitrepo.info["branch"] == "master"

    @staticmethod
    def test_Gitget_repo_only():
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo"
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)
            assert gitrepo.info["branch"] == "master"

    @staticmethod
    def test_Gitget_tag():
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo",
            branch="tag_v1.0",
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)
            assert gitrepo.info["branch"] == "tag_v1.0"

    @staticmethod
    def test_Gitget_depth0():
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo",
            branch="master",
            depth=0,
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)
            assert gitrepo.info["branch"] == "master"

    @staticmethod
    def test_Gitget_depth_negative():
        with pytest.raises(ValueError) as exception_info:
            with Gitget(
                repository="https://github.com/simonkowallik/as3ninjaDemo",
                branch="master",
                depth=-1,
            ) as gitrepo:
                print(gitrepo.info)

        assert exception_info.type is ValueError

    @staticmethod
    def test_non_existing_repository():
        """test a non-existing repository"""
        with pytest.raises(GitgetException) as exception_info:
            with Gitget(
                repository="https://github.com/repository-does-not-exist"
            ) as gitrepo:
                print(gitrepo.info)

        assert exception_info.type is GitgetException

    @staticmethod
    @pytest.mark.skipif(
        sys.version_info < (3, 7, 5),
        reason="Skipping this test when python version < 3.7.5  as it hangs forever, see: https://bugs.python.org/issue37424",
    )
    @mock.patch.object(NINJASETTINGS, "GITGET_TIMEOUT", 5)
    def test_private_repository():
        """test a private repository requiring authentication.
        This test will prompt for credentials if not authenticated and will run into a timeout.
        """
        with pytest.raises(GitgetException) as exception_info:
            with Gitget(
                repository="https://github.com/simonkowallik/some-private-repository"
            ) as gitrepo:
                print(gitrepo.info)

        assert exception_info.type is GitgetException


class Test_Gitget_specific_commit_id:
    @staticmethod
    def test_full_clone():
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo",
            commit="924f79f8569317d01d1be7d6a77ac8e2b88332ff",
            depth=0,
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)

    @staticmethod
    def test_non_existing_commit():
        with pytest.raises(GitgetException) as exception_info:
            with Gitget(
                repository="https://github.com/simonkowallik/as3ninjaDemo",
                commit=40 * "1",
            ) as gitrepo:
                print(gitrepo.info)

        assert exception_info.type is GitgetException

    @staticmethod
    def test_commit_missing_in_clone():
        with pytest.raises(GitgetException) as exception_info:
            with Gitget(
                repository="https://github.com/simonkowallik/as3ninjaDemo",
                commit="924f79f8569317d01d1be7d6a77ac8e2b88332ff",
                depth=3,
            ) as gitrepo:
                print(gitrepo.info)

        assert exception_info.type is GitgetException

    @staticmethod
    def test_commit_head_tilde():
        """Test HEAD~ works"""
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo", commit="HEAD~"
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)

    @staticmethod
    def test_commit_head_tilde2():
        """Test HEAD~<int> syntax works"""
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo", commit="HEAD~2"
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)

    @staticmethod
    @pytest.mark.skip(reason="as3ninjaDemo needs 20 commits")
    def test_commit_within_depth20():
        """Test that a depth of 20 is used instead of the default depth of 1"""
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo", commit="HEAD~19"
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)


@pytest.mark.usefixtures("fixture_tmpdir")
class Test_Gitget_advanced_interface:
    @staticmethod
    def test_custom_repodir(fixture_tmpdir):
        repodir = fixture_tmpdir
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo",
            branch="master",
            repodir=repodir,
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)
            assert gitrepo.info["branch"] == "master"

        assert Path(repodir).exists()

    @staticmethod
    def test_rmrepodir(fixture_tmpdir):
        repodir = fixture_tmpdir
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo",
            branch="master",
            repodir=repodir,
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)
            assert gitrepo.info["branch"] == "master"
            gitrepo.rmrepodir()

        assert Path(repodir).exists() is False

    @staticmethod
    def test_custom_repodir_2ndclone_force(fixture_tmpdir):
        repodir = fixture_tmpdir
        # first clone
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo",
            branch="master",
            repodir=repodir,
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)
            assert gitrepo.info["branch"] == "master"

        # second clone to existing repo
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo",
            branch="master",
            repodir=repodir,
            force=True,
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)
            assert gitrepo.info["branch"] == "master"

    @staticmethod
    def test_custom_repodir_2ndclone_noforce(fixture_tmpdir):
        repodir = fixture_tmpdir
        # first clone
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo",
            branch="master",
            repodir=repodir,
        ) as gitrepo:
            assert isinstance(gitrepo.info, dict)
            assert gitrepo.info["branch"] == "master"

        # second clone to existing repo without force raises exception
        with pytest.raises(GitgetException) as exception_info:
            with Gitget(
                repository="https://github.com/simonkowallik/as3ninjaDemo",
                branch="master",
                repodir=repodir,
            ) as gitrepo:
                print(gitrepo.info)

        assert exception_info.type is GitgetException


class Test_previous_issues:
    @staticmethod
    def test_dir_exists_on_with():
        with Gitget(
            repository="https://github.com/simonkowallik/as3ninjaDemo"
        ) as gitrepo:
            assert Path(gitrepo.repodir + "/.git").exists()
