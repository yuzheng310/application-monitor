"""A nonblocking process lock, shared by the web server and scanner."""
import os
if os.name == "nt":
    import msvcrt
else:
    import fcntl


def acquire(file):
    if os.name == "nt":
        file.seek(0, 2)
        if file.tell() == 0:
            file.write("\0")
            file.flush()
        file.seek(0)
        try:
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise BlockingIOError("已有进程持有锁") from error
    else:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
