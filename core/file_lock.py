"""One-byte OS locks shared by cooperating file writers."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat


@contextmanager
def exclusive(path: Path):
    path = Path(path)
    if path.exists() and (not path.is_file() or path.is_symlink() or path.stat().st_size > 1):
        raise RuntimeError(f'The operation lock is not a one-byte regular file: {path.name}')
    descriptor = os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1:
            raise RuntimeError(f'The operation lock is invalid: {path.name}')
        if not info.st_size:
            os.write(descriptor,b'0')
        os.lseek(descriptor,0,os.SEEK_SET)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(descriptor,msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:
        # Keep the path: every process must lock the same inode.
        os.close(descriptor)
