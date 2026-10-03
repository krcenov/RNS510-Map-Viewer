"""
Real Java decompilation support for `firmware_java_reader.find_class_files()`
output. Auto-provisions whatever it needs on first use (a portable JDK via
the `install-jdk` pip package, and the open-source CFR decompiler jar from
its real GitHub releases) rather than requiring the caller to have a JVM
pre-installed -- consistent with this module's own "don't hardcode assets"
approach: nothing is bundled in this repo, everything is fetched/cached
under the user's own local app-data/cache directory on first real use.

Usage:
    from firmware_java_reader import find_class_files
    from firmware_java_decompile import decompile_class

    classes = find_class_files(data)
    source = decompile_class(classes[0].data)   # -> str, real Java source
"""

import os
import subprocess
import sys
import tempfile
import urllib.request

CFR_VERSION = "0.152"
CFR_URL = f"https://github.com/leibnitz27/cfr/releases/download/{CFR_VERSION}/cfr-{CFR_VERSION}.jar"

_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".rns510_tools_cache")
_CFR_PATH = os.path.join(_CACHE_DIR, f"cfr-{CFR_VERSION}.jar")

_java_bin_cache = None


def _ensure_java() -> str:
    """Return a path to a working `java` executable, installing a portable
    JDK via the `install-jdk` package on first use if none is found."""
    global _java_bin_cache
    if _java_bin_cache and os.path.exists(_java_bin_cache):
        return _java_bin_cache

    # 1. is a `java` already on PATH?
    import shutil
    found = shutil.which("java")
    if found:
        _java_bin_cache = found
        return found

    # 2. fall back to installing a portable JDK (cached under ~/.jdk by the
    #    install-jdk package itself after the first call)
    try:
        import jdk
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "install-jdk"], check=True)
        import jdk

    jdk_dir = jdk.install("11") if not _existing_jdk_dir() else _existing_jdk_dir()
    java_path = os.path.join(jdk_dir, "bin", "java.exe" if os.name == "nt" else "java")
    _java_bin_cache = java_path
    return java_path


def _existing_jdk_dir():
    """Reuse an already-installed portable JDK (from a prior run) instead of
    re-downloading one every time."""
    base = os.path.join(os.path.expanduser("~"), ".jdk")
    if not os.path.isdir(base):
        return None
    candidates = [os.path.join(base, d) for d in os.listdir(base)]
    candidates = [c for c in candidates if os.path.isdir(c)]
    return candidates[0] if candidates else None


def _ensure_cfr() -> str:
    """Return a path to the CFR decompiler jar, downloading it from its
    real GitHub release on first use."""
    if os.path.exists(_CFR_PATH):
        return _CFR_PATH
    os.makedirs(_CACHE_DIR, exist_ok=True)
    urllib.request.urlretrieve(CFR_URL, _CFR_PATH)
    return _CFR_PATH


def decompile_class(class_bytes: bytes, timeout: int = 30) -> str:
    """Decompile a single real class file (as raw bytes, e.g. from
    `firmware_java_reader.ClassFileInfo.data`) to Java source using CFR.
    Returns the real decompiled source text (or CFR's own error text if
    decompilation fails for that specific class -- still returned as a
    string, never raises for a normal decompile failure)."""
    java = _ensure_java()
    cfr = _ensure_cfr()

    with tempfile.TemporaryDirectory() as tmp:
        class_path = os.path.join(tmp, "Decompile.class")
        with open(class_path, "wb") as f:
            f.write(class_bytes)
        result = subprocess.run(
            [java, "-jar", cfr, class_path],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout or result.stderr


if __name__ == "__main__":
    import firmware_java_reader as fjr

    path = sys.argv[1] if len(sys.argv) > 1 else "FHDD6.FLI"
    with open(path, "rb") as f:
        data = f.read()

    classes = fjr.find_class_files(data)
    print(f"found {len(classes)} real class files; decompiling the first one...")
    if classes:
        print(decompile_class(classes[0].data))
