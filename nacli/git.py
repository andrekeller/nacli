"""nacli git module"""
import logging
import os
import re
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

LOG = logging.getLogger(__name__)


class GitError(Exception):
    """exception raised when a git operation fails"""


class Repo:
    """a git repository.

    This class may be used as a context manager. In that case temporary
    directory gets cleaned as soon as you exit the manager.
    """

    def __init__(self, url):
        """create a working copy of a remote git repository"""
        self._url = url
        self._tmpdir = TemporaryDirectory(prefix='nacli_repo_')
        self._workdir = Path(self._tmpdir.name, 'git')

        self.git('clone',
                 '--depth=1',
                 '--quiet',
                 '--no-single-branch',
                 self._url,
                 'git',
                 cwd=self._tmpdir.name)
        LOG.debug('cloned %s into %s', self._url, self._workdir)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        LOG.debug('cleanup temporary directory %s', self._tmpdir.name)
        self._tmpdir.cleanup()

    def git(self, *cmds, **kwargs):
        """execute a git command in the repository"""
        cmds = ('git',) + cmds
        env = kwargs.pop('env', os.environ.copy())
        # disable terminal prompts for git. otherwise git may ask for
        # for username / passwords which would interrupt program flow
        env.update({'GIT_TERMINAL_PROMPT': '0'})
        cwd = kwargs.pop('cwd', self._workdir)
        try:
            # the str is not actually needed, but pycharm's introspection does
            # not realize that universal_newlines parameters will change
            # check_output return value's type to string (as opposed to the
            # default bytes) and issues annoying warnings in subsequent code.
            rval = str(subprocess.check_output(
                cmds,
                stderr=subprocess.STDOUT,
                cwd=cwd,
                env=env,
                universal_newlines=True,
                **kwargs
            ))
            LOG.debug(
                'command "%s" completed with exit code "0" and output: "%s"',
                ' '.join(cmds),
                rval.replace('\n', '; ').strip('; '),
            )
        except subprocess.CalledProcessError as exc:
            raise GitError(
                'command "%s" failed with exit code "%s" and output: "%s"' % (
                    ' '.join(cmds),
                    exc.returncode,
                    exc.output.replace('\n', '; ').strip('; '),
                )
            ) from None
        return rval

    @property
    def branches(self):
        """returns all remote branches of the repository"""
        gitbranches = self.git('branch', '--list', '--all').split('\n')

        re_branch = re.compile(r'\s*remotes/origin/(?P<branch>[^\s]+$)')

        for gitbranch in gitbranches:
            try:
                yield re_branch.match(gitbranch).groupdict()['branch']
            except AttributeError:
                continue

    def validate_branch(self, branch):
        """verify if repository has a specific branch"""
        if not self.git('branch', '--list', '--all', 'origin/{}'.format(branch)):
            raise GitError(
                "Branch {branch} not found for repository {url}".format(
                    branch=branch,
                    url=self._url
                )
            )
        LOG.debug('%s is a valid branch in %s', branch, self._url)

    def validate_tag(self, tag):
        """verify if repository has a specific tag"""
        if not self.git('tag', '--list', tag):
            raise GitError(
                "Tag {tag} not found for repository {url}".format(
                    tag=tag,
                    url=self._url
                )
            )
        LOG.debug('%s is a tag branch in %s', tag, self._url)

    def validate_commit(self, commit):
        """verify if repository has a specific commit"""
        output = self.git('cat-file', '-t', commit).strip()

        if output != 'commit':
            raise GitError(
                "Commit {commit} not found for repository {url}".format(
                    commit=commit,
                    url=self._url
                )
            )
        LOG.debug('%s is a valid commit in %s', commit, self._url)
