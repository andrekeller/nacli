"""naclit statetree module"""
from collections import defaultdict
from pathlib import Path
import yaml
from nacli.git import Repo


class GitRef:
    """a git reference"""

    def __init__(self, name, *, reftype=None):
        self._name = name
        self._reftype = reftype

    def __str__(self):
        return "{}: {}".format(self._reftype.capitalize(), self.name)

    @property
    def name(self):
        """returns the name of a git reference"""
        return self._name

    @property
    def reftype(self):
        """returns the type of a git reference"""
        return self._reftype


class GitBranch(GitRef):
    """a git branch"""

    def __init__(self, name):
        super().__init__(name, reftype='branch')


class GitCommit(GitRef):
    """a git commit"""

    def __init__(self, name):
        super().__init__(name, reftype='commit')


class GitTag(GitRef):
    """a git tag"""

    def __init__(self, name):
        super().__init__(name, reftype='tag')


class StateParseError(Exception):
    """state file could not be parsed"""


class State:
    """a salt state"""

    def __init__(self, name, *, url, ref=None):
        self._name = name
        self._url = url
        self._ref = ref

    def __repr__(self):
        state = "{} ({})".format(self._name, self._url)
        if self._ref is not None:
            state = "{} [{}]".format(state, self._ref)
        return state

    def __hash__(self):
        return hash(str(self))

    def __lt__(self, other):
        return str(other) > str(self)

    @property
    def name(self):
        """returns the name of a salt state"""
        return self._name

    @property
    def url(self):
        """returns the repository url of a salt state"""
        return self._url

    @property
    def ref(self):
        """returns the git repository reference of a salt state"""
        return self._ref

    def as_dict(self, verify_refs=True):
        """returns yaml representation of the state"""
        if verify_refs:
            with Repo(url=self.url) as state_repo:
                try:
                    validators = {
                        'branch': state_repo.validate_branch,
                        'commit': state_repo.validate_commit,
                        'tag': state_repo.validate_tag,
                    }
                    validators[self.ref.reftype](self.ref.name)
                except AttributeError:
                    pass
        try:
            return {
                self.name: {
                    'url': self.url,
                    self.ref.reftype: self.ref.name,
                }
            }
        except AttributeError:
            return {self.name: self.url}


class StateTreeRepo(Repo):
    """a git repository representing a salt state tree"""

    def __init__(self, url):
        self._environments = defaultdict(list)
        super().__init__(url)
        self._scan()

    @staticmethod
    def _verify_state(state):
        """verifies if a state entry in states.yaml is syntactically valid."""
        _state_options = {'branch', 'commit', 'tag', 'url'}
        print(state)
        if len(state) != 1:
            raise StateParseError('State should have options grouped under a '
                                  'single key, not {}'
                                  .format(','.join(state.keys())))
        state_name, state_options = state.popitem()
        if not isinstance(state_options, (str, dict)):
            raise StateParseError('State {} options should be passed as str or'
                                  ' dict, not {}'
                                  .format(state_name,
                                          type(state_options).__name__))
        if isinstance(state_options, dict):
            invalid_keys = set(state_options.keys()).difference(_state_options)
            if invalid_keys:
                raise StateParseError('State {} invalid options: {}'
                                      .format(state_name, invalid_keys))
            try:
                url = state_options.pop('url')
            except KeyError:
                raise StateParseError('State {} missing mandatory option "url"'
                                      .format(state_name)) from None
            if len(state_options) > 1:
                raise StateParseError('State {} more than one of "commit", '
                                      '"tag" or "branch" specified: "{}"'
                                      .format(state_name,
                                              '", "'.join(state_options)))
            if 'branch' in state_options:
                ref = GitBranch(state_options.get('branch'))
            elif 'commit' in state_options:
                ref = GitCommit(state_options.get('commit'))
            elif 'tag' in state_options:
                ref = GitTag(state_options.get('tag'))
            else:
                ref = None
        else:
            url = state_options
            ref = None
        return State(state_name, url=url, ref=ref)

    def _scan(self):
        """scans the state tree repository.

        This will walk through all branches, parses its states.yaml and store
        the information in this StateTreeRepo object
        """

        for branch in self.branches:
            self.git('checkout', branch)
            try:
                with open(Path(self._workdir, 'states.yaml')) as states:
                    for state in yaml.safe_load(states):
                        self._environments[branch].append(self._verify_state(state))

            except yaml.YAMLError as exc:
                raise StateParseError('Could no parse states.yaml for branch'
                                      ' {}: {}'
                                      .format(branch, exc)) from None
            except FileNotFoundError:
                continue

    def yaml(self, environment):
        """returns yaml representaion of environment"""
        _yaml = {}
        for state in sorted(self._environments[environment]):
            _yaml.update(state.as_dict())

        return yaml.safe_dump(_yaml, default_flow_style=False)
