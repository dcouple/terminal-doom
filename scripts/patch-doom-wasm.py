"""Patch a cloudflare/doom-wasm checkout so it builds for terminal-doom.

The port was written against emscripten 2.x in 2021. Four small edits carry it
forward and drop the pieces a terminal does not want.
"""
import re
import sys

src = sys.argv[1]


def edit(path, fn):
    full = f"{src}/{path}"
    before = open(full).read()
    after = fn(before)
    if after == before:
        sys.exit(f"patch-doom-wasm: {path} was already in the expected state, refusing to guess")
    open(full, "w").write(after)


# 1. Drop the "websockets-" program prefix, so the build lands on doom.js and
#    doom.wasm and the page can reference them by an obvious name.
# 2. EXTRA_EXPORTED_RUNTIME_METHODS has been renamed, and callMain now has to be
#    exported by name — the page starts the game itself, after preloading the
#    wad into the emscripten filesystem.
# 3. SAFE_HEAP, the stack checks and the source map are development aids. They
#    cost frame rate and about 20 MB of artifact, and a terminal wants neither.
# 4. Memory growth on, so a wad bigger than the shareware one still loads.
EMFLAGS = (
    "-s INVOKE_RUN=1 -s USE_SDL=2 -s USE_SDL_MIXER=2 -s LEGACY_GL_EMULATION=0 "
    "-s USE_SDL_NET=2 -s ASSERTIONS=0 -s WASM=1 -s ALLOW_MEMORY_GROWTH=1 "
    # m4 strips one level of square brackets, so the list is doubled exactly as
    # the flag it replaces was.
    "-s FORCE_FILESYSTEM=1 -s EXPORTED_RUNTIME_METHODS=[['FS','ccall','callMain']] "
    "-s SAFE_HEAP=0 -s EXIT_RUNTIME=1 -s STACK_OVERFLOW_CHECK=0 "
    "-s PROXY_POSIX_SOCKETS=0 -s USE_PTHREADS=0 -s PROXY_TO_PTHREAD=0 "
    "-s INITIAL_MEMORY=134217728 -s ERROR_ON_UNDEFINED_SYMBOLS=0 -s ASYNCIFY -O3"
)


def configure_ac(text):
    text = text.replace("PROGRAM_PREFIX=${PROGRAM_SPREFIX}-", 'PROGRAM_PREFIX=""')
    text, n = re.subn(r'EMFLAGS="[^"]*"', 'EMFLAGS="%s"' % EMFLAGS, text)
    if n != 1:
        sys.exit("patch-doom-wasm: expected exactly one EMFLAGS assignment, found %d" % n)
    return text


# 5. doomtype.h declares its own boolean as `enum { false, true }`, which no
#    longer compiles once anything upstream of it has pulled in <stdbool.h> —
#    and SDL2's headers now do. The header's own fallback, `typedef bool
#    boolean`, is not a safe substitute: doom memsets whole sprite tables to -1
#    and then tests them against `true`, which is well defined for a four byte
#    enum and not for a one byte _Bool. Read through a _Bool, the -1 sentinel
#    comes back true, and r_things.c aborts the boot with
#    "Sprite TROO frame I has rotations and a rot=0 lump".
#
#    So: keep the width, take the constants from stdbool.
def doomtype_h(text):
    start = text.index("#if defined(__cplusplus) || defined(__bool_true_false_are_defined)")
    end = text.index("#endif\n", text.index("} boolean;", start)) + len("#endif\n")
    return text[:start] + "#include <stdbool.h>\ntypedef int boolean;\n" + text[end:]


edit("configure.ac", configure_ac)
edit("src/doomtype.h", doomtype_h)
print("patch-doom-wasm: configure.ac, src/doomtype.h")
