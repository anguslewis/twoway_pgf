#!/usr/bin/env bash
# Explicit one-time setup, launched before Stata initializes embedded Python.
# Arguments are request/receipt file paths.
set -euo pipefail
# Directory permissions follow the caller's umask and filesystem defaults.
PACKAGE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQUEST="${1:?request file required}"
RECEIPT="${2:?fresh receipt path required}"
[[ ! -e "$RECEIPT" ]] || { echo 'Refusing an existing setup receipt' >&2; exit 1; }
# One field per line: python, package state root, manager, TeX-bin, offline,
# explicit mode, optional environment prefix.
exec 3< "$REQUEST"
IFS= read -r PYTHON_EXEC <&3
IFS= read -r ROOT <&3
IFS= read -r MANAGER <&3
IFS= read -r TEXBIN <&3
IFS= read -r OFFLINE <&3
IFS= read -r MODE <&3
IFS= read -r ENV_PREFIX <&3
if IFS= read -r EXTRA <&3; then echo 'Unexpected setup request field' >&2; exit 1; fi
exec 3<&-
[[ "$OFFLINE" == 0 || "$OFFLINE" == 1 ]] || exit 1
case "$MODE" in validate|install) ;; *) echo 'Invalid setup mode; use validate or install with an existing Conda installation.' >&2; exit 1 ;; esac
if [[ "$MODE" == install ]]; then
    case "$(uname -sm)" in
      'Darwin arm64') PLATFORM=osx-arm64 ;;
      'Linux x86_64') PLATFORM=linux-64 ;;
      *) echo 'Automatic environment creation supports Apple-silicon macOS and Linux x86-64. On other POSIX systems, create environment.yml with Conda and select its Python with python().' >&2; exit 1 ;;
    esac
fi
if [[ "$MODE" == validate ]]; then
    [[ -z "$MANAGER" ]] || { echo 'manager requires explicit install mode' >&2; exit 1; }
    [[ -z "$ENV_PREFIX" ]] || { echo 'An environment prefix requires explicit install mode' >&2; exit 1; }
    if [[ -z "$PYTHON_EXEC" && -n "${CONDA_PREFIX:-}" && -x "$CONDA_PREFIX/bin/python" ]]; then
        PYTHON_EXEC="$CONDA_PREFIX/bin/python"
    fi
    if [[ -z "$PYTHON_EXEC" ]]; then
        for CANDIDATE in python3 python; do
            if command -v "$CANDIDATE" >/dev/null 2>&1; then PYTHON_EXEC="$(command -v "$CANDIDATE")"; break; fi
        done
    fi
    [[ -n "$PYTHON_EXEC" ]] || { echo 'No existing Python found; supply python() or use install with your existing Conda installation.' >&2; exit 1; }
    echo "Validating existing Python (no installation): $PYTHON_EXEC"
else
    [[ -z "$PYTHON_EXEC" ]] || { echo 'Installation mode cannot target an existing interpreter' >&2; exit 1; }
    echo 'Explicit environment installation requested through existing Conda.'
fi
# Load pinned build metadata.
source "$PACKAGE/bootstrap/pins.sh"
sha256() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d ' ' -f 1
    else shasum -a 256 "$1" | cut -d ' ' -f 1; fi
}
verify() {
    [[ "$(sha256 "$1")" == "$2" ]] || { echo "SHA256 mismatch: $1" >&2; exit 1; }
}
[[ "$ROOT" == /* ]] || { echo 'Package storage root must be absolute' >&2; exit 1; }
mkdir -p "$ROOT" || { echo "Cannot create package directory $ROOT. Check PLUS write permissions." >&2; exit 1; }
ROOT="$(cd "$ROOT" && pwd -P)"
# Validation is read-only with respect to shared package state: diagnostics
# use unique temporary files, the interpreter record is committed atomically
# only after Stata accepts the selection, and cache directories use mkdir -p.
# Do not serialize every figure job behind one global lock. In particular,
# an unconditional lock here made concurrent figure jobs fail even though
# they only validated the already-installed backend.
LOCK_DIR="$ROOT/.setup-lock"
if [[ "$MODE" == install ]]; then
    mkdir "$LOCK_DIR" || {
        echo "Cannot lock installation at $ROOT. Another installation may be active." >&2
        if [[ -f "$LOCK_DIR/owner" ]]; then
            echo "Lock owner:" >&2
            cat "$LOCK_DIR/owner" >&2
        else
            echo "The lock has no owner record (legacy or interrupted setup); inspect it before removal." >&2
        fi
        exit 1
    }
    cleanup_lock() {
        rm -f "$LOCK_DIR/owner"
        rmdir "$LOCK_DIR"
    }
    trap cleanup_lock EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
    {
        printf 'pid=%s\n' "$$"
        printf 'host=%s\n' "$(hostname)"
        printf 'slurm_job_id=%s\n' "${SLURM_JOB_ID:-none}"
        printf 'started_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "$LOCK_DIR/owner"
elif [[ -d "$LOCK_DIR" && -f "$LOCK_DIR/owner" ]]; then
    echo "An install-lock record exists at $LOCK_DIR; validation is lock-free." >&2
fi
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME
export MPLCONFIGDIR="$ROOT/cache/mpl" XDG_CACHE_HOME="$ROOT/cache"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p "$MPLCONFIGDIR"
READY=""
if [[ "$MODE" == install ]]; then
    # Use Conda's configured package cache and envs_dirs.
    WHEEL="$PACKAGE/artifacts/$WHEEL_NAME"
    LOCK="$PACKAGE/locks/$PLATFORM.txt"
    case "$PLATFORM" in
      osx-arm64) LOCK_HASH="$LOCK_OSX_SHA256" ;;
      linux-64) LOCK_HASH="$LOCK_LINUX_SHA256" ;;
    esac
    verify "$WHEEL" "$WHEEL_SHA256"
    verify "$LOCK" "$LOCK_HASH"
    BUILD_ID="$VERSION-$PLATFORM-${WHEEL_SHA256:0:12}-${LOCK_HASH:0:12}"
    if command -v sha256sum >/dev/null 2>&1; then
        TARGET_ID="$(printf '%s' "${ENV_PREFIX:-name:twoway_pgf}" | sha256sum | cut -d ' ' -f 1)"
    else
        TARGET_ID="$(printf '%s' "${ENV_PREFIX:-name:twoway_pgf}" | shasum -a 256 | cut -d ' ' -f 1)"
    fi
    READY="$ROOT/ready-$BUILD_ID-${TARGET_ID:0:12}.txt"
    if [[ -f "$READY" ]]; then
        IFS= read -r PYTHON_EXEC < "$READY" || PYTHON_EXEC=""
        [[ "$PYTHON_EXEC" == /* ]] || { echo "Invalid environment record: $READY. Select an existing environment with python(), or remove this record before install." >&2; exit 1; }
        if [[ ! -e "$PYTHON_EXEC" ]]; then
            echo "Stale environment record: $READY (Python missing at $PYTHON_EXEC). Checking the destination before recreating the environment."
            PYTHON_EXEC=""
        else
            [[ -x "$PYTHON_EXEC" ]] || { echo "Python in $READY is not executable; check its permissions: $PYTHON_EXEC" >&2; exit 1; }
        fi
    fi
    if [[ -n "$PYTHON_EXEC" ]]; then
        echo "Rechecking installed environment: $PYTHON_EXEC"
    else
        if [[ -z "$MANAGER" && -n "${CONDA_EXE:-}" && -x "$CONDA_EXE" ]]; then
            MANAGER="$CONDA_EXE"
        fi
        if [[ -z "$MANAGER" ]]; then
            for CANDIDATE in conda mamba micromamba; do
                if type -P "$CANDIDATE" >/dev/null; then MANAGER="$(type -P "$CANDIDATE")"; break; fi
            done
        fi
        if [[ -z "$MANAGER" ]]; then
            echo 'Conda not found. Make your existing Conda installation available on PATH, or supply install manager("/absolute/path/to/conda"). No environment manager is installed by this package.' >&2
            echo 'Finder/Dock-launched Stata may not inherit your terminal PATH or CONDA_EXE. In your usual Conda terminal, run conda info --base; append /bin/conda to that path. In Stata rerun twoway_pgf_setup, install manager("/full/path/bin/conda") texbin("/path/to/tex/bin") (MacTeX normally uses /Library/TeX/texbin).' >&2
            exit 1
        fi
        [[ "$MANAGER" == /* && -x "$MANAGER" ]] || { echo 'manager must be an executable absolute path to an installed Conda-compatible manager' >&2; exit 1; }
        if [[ -n "$ENV_PREFIX" ]]; then
            [[ "$ENV_PREFIX" == /* ]] || { echo 'envpath() must be an absolute Conda environment path' >&2; exit 1; }
            [[ ! -e "$ENV_PREFIX" ]] || { echo 'envpath() already exists; it was not modified. Select its Python with python() or choose a fresh envpath().' >&2; exit 1; }
            OPTIONS=(create -y --prefix "$ENV_PREFIX" --file "$LOCK")
            echo "Creating environment with $MANAGER at explicit prefix $ENV_PREFIX"
        else
            # Read the manager's environment inventory.
            ENV_LIST="$("$MANAGER" env list)" || { echo 'Cannot inspect existing Conda environments; no environment was created or changed.' >&2; exit 1; }
            if printf '%s\n' "$ENV_LIST" | awk '$1 == "twoway_pgf" { found=1 } END { exit !found }'; then
                echo 'Conda environment twoway_pgf already exists; it was not modified. Activate it and select its Python with python(), or choose install envpath("/path/to/a/new/environment").' >&2
                exit 1
            fi
            OPTIONS=(create -y --name twoway_pgf --file "$LOCK")
            echo "Creating named environment twoway_pgf with $MANAGER in Conda's configured environment location"
        fi
        [[ "$OFFLINE" == 0 ]] || OPTIONS+=(--offline)
        "$MANAGER" "${OPTIONS[@]}"
        if [[ -n "$ENV_PREFIX" ]]; then
            PYTHON_EXEC="$ENV_PREFIX/bin/python"
        else
            PYTHON_EXEC="$("$MANAGER" run --name twoway_pgf python -I -c 'import sys; print(sys.executable)')"
        fi
        "$PYTHON_EXEC" -I -m pip install --no-index --no-deps "$WHEEL"
    fi
fi
[[ "$PYTHON_EXEC" == /* && -x "$PYTHON_EXEC" ]] || { echo 'python must be an executable absolute path' >&2; exit 1; }
DIAGNOSTIC="$(mktemp "$ROOT/diagnostic-XXXXXX")"
"$PYTHON_EXEC" -I "$PACKAGE/stata/twoway_pgf_bridge.py" --check "$VERSION"
# Save the environment pointer before TeX validation.
if [[ -n "$READY" ]]; then
    STAGE="$(mktemp "$ROOT/ready-XXXXXX")"
    printf '%s\n' "$PYTHON_EXEC" > "$STAGE"
    mv -f "$STAGE" "$READY"
fi
"$PYTHON_EXEC" -I -m twoway_pgf.installation --expected "$VERSION" --texbin "$TEXBIN" --receipt "$DIAGNOSTIC"
# Convert the checked diagnostic to a plain-text Stata record.
"$PYTHON_EXEC" -I "$PACKAGE/bootstrap/record.py" "$DIAGNOSTIC" "$RECEIPT"
