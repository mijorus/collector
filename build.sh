#!/usr/bin/env bash
# Build and install Collector natively with Meson (no Flatpak).
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SOURCE_DIR"

PREFIX="${PREFIX:-$HOME/.local}"
BUILD_DIR="${BUILD_DIR:-build}"
PYTHON="${PYTHON:-python3}"
RUN_TESTS="${RUN_TESTS:-1}"
SMOKE_TEST="${SMOKE_TEST:-0}"
SMOKE_TIMEOUT="${SMOKE_TIMEOUT:-5}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARNING:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Usage: ./build.sh [OPTIONS]

Build and install Collector with Meson into a writable prefix (default: ~/.local).
No Flatpak, root privileges, or system-wide installation are required.

Options:
  --prefix DIR      Install prefix (default: \$HOME/.local)
  --build-dir DIR   Meson build directory (default: build)
  --no-tests        Skip 'meson test' validation
  --smoke-test      Briefly launch the installed app after installation
  -h, --help        Show this help

Environment variables:
  PREFIX, BUILD_DIR, PYTHON, RUN_TESTS, SMOKE_TEST, SMOKE_TIMEOUT

Examples:
  ./build.sh
  PREFIX="$HOME/opt/collector" ./build.sh
  ./build.sh --smoke-test
EOF
}

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

install_hints() {
  local distro=""
  if [ -r /etc/os-release ]; then
    distro="$(sed -n 's/^ID=//p' /etc/os-release | head -n 1 | tr -d '\"')"
  fi
  case "$distro" in
    fedora)
      echo 'On Fedora try: sudo dnf install meson ninja-build gtk4-devel libadwaita-devel python3-gobject python3-pillow python3-requests python3-pip glib2-devel gettext desktop-file-utils appstream'
      ;;
    debian|ubuntu|linuxmint|pop)
      echo 'On Debian/Ubuntu try: sudo apt install meson ninja-build libgtk-4-dev libadwaita-1-dev python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-pil python3-requests python3-pip libglib2.0-bin gettext desktop-file-utils appstream-util'
      ;;
    arch|manjaro|endeavouros)
      echo 'On Arch try: sudo pacman -S meson ninja gtk4 libadwaita python-gobject python-pillow python-requests python-pip glib2 gettext desktop-file-utils appstream-glib'
      ;;
    *)
      echo 'Install Meson, Ninja, GTK4/Libadwaita development files and typelibs, PyGObject, gettext, and pip using your package manager.'
      ;;
  esac
}

pip_install() {
  local spec="$1"
  local -a args=()

  # A virtualenv already owns its site-packages; otherwise install for the user.
  [ -n "${VIRTUAL_ENV:-}" ] || args+=(--user)

  # PEP 668 "externally managed" environments need an explicit opt-out.
  if "$PYTHON" -m pip install --help 2>/dev/null | grep -q -- '--break-system-packages'; then
    local stdlib
    stdlib="$("$PYTHON" -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')"
    [ ! -f "$stdlib/EXTERNALLY-MANAGED" ] || args+=(--break-system-packages)
  fi

  "$PYTHON" -m pip install "${args[@]}" "$spec"
}

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --prefix)
      shift
      [ $# -gt 0 ] || die '--prefix requires an argument'
      PREFIX="$1"
      ;;
    --prefix=*)
      PREFIX="${1#*=}"
      ;;
    --build-dir)
      shift
      [ $# -gt 0 ] || die '--build-dir requires an argument'
      BUILD_DIR="$1"
      ;;
    --build-dir=*)
      BUILD_DIR="${1#*=}"
      ;;
    --no-tests)
      RUN_TESTS=0
      ;;
    --smoke-test)
      SMOKE_TEST=1
      ;;
    *)
      die "Unknown option: $1 (try --help)"
      ;;
  esac
  shift
done

# Expand a literal leading ~ even when the value came from --prefix=~/...
PREFIX="${PREFIX/#\~/$HOME}"
BUILD_DIR="${BUILD_DIR/#\~/$HOME}"

log 'Checking build tools'
missing_tools=()
for tool in meson ninja pkg-config glib-compile-resources glib-compile-schemas msgfmt; do
  command -v "$tool" >/dev/null 2>&1 || missing_tools+=("$tool")
done
if [ ${#missing_tools[@]} -gt 0 ]; then
  die "Missing build tools: ${missing_tools[*]}. $(install_hints)"
fi
if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
  die "Python pip is unavailable for $PYTHON. $(install_hints)"
fi

log 'Checking GTK4 / Libadwaita GObject Introspection bindings'
if ! "$PYTHON" - <<'PY' >/dev/null 2>&1
import gi
for namespace, version in (('Gtk', '4.0'), ('Gdk', '4.0'), ('Adw', '1')):
    gi.require_version(namespace, version)
from gi.repository import Gtk, Gdk, Adw, Gio  # noqa: F401
PY
then
  die "PyGObject or the GTK4/Libadwaita typelibs are unavailable for $PYTHON. $(install_hints)"
fi

if [ -f requirements.txt ]; then
  log 'Checking Python dependencies from requirements.txt'
  while IFS= read -r raw_spec || [ -n "$raw_spec" ]; do
    spec="$(trim "${raw_spec%%#*}")"
    [ -n "$spec" ] || continue
    name="${spec%%[=<>!~]*}"
    case "$name" in
      [Pp][Ii][Ll][Ll][Oo][Ww]) module=PIL ;;
      *)                        module="$name" ;;
    esac
    if "$PYTHON" -c "import $module" >/dev/null 2>&1; then
      log "  $spec: already available"
    else
      log "  $spec: installing"
      pip_install "$spec"
      "$PYTHON" -c "import $module" >/dev/null 2>&1 || die "Failed to install $spec"
    fi
  done < requirements.txt
fi

mkdir -p "$PREFIX"
PREFIX="$(cd "$PREFIX" && pwd -P)"
case "$BUILD_DIR" in
  /*) BUILD_PATH="$BUILD_DIR" ;;
  *)  BUILD_PATH="$SOURCE_DIR/$BUILD_DIR" ;;
esac

log "Configuring Meson build (prefix: $PREFIX)"
if [ -f "$BUILD_PATH/meson-info/intro-buildoptions.json" ]; then
  meson setup --wipe "$BUILD_PATH" --prefix="$PREFIX"
else
  if [ -d "$BUILD_PATH" ] && [ -n "$(find "$BUILD_PATH" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    die "'$BUILD_PATH' exists but is not a Meson build directory; remove it or set BUILD_DIR"
  fi
  meson setup "$BUILD_PATH" --prefix="$PREFIX"
fi

log 'Compiling'
meson compile -C "$BUILD_PATH"

if [ "$RUN_TESTS" = 1 ]; then
  log 'Running validation tests'
  meson test -C "$BUILD_PATH" --print-errorlogs
fi

log 'Installing'
meson install -C "$BUILD_PATH"

# Meson normally does this via gnome.post_install(); repeat to be safe.
if [ -d "$PREFIX/share/glib-2.0/schemas" ]; then
  glib-compile-schemas "$PREFIX/share/glib-2.0/schemas"
fi

log 'Verifying installation'
launcher="$PREFIX/bin/collector"
[ -x "$launcher" ] || die "Missing or non-executable launcher: $launcher"
[ -f "$PREFIX/share/collector/collector.gresource" ] || die "Missing GResource bundle"
[ -f "$PREFIX/share/glib-2.0/schemas/gschemas.compiled" ] || die "Compiled GSettings schema not found"

if [ "$SMOKE_TEST" = 1 ]; then
  log "Launching collector for ${SMOKE_TIMEOUT}s (exit 124/137 means it stayed alive)"
  command -v timeout >/dev/null 2>&1 || die "'timeout' command is required for the smoke test"

  # An isolated session bus avoids GApplication's single-instance handoff to
  # any Collector instance the user may already have running.
  smoke_cmd=(timeout --kill-after=2s "$SMOKE_TIMEOUT" "$launcher")
  if command -v dbus-run-session >/dev/null 2>&1; then
    smoke_cmd=(dbus-run-session -- "${smoke_cmd[@]}")
  else
    warn 'dbus-run-session not found; an already-running Collector may affect this test'
  fi

  set +e
  # Accessibility bus activation is irrelevant (and noisy) in an isolated session.
  APP_DEBUG=1 GTK_A11Y=none "${smoke_cmd[@]}"
  smoke_rc=$?
  set -e
  case "$smoke_rc" in
    0|124|137) log "Smoke test OK (exit $smoke_rc)" ;;
    *)         die "Smoke test failed with exit $smoke_rc" ;;
  esac
fi

cat <<EOF

Build and install complete.
  Source:    $SOURCE_DIR
  Build:     $BUILD_PATH
  Prefix:    $PREFIX
  Launcher:  $launcher
  Run with:  $launcher
EOF
