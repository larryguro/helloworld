import argparse
import atexit
import ctypes
import ctypes.wintypes
import os
import signal
import struct
import sys
import threading


kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.LoadLibraryW.restype = ctypes.wintypes.HMODULE
kernel32.LoadLibraryW.argtypes = [ctypes.wintypes.LPCWSTR]
kernel32.FreeLibrary.restype = ctypes.wintypes.BOOL
kernel32.FreeLibrary.argtypes = [ctypes.wintypes.HMODULE]


MACHINE_NAMES = {
    0x014c: "32-bit",   # IMAGE_FILE_MACHINE_I386
    0x8664: "64-bit",   # IMAGE_FILE_MACHINE_AMD64
    0xAA64: "64-bit",   # IMAGE_FILE_MACHINE_ARM64
    0x01c4: "32-bit",   # IMAGE_FILE_MACHINE_ARMNT
}


def get_dll_arch(path):
    """PE 헤더에서 DLL 아키텍처를 반환. 파싱 실패 시 None."""
    try:
        with open(path, 'rb') as f:
            if f.read(2) != b'MZ':
                return None
            f.seek(0x3C)
            pe_offset = struct.unpack('<I', f.read(4))[0]
            f.seek(pe_offset)
            if f.read(4) != b'PE\x00\x00':
                return None
            machine = struct.unpack('<H', f.read(2))[0]
        return MACHINE_NAMES.get(machine)
    except OSError:
        return None


_handle = None


def unload_dll():
    global _handle
    if _handle is not None:
        kernel32.FreeLibrary(_handle)
        _handle = None
        print("DLL unloaded.")


atexit.register(unload_dll)


def main():
    global _handle

    parser = argparse.ArgumentParser(
        description="Load a DLL and keep it loaded until Enter or Ctrl+C."
    )
    parser.add_argument("dll_path", help="Path to the DLL file to load")
    args = parser.parse_args()

    dll_path = os.path.abspath(args.dll_path)

    if not os.path.isfile(dll_path):
        print(f"Error: File not found: {dll_path}", file=sys.stderr)
        sys.exit(1)

    dll_arch = get_dll_arch(dll_path)
    proc_arch = "64-bit" if sys.maxsize > 2**32 else "32-bit"
    if dll_arch and dll_arch != proc_arch:
        print(f"Error: Architecture mismatch.", file=sys.stderr)
        print(f"  DLL:     {dll_arch}  ({dll_path})", file=sys.stderr)
        print(f"  Process: {proc_arch}", file=sys.stderr)
        print(f"  -> Use a {dll_arch} Python/executable to load this DLL.", file=sys.stderr)
        sys.exit(2)

    handle = kernel32.LoadLibraryW(dll_path)
    if not handle:
        err = ctypes.get_last_error()
        msg = ctypes.FormatError(err)
        print(f"Error: LoadLibraryW failed (code {err}): {msg}", file=sys.stderr)
        sys.exit(2)

    _handle = handle
    print(f"Loaded: {dll_path}")
    print(f"Handle: 0x{handle:016X}")
    print("Press Enter or Ctrl+C to unload and exit...")

    done = threading.Event()

    def signal_handler(sig, frame):
        done.set()

    signal.signal(signal.SIGINT, signal_handler)
    try:
        signal.signal(signal.SIGBREAK, signal_handler)
    except AttributeError:
        pass

    def wait_for_enter():
        try:
            input()
        except (EOFError, OSError):
            pass
        done.set()

    t = threading.Thread(target=wait_for_enter, daemon=True)
    t.start()

    done.wait()
    unload_dll()


if __name__ == "__main__":
    main()
