"""Read a .nup package (a decrypted Switch 2 dump: titles, each with an exefs/ and a romfs/ tree) and extract it.

    python -I nx2/nup.py <file.nup>                      list the titles and their trees
    python -I nx2/nup.py <file.nup> --extract <dir> [--title <n|version>] [--only exefs|romfs]

The layout (worked out from the file; little-endian):
    0x000  "NUP\\x01" header, u64 file size at +0x40
    0x080  "TOC\\x01", u32 titles, u64 dirs, u64 files, u64 strings offset (from 0x80), u64 strings size
    0x0b0  titles, 0x40 each: u64 title id, u32 root dir, u32 exefs dir, u32 romfs dir, u32 version, ...,
           u64 offset + u64 size of the title's metadata blob at +0x20
    then   dirs, 24 bytes each: u32 name offset, u32 name length, u32 first child, u32 children, u64 0
    then   files, 80 bytes each: u32 name offset, u32 name length, u64 size, u64 data offset, u64 size again,
           32-byte hash, 16 bytes 0
    then   the child list, u32 each: a node index; below the dir count a dir, else (index - dirs) a file
    then   the name strings (not 0-terminated)
File data is stored as is, or wrapped in a Zstandard frame by newer dumpers. Native game .zs frames must remain compressed.
"""
import argparse
import concurrent.futures
import copy
import io
import ntpath
import os
import shutil
import struct
import sys
import tempfile
import threading
from pathlib import Path, PurePosixPath, PureWindowsPath


ZSTD = b"\x28\xb5\x2f\xfd"


def extended_windows_path(path):
    """Normalize before opting into Win32 Unicode paths (including UNC shares)."""
    path = ntpath.abspath(os.fsdecode(path))
    if path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def filesystem_path(path):
    return extended_windows_path(path) if os.name == "nt" else os.fspath(path)


def write_new_entry(nup, record, destination, name="", packed=None):
    """(0.4.5) An entry whose file does not exist yet, written under its own name: the temp name and the rename cost a
    third of the extraction on Windows (12 thousand files: 6.6 s of renames in 37 s). Exclusive creation, so an existing
    file is never touched; on failure the partial file is removed. A file cut short by a killed process has the wrong
    size, and the next extraction rewrites it (a fresh extraction goes to a stage folder used only when complete)."""
    destination = filesystem_path(destination)
    try:
        stream = create_new(destination)
    except FileExistsError:
        return write_entry(nup, record, destination, name, packed=packed)
    except OSError as error:
        raise entry_error(error, destination) from error
    try:
        with stream:
            nup.copy_to(record, stream, name, packed=packed)
    except BaseException as error:
        try:
            os.unlink(destination)
        except OSError:
            pass
        if isinstance(error, OSError):
            raise entry_error(error, destination) from error
        raise


def create_new(destination):
    return open(destination, "xb")


def entry_error(error, destination):
    parent = os.path.dirname(destination)
    units = len(destination.encode("utf-16-le", errors="surrogatepass")) // 2
    detail = ("Falha ao gravar entrada NUP; "
              f"diretorio pai existe={os.path.isdir(parent)}, caminho={units} unidades UTF-16, "
              f"winerror={getattr(error, 'winerror', None)}. "
              "Confira a disponibilidade da unidade e o acesso a pasta. "
              "A entrada original e os objetos compilados nao foram removidos. "
              f"Erro original: {error}")
    return OSError(error.errno, detail, destination)


def write_entry(nup, record, destination, name="", packed=None):
    """Publish only a complete entry, using a short, exclusively owned temp name."""
    destination = filesystem_path(destination)
    parent = os.path.dirname(destination)
    temporary = None
    descriptor = None
    try:
        os.makedirs(parent, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".nup-", suffix=".part", dir=parent)
        stream = os.fdopen(descriptor, "wb")
        descriptor = None
        with stream:
            nup.copy_to(record, stream, name, packed=packed)
        os.replace(temporary, destination)
        temporary = None
    except OSError as error:
        raise entry_error(error, destination) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError as error:
                print(f"Nao foi possivel remover o temporario desta entrada: {temporary}: {error}",
                      file=sys.stderr)


def frame_content_size(head):
    if len(head) < 5 or head[:4] != ZSTD:
        return None
    descriptor = head[4]
    single = (descriptor >> 5) & 1
    at = 5 + (0 if single else 1) + (0, 1, 2, 4)[descriptor & 3]
    count = (1 if single else 0, 2, 4, 8)[descriptor >> 6]
    if not count or len(head) < at + count:
        return None
    size = int.from_bytes(head[at:at + count], "little")
    return size + 256 if count == 2 else size


def zstd_module():
    try:
        import zstandard
    except ImportError:
        raise SystemExit("zstandard nao foi encontrado. Aplique a atualizacao completa das dependencias.") from None
    return zstandard


class Nup:
    def __init__(self, path):
        self.path = path
        self.f = open(filesystem_path(path), "rb")
        try:
            self._read_metadata()
        except BaseException:
            self.f.close()
            raise

    def _read_metadata(self):
        h = self.f.read(0x80)
        if h[:4] != b"NUP\x01":
            raise SystemExit("%s: not a NUP package (magic %r)" % (self.path, h[:4]))
        self.file_size = struct.unpack_from("<Q", h, 0x40)[0]
        t = self.f.read(0x30)
        if t[:4] != b"TOC\x01":
            raise SystemExit("%s: no TOC at 0x80" % self.path)
        nt, nd, nf, soff, ssz = struct.unpack_from("<IQQQQ", t, 4)
        self.nd, self.nf = nd, nf
        dirs_at = 0x80 + 0x30 + 0x40 * nt
        files_at = dirs_at + 24 * nd
        kids_at = files_at + 80 * nf
        strings_at = 0x80 + soff
        size = os.fstat(self.f.fileno()).st_size
        if not nt or strings_at < kids_at or strings_at + ssz > size or (strings_at - kids_at) % 4:
            raise ValueError("invalid NUP metadata bounds")
        self.f.seek(0)
        meta = self.f.read(strings_at + ssz)
        self.strings = meta[strings_at:strings_at + ssz]
        self.titles = []
        for i in range(nt):
            o = 0xb0 + 0x40 * i
            tid, root, exefs, romfs, ver = struct.unpack_from("<QIIII", meta, o)
            self.titles.append(dict(index=i, id=tid, root=root, exefs=exefs, romfs=romfs, version=ver))
        self.dirs = [struct.unpack_from("<4I", meta, dirs_at + 24 * i) for i in range(nd)]
        self.files = []
        for i in range(nf):
            no, nl, size, off, size2 = struct.unpack_from("<IIQQQ", meta, files_at + 80 * i)
            self.files.append((no, nl, size, off, size2))
        nk = (strings_at - kids_at) // 4
        self.kids = struct.unpack_from("<%dI" % nk, meta, kids_at)

    def name(self, off, n):
        return self.strings[off:off + n].decode("utf-8")

    def walk(self, d, prefix=""):
        """(relative path, file record) for every file under dir d."""
        no, nl, first, n = self.dirs[d]
        for k in self.kids[first:first + n]:
            if k < self.nd:
                cno, cnl = self.dirs[k][:2]
                yield from self.walk(k, prefix + self.name(cno, cnl) + "/")
            else:
                r = self.files[k - self.nd]
                yield prefix + self.name(r[0], r[1]), r

    def _unpacked_blocks(self, r):
        zstandard = zstd_module()
        decoder = zstandard.ZstdDecompressor().decompressobj()
        self.f.seek(r[3])
        left = min(os.fstat(self.f.fileno()).st_size - r[3], r[2] + (1 << 16))
        while left > 0 and not decoder.eof:
            data = self.f.read(min(left, 1 << 16))
            if not data:
                break
            left -= len(data)
            try:
                block = decoder.decompress(data)
            except zstandard.ZstdError as error:
                raise ValueError("invalid compressed NUP entry: %s" % error) from error
            yield block
        if not decoder.eof:
            raise ValueError("truncated compressed NUP entry")

    def is_packed(self, r, name=""):
        self.f.seek(r[3])
        head = self.f.read(18)
        if head[:4] != ZSTD:
            return False
        stated = frame_content_size(head)
        if stated is not None and stated != r[2]:
            return False
        # .zs is already compressed in the game. Only remove an outer wrapper
        # when the result is itself a .zs frame of the listed file size.
        if stated is None or name.endswith(".zs"):
            total, prefix = 0, b""
            try:
                for block in self._unpacked_blocks(r):
                    total += len(block)
                    prefix = (prefix + block[:4])[:4]
                    if total > r[2]:
                        return False
            except ValueError:
                return False
            return total == r[2] and (not name.endswith(".zs") or prefix == ZSTD)
        return True

    def reopen(self):
        """The same archive on a handle of its own (one per extraction thread: seek and read share the position)"""
        other = copy.copy(self)
        other.f = open(filesystem_path(self.path), "rb")
        return other

    def _copy_if_packed(self, r, target, name):
        """is_packed and the unwrapping copy in one pass (0.4.5: a .zs, or a frame without its size, was decompressed
        twice, once to check it and once to write it). Writes the file and returns True, or returns False with target as it
        was. A wrapper of the stated size that fails raises, as copy_to does."""
        self.f.seek(r[3])
        head = self.f.read(18)
        if head[:4] != ZSTD:
            return False
        stated = frame_content_size(head)
        if stated is not None and stated != r[2]:
            return False
        verify = stated is None or name.endswith(".zs")
        start = target.tell()
        total, prefix, fits = 0, b"", True
        try:
            for block in self._unpacked_blocks(r):
                total += len(block)
                if total > r[2]:
                    if not verify:
                        raise ValueError("compressed NUP entry exceeds its declared size")
                    fits = False
                    break
                prefix = (prefix + block[:4])[:4]
                target.write(block)
        except ValueError:
            if not verify:
                raise
            fits = False
        if not verify:
            if total != r[2]:
                raise ValueError("compressed NUP entry: %d bytes, expected %d" % (total, r[2]))
            return True
        if fits and total == r[2] and (not name.endswith(".zs") or prefix == ZSTD):
            return True
        target.seek(start)
        target.truncate()
        return False

    def copy_to(self, r, target, name="", packed=None):
        if packed is None:
            if self._copy_if_packed(r, target, name):
                return
            packed = False
        if packed:
            total = 0
            for block in self._unpacked_blocks(r):
                total += len(block)
                if total > r[2]:
                    raise ValueError("compressed NUP entry exceeds its declared size")
                target.write(block)
            if total != r[2]:
                raise ValueError("compressed NUP entry: %d bytes, expected %d" % (total, r[2]))
            return
        self.f.seek(r[3])
        left = r[2]
        while left:
            block = self.f.read(min(left, 8 << 20))
            if not block:
                raise ValueError("short read in NUP entry")
            target.write(block)
            left -= len(block)

    def read(self, r, n=None):
        if not self.is_packed(r):
            self.f.seek(r[3])
            return self.f.read(r[2] if n is None else min(n, r[2]))
        target = io.BytesIO()
        self.copy_to(r, target, packed=True)
        value = target.getvalue()
        return value if n is None else value[:n]


def pick_title(nup, want):
    if want is None:
        return max(nup.titles, key=lambda t: t["version"])   # (the newest: the update over the base)
    for t in nup.titles:
        if str(t["index"]) == want or str(t["version"]) == want or "%016x" % t["id"] == want.lower():
            return t
    raise SystemExit("no title %s" % want)


def extract_workers():
    """Threads for extract. One by default: measured on the 3500X's SATA SSD, threads writing into the same folders made it
    slower (6000 compressed files of one folder: 3.9 s on one thread, 21.5 s on three, 52.7 s on six); the speed of 0.4.5
    comes from the direct write and the single decompression. NUP_WORKERS=n: n threads, each with its own handle."""
    wanted = os.environ.get("NUP_WORKERS", "")
    if wanted.isdigit() and int(wanted) > 0:
        return min(16, int(wanted))
    return 1


def extract(nup, t, out, only=None, quiet=False, workers=None):
    entries = []
    for part in ("exefs", "romfs"):
        if only and part != only:
            continue
        root = Path(filesystem_path(Path(out, part))).resolve()
        folders = {}
        for rel, r in nup.walk(t[part]):
            relative = PurePosixPath(rel)
            windows = PureWindowsPath(rel)
            if relative.is_absolute() or windows.drive or windows.root or "\\" in rel or any(
                    component in ("", ".", "..") or ":" in component for component in rel.split("/")):
                raise SystemExit("invalid archive path: %r" % rel)
            # (0.4.5) resolved once a folder, not once a file (a tenth of the time); the file itself is checked by
            # write_new_entry's exclusive creation and write_entry's resolve of an existing name
            parts = relative.parts
            folder = folders.get(parts[:-1])
            if folder is None:
                folder = root.joinpath(*parts[:-1]).resolve() if parts[:-1] else root
                folders[parts[:-1]] = folder
            destination = folder / parts[-1]
            if root != folder and root not in folder.parents:
                raise SystemExit("archive path leaves output: %r" % rel)
            entries.append((rel, r, filesystem_path(destination)))
    # (0.4.5) the folders first, then the files (NUP_WORKERS > 1: on several threads, each with its own handle)
    for parent in sorted({os.path.dirname(dst) for _, _, dst in entries}):
        os.makedirs(parent, exist_ok=True)
    workers = extract_workers() if workers is None else max(1, workers)
    if not hasattr(nup, "reopen"):   # (a reader without its own handles: one thread)
        workers = 1
    local = threading.local()
    readers = []
    lock = threading.Lock()
    done = {"n": 0, "total": 0}

    def reader():
        own = getattr(local, "nup", None)
        if own is None:
            own = nup if workers == 1 else nup.reopen()
            local.nup = own
            with lock:
                readers.append(own)
        return own

    def one(entry):
        rel, r, dst = entry
        archive = reader()
        packed = None
        if os.path.lexists(dst):
            if os.path.islink(dst) or not os.path.isfile(dst):
                raise SystemExit("archive path is not a plain file in the output: %r" % rel)
            if os.path.getsize(dst) == r[2]:
                packed = archive.is_packed(r, rel)
                if not packed:
                    return      # packed files from the older reader may have the right size but wrong bytes
            write_entry(archive, r, dst, rel, packed=packed)
        else:
            write_new_entry(archive, r, dst, rel)
        with lock:
            done["n"] += 1
            done["total"] += r[2]
            if not quiet and done["n"] % 5000 == 0:
                print("  %d files, %.1f GB" % (done["n"], done["total"] / 1e9), flush=True)

    try:
        if workers == 1:
            for entry in entries:
                one(entry)
        else:
            with concurrent.futures.ThreadPoolExecutor(workers) as pool:
                pending = set()
                for entry in entries:     # (a bounded window: 186 thousand futures at once is memory for nothing)
                    pending.add(pool.submit(one, entry))
                    if len(pending) >= workers * 64:
                        finished, pending = concurrent.futures.wait(
                            pending, return_when=concurrent.futures.FIRST_COMPLETED)
                        for future in finished:
                            future.result()
                for future in concurrent.futures.as_completed(pending):
                    future.result()
    finally:
        for own in readers:
            if own is not nup:
                own.f.close()
    return done["n"], done["total"]


def heal(nup, selected, exefs, names):
    exefs = filesystem_path(exefs)
    for name in names:
        path = os.path.join(exefs, name)
        if os.path.exists(path):
            with open(path, "rb") as source:
                if source.read(4) == b"NSO0":
                    continue
        for other in reversed(nup.titles):
            if other["index"] == selected["index"]:
                continue
            candidate = next((record for relative, record in nup.walk(other["exefs"]) if relative == name), None)
            if candidate is not None and nup.read(candidate, 4) == b"NSO0":
                write_entry(nup, candidate, path, name)
                print("  %s: taken from title %d (v%d)" % (name, other["index"], other["version"]))
                break


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("nup")
    ap.add_argument("--extract", metavar="DIR")
    ap.add_argument("--title", help="index, version or title id (default: the newest)")
    ap.add_argument("--only", choices=("exefs", "romfs"))
    a = ap.parse_args()
    nup = Nup(a.nup)
    print("%s: %.2f GB, %d titles, %d dirs, %d files" % (os.path.basename(a.nup), nup.file_size / 1e9,
                                                          len(nup.titles), nup.nd, nup.nf))
    for t in nup.titles:
        ex = list(nup.walk(t["exefs"]))
        ro = list(nup.walk(t["romfs"]))
        print("title %d: %016x v%d  exefs %d files (%s)  romfs %d files, %.2f GB" % (
            t["index"], t["id"], t["version"], len(ex), ", ".join("%s %d" % (p, r[2]) for p, r in ex),
            len(ro), sum(r[2] for _, r in ro) / 1e9))
        same = sum(1 for _, r in ro if r[2] != r[4])
        if same:
            print("  (%d romfs files with two different sizes)" % same)
    if a.extract:
        t = pick_title(nup, a.title)
        free = shutil.disk_usage(filesystem_path(os.path.dirname(os.path.abspath(a.extract)) or ".")).free
        print("extracting title %d (v%d) to %s (%.0f GB free)" % (t["index"], t["version"], a.extract, free / 1e9))
        n, total = extract(nup, t, a.extract, a.only)
        print("done: %d files written, %.2f GB" % (n, total / 1e9))
        if a.only != "romfs":   # (main is ZBIC-compressed on firmware 22+: made a plain NSO for the tools)
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import unpack
            heal(nup, t, os.path.join(a.extract, "exefs"), unpack.NAMES)
            for m in unpack.NAMES:
                p = filesystem_path(os.path.join(a.extract, "exefs", m))
                if os.path.exists(p) and unpack.unpack_nso(p):
                    print("  %s: ZBIC -> plain NSO" % m)


if __name__ == "__main__":
    sys.exit(main())
