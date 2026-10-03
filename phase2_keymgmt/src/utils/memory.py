# phase2_keymgmt/src/utils/memory.py
"""
SIMULATION ONLY — Memory Locking & Zeroization.
REAL HARDWARE (TEE/SE/StrongBox) HANDLES THIS IN SILICON.
This module provides best-effort software mitigation on Linux.
"""
import ctypes
import ctypes.util
import os
import sys
import logging
from contextlib import contextmanager
from typing import Optional, Any, Union

log = logging.getLogger(__name__)

# --- Libc Binding ---
_libc = None
def _get_libc():
    global _libc
    if _libc is None:
        # Find libc
        lib_name = ctypes.util.find_library('c')
        if not lib_name:
            raise OSError("libc not found")
        _libc = ctypes.CDLL(lib_name, use_errno=True)
    return _libc

# Constants
MCL_CURRENT = 1
MCL_FUTURE = 2
MCL_CURRENT_FUTURE = MCL_CURRENT | MCL_FUTURE

def mlock_pages(addr: int, length: int) -> bool:
    """
    Lock physical pages backing virtual address range [addr, addr+length) into RAM.
    Prevents swapping to disk. Requires CAP_IPC_LOCK or RLIMIT_MEMLOCK.
    """
    try:
        libc = _get_libc()
        res = libc.mlock(ctypes.c_void_p(addr), ctypes.c_size_t(length))
        if res != 0:
            errno = ctypes.get_errno()
            log.warning(f"mlock failed (errno={errno}): Keys MAY swap to disk. "
                        f"Run with 'ulimit -l unlimited' or CAP_IPC_LOCK.")
            return False
        return True
    except Exception as e:
        log.warning(f"mlock unavailable: {e}")
        return False

def munlock_pages(addr: int, length: int):
    try:
        libc = _get_libc()
        libc.munlock(ctypes.c_void_p(addr), ctypes.c_size_t(length))
    except Exception:
        pass

def secure_zero(buf: Union[bytearray, memoryview, ctypes.Array]):
    """
    Best-effort compiler-barrier memset.
    In Python, bytearray assignment *usually* works, but CPython optimizer *might* remove it.
    ctypes.memset is the most reliable portable barrier in pure Python/ctypes.
    """
    if isinstance(buf, bytearray):
        addr = ctypes.addressof(ctypes.c_char.from_buffer(buf))
        length = len(buf)
    elif isinstance(buf, memoryview):
        if not buf.contiguous or buf.readonly:
            log.error("secure_zero: memoryview not contiguous or readonly. Fallback to manual loop.")
            buf[:] = b'\x00' * len(buf)
            return
        addr = ctypes.addressof(ctypes.c_char.from_buffer(buf.obj, buf.offset))
        length = buf.nbytes
    elif isinstance(buf, ctypes.Array):
        addr = ctypes.addressof(buf)
        length = ctypes.sizeof(buf)
    else:
        raise TypeError("secure_zero requires bytearray, memoryview, or ctypes Array")

    try:
        libc = _get_libc()
        libc.memset(ctypes.c_void_p(addr), 0, ctypes.c_size_t(length))
    except Exception:
        # Fallback manual zeroization
        for i in range(len(buf)):
            buf[i] = 0

@contextmanager
def secure_buffer(size: int):
    """
    Context manager allocating a locked, zeroized bytearray.
    Yields a bytearray.
    """
    buf = bytearray(size)
    addr = ctypes.addressof(ctypes.c_char.from_buffer(buf))
    
    locked = mlock_pages(addr, size)
    try:
        yield buf
    finally:
        secure_zero(buf)
        if locked:
            munlock_pages(addr, size)
        del buf
