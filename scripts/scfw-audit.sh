#!/bin/bash
# =============================================================================
# scfw-audit.sh — Local Datadog SCFW (Supply Chain Firewall) audit
#
# Purpose:   Audit project dependencies against known-malicious package lists
#            using Datadog's SCFW tool. Mirrors the CI SCFW gate locally.
#
# Prerequisites:
#   - uv (https://docs.astral.sh/uv/)
#   - python3
#
# What it creates:
#   - Temporary requirements file (cleaned up automatically)
#   - Temporary virtualenv in /tmp (cleaned up automatically)
#
# Usage:
#   ./scripts/scfw-audit.sh                     # audit with default SCFW version
#   ./scripts/scfw-audit.sh --scfw-version 2.7.0  # audit with specific version
#   ./scripts/scfw-audit.sh -h                  # show help
# =============================================================================

set -euo pipefail

# -- Constants ----------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DEFAULT_SCFW_VERSION="2.6.0"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# -- Logging ------------------------------------------------------------------

info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
header()  { echo -e "\n${BLUE}=== $* ===${NC}"; }

# -- Help ---------------------------------------------------------------------

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Run a Datadog SCFW supply-chain audit against project dependencies.

Options:
  --scfw-version VERSION   SCFW version to use (default: $DEFAULT_SCFW_VERSION)
  -h, --help               Show this help and exit

Examples:
  $(basename "$0")
  $(basename "$0") --scfw-version 2.7.0
EOF
}

# -- Prerequisites ------------------------------------------------------------

check_prerequisites() {
    local missing=0

    if ! command -v uv &>/dev/null; then
        warn "uv not found."
        if command -v brew &>/dev/null; then
            warn "  Install: brew install uv"
        elif command -v apt-get &>/dev/null; then
            warn "  Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
        elif command -v dnf &>/dev/null; then
            warn "  Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
        fi
        missing=1
    fi

    if ! command -v python3 &>/dev/null; then
        warn "python3 not found."
        if command -v brew &>/dev/null; then
            warn "  Install: brew install python@3.12"
        elif command -v apt-get &>/dev/null; then
            warn "  Install: sudo apt-get update && sudo apt-get install -y python3"
        elif command -v dnf &>/dev/null; then
            warn "  Install: sudo dnf install -y python3"
        fi
        missing=1
    fi

    if [[ "$missing" -eq 1 ]]; then
        error "Missing prerequisites. Install the tools above and retry."
    fi
}

# -- Date computation (cross-OS) ---------------------------------------------

compute_exclude_newer() {
    # Try GNU date first, fall back to BSD date (macOS)
    if date -d '-3 days' +%Y-%m-%d &>/dev/null; then
        EXCLUDE_NEWER="$(date -d '-3 days' +%Y-%m-%d)"
    elif date -v-3d +%Y-%m-%d &>/dev/null; then
        EXCLUDE_NEWER="$(date -v-3d +%Y-%m-%d)"
    else
        error "Cannot compute date. Neither GNU date nor BSD date available."
    fi
}

# -- Cleanup ------------------------------------------------------------------

SCFW_VENV=""
SCFW_REQUIREMENTS=""

cleanup() {
    if [[ -n "$SCFW_VENV" && -d "$SCFW_VENV" ]]; then
        rm -rf "$SCFW_VENV"
    fi
    if [[ -n "$SCFW_REQUIREMENTS" && -f "$SCFW_REQUIREMENTS" ]]; then
        rm -f "$SCFW_REQUIREMENTS"
    fi
}

# -- Main ---------------------------------------------------------------------

main() {
    local scfw_version="$DEFAULT_SCFW_VERSION"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --scfw-version)
                [[ -n "${2:-}" ]] || error "--scfw-version requires a value"
                scfw_version="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
    done

    header "SCFW Supply-Chain Audit"
    info "SCFW version: $scfw_version"

    check_prerequisites

    # Validate project structure
    [[ -f "$PROJECT_ROOT/pyproject.toml" ]] || error "pyproject.toml not found in $PROJECT_ROOT"
    [[ -f "$PROJECT_ROOT/uv.lock" ]]        || error "uv.lock not found in $PROJECT_ROOT"

    compute_exclude_newer
    info "Exclude-newer date: $EXCLUDE_NEWER"

    # Register cleanup trap
    trap cleanup EXIT

    cd "$PROJECT_ROOT"

    # Export dependencies to temp requirements file
    header "Step 1: Export dependencies"
    SCFW_REQUIREMENTS="$(mktemp "${TMPDIR:-/tmp}/scfw-requirements.XXXXXX.txt")"
    uv export --frozen --exclude-newer "$EXCLUDE_NEWER" --extra test --extra dev --no-hashes -o "$SCFW_REQUIREMENTS"
    info "Requirements exported to $SCFW_REQUIREMENTS"

    # Create isolated temp venv
    header "Step 2: Create temporary virtualenv"
    SCFW_VENV="$(mktemp -d "${TMPDIR:-/tmp}/scfw-venv.XXXXXX")"
    uv venv "$SCFW_VENV"
    # shellcheck disable=SC1091
    source "$SCFW_VENV/bin/activate"
    python -m ensurepip --upgrade
    info "Temporary venv: $SCFW_VENV"

    # Run SCFW audit
    header "Step 3: Run SCFW audit"
    uvx "scfw==$scfw_version" run --allow-on-warning pip install -r "$SCFW_REQUIREMENTS"

    deactivate

    # Summary
    echo ""
    info "SCFW audit passed. No known-malicious packages detected."
}

main "$@"
