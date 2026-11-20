"""Prevent concurrent experiment runners from resetting the same project labs."""
import fcntl
from pathlib import Path

def acquire(root):
    path=Path(root)/'runs/experiment.lock';path.parent.mkdir(exist_ok=True)
    try:handle=path.open('a+')
    except PermissionError:
        # A terminal-sudo run may own the existing lock. Linux flock also
        # supports a read-only descriptor; do not chmod or replace the inode.
        handle=path.open('r')
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close();raise RuntimeError('Another experiment/reference runner holds the project lab lock')
    return handle
