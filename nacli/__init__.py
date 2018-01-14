"""nacli"""
import logging
from nacli.statetree import StateTreeRepo
LOG = logging.getLogger(__name__)


def main():
    """nacli main entrypoint"""
    logging.basicConfig(level=logging.DEBUG)

    repo = StateTreeRepo(url='ssh://git@git.0x2a.io:10022/arst/nacli-control.git')
    from pprint import pprint
    pprint(repo.yaml('base'))
