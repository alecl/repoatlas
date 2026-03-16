# Bash Script Conventions

Patterns derived from production scripts in this repo (`db-setup.sh`, `db-migrate.sh`, `web-secrets-setup.sh`, `infra-deploy.sh`, `aws_sso.sh`). Organized by priority tier.

---

## Tier 1: MUST-HAVE

These patterns appear in scripts aiming to prevent real bugs.

### Strict mode

Every script starts with `set -euo pipefail`. The triad catches: non-zero exits (`-e`), undefined variables (`-u`), and failures in piped commands (`pipefail`).

### Execution mode policy (CI/CD-safe by default)

Scripts must explicitly support two modes:

- **CI/CD mode (default safety posture):** non-interactive, fail-fast, no blocking prompts, deterministic output, explicit flags for destructive operations.
- **Operator mode (interactive):** may prompt, may show richer progress output, may offer manual fallback paths.

If behavior differs by mode, script help text and examples must document both paths.
Recommended switch: `--yes` or equivalent for non-interactive confirmation bypass.

### Shebang and header comment block

`#!/bin/bash` shebang, followed by a comment block stating: purpose, what the script creates or modifies, prerequisites, usage examples with parameters, and author/date.

### Resolve script directory

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

Never use bare `pwd` or `$0`. Derive sibling paths relative to `SCRIPT_DIR`.

### `main "$@"` entry point

Route all execution through a `main` function called at the bottom of the file. This scopes variables with `local` and separates definitions from execution.

### Colored logging functions

Define `info()`, `warn()`, `error()`, and optionally `header()` for multi-step scripts. Use ANSI color codes (`GREEN`, `YELLOW`, `RED`, `BLUE`) with `NC` reset.

For executable scripts, `error()` should `exit 1`.
For scripts intended to be sourced, use a separate helper (for example `error_return()`) that `return 1` instead of exiting the parent shell.

### Prerequisite checking with `command -v`

Dedicate a `check_prerequisites()` function that validates every non-base command the script needs. Each missing command should produce an install hint based on host OS/package manager:

- macOS: `brew install <pkg>`
- Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y <pkg>`
- Amazon Linux 2023 (and other `dnf` distros): `sudo dnf install -y <pkg>`

Detect the available package manager dynamically (e.g., check `command -v brew`, `command -v apt-get`, `command -v dnf` in sequence) rather than assuming one.

### Idempotent create-or-update operations

Scripts must be re-runnable. Check current state before mutating. Two concrete patterns:

**SQL — create user or update password:**

```bash
psql -v ON_ERROR_STOP=1 \
  -v app_user="$app_user" \
  -v app_password="$app_password" \
  -v app_db="$app_db" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') THEN
    EXECUTE format('CREATE USER %I WITH PASSWORD %L', :'app_user', :'app_password');
  ELSE
    EXECUTE format('ALTER USER %I WITH PASSWORD %L', :'app_user', :'app_password');
  END IF;
END
$$;

SELECT format('CREATE DATABASE %I', :'app_db')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'app_db')\gexec
SQL
```

**Cloud resource — check-then-create or update:**

```bash
put_ssm_param() {
    local name="$1" value="$2" description="$3"

    if aws ssm get-parameter --name "$name" --region "$REGION" &> /dev/null; then
        warn "Parameter $name already exists — updating value"
        aws ssm put-parameter \
            --name "$name" --type SecureString --value "$value" \
            --description "$description" --region "$REGION" --overwrite
    else
        info "Creating parameter $name"
        aws ssm put-parameter \
            --name "$name" --type SecureString --value "$value" \
            --description "$description" --region "$REGION"
    fi
}
```

For auto-generated secrets (encryption keys, passwords), add a `param_exists` guard that skips generation entirely on re-runs to avoid accidental key rotation.

### Cross-OS compatibility (bash 3.2, macOS/Ubuntu/Amazon Linux 2023)

Ensure code works on macOS (bash 3.2, BSD tools), Ubuntu 22 (bash 5, GNU tools), and Amazon Linux 2023 (bash 5, GNU tools, `dnf`-based). Common variation points: `date`, `grep`, `sed`, `awk`. Use broadly compatible syntax or conditionally branch on `uname -s` output (e.g., `Darwin` for macOS). Avoid `grep -P` (GNU-only); prefer `grep -E` or `awk`.

### General bash hygiene

- Use `[[ ]]` instead of `[ ]` for tests
- Quote variables: `"$variable"` not `$variable`
- Use `$()` instead of backticks
- Use `trap` for cleanup
- Use `mktemp` for temporary files
- Avoid `eval`
- Sanitize user input
- Set proper file permissions
- Run `shellcheck` for static analysis

---

## Tier 2: SHOULD-HAVE

These patterns improve maintainability and operator experience.

### `export AWS_PAGER=""`

Set in every script that calls `aws`. Prevents the pager from blocking non-interactive execution.

### AWS credential validation — branch by auth model

Validate credentials early, but choose checks by execution context:

- **Developer SSO flow:** `aws sts get-caller-identity` plus SSO token cache expiry check (`~/.aws/sso/cache/*.json`, matching `sso_start_url`).
- **CI/CD or cloud-hosted flow (IAM role/env creds):** `aws sts get-caller-identity` and account/role expectation checks; do **not** attempt `aws sso login`.

Only call `aws sso login` in interactive developer contexts where SSO is actually configured.

### Single source of truth for config values

Extract environment names, account IDs, stack names, and resource paths from IaC config (CDK context, SSM parameters) at runtime rather than hardcoding them in scripts.

### `-h|--help` flag with usage text

Every script that accepts arguments should respond to `-h` and `--help` with usage instructions and exit 0.

### `--skip-*` flags for composable multi-step scripts

Use `while [[ $# -gt 0 ]]; do case $1 in ...` for argument parsing. This supports long options (`--skip-bootstrap`, `--diff-only`, `--debug`) which `getopts` cannot handle. Initialize boolean defaults at the top of the file.

```bash
DEBUG_LOG=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-bootstrap) SKIP_BOOTSTRAP=true; shift ;;
    --diff-only)      DIFF_ONLY=true;      shift ;;
    --debug)
      DEBUG_LOG="${SCRIPT_NAME}-$(date +%Y-%m-%d-%H-%M-%S).log"
      info "Debug log: $DEBUG_LOG"
      shift
      ;;
    -h|--help) usage; exit 0 ;;
    *) error "Unknown option: $1" ;;
  esac
done
```

### Handle acceptable failures explicitly (avoid blanket `|| true`)

Under `set -e`, any non-zero exit aborts execution. Do **not** broadly append `|| true` to service/API calls, because this can hide auth, permission, network, and throttling failures.

Use one of these patterns instead:

- Predicates in `if` conditions for expected "not found" checks.
- Capture exit code and branch only for documented acceptable codes/states.
- Parse command output for explicit sentinel values (`None`, empty list, etc.) and fail otherwise.

Use `|| true` only for truly best-effort cleanup where failure is irrelevant and explicitly documented.

### Before/after state logging

Log state before and after mutations so operators can see what changed:

```bash
# (Date values below are illustrative — compute from current date per CLAUDE.md rules)
current_rev=$(uv run --frozen --exclude-newer 2026-02-12 alembic current 2>&1) || true
info "Current revision: ${current_rev:-<none>}"

uv run --frozen --exclude-newer 2026-02-12 alembic upgrade head

new_rev=$(uv run --frozen --exclude-newer 2026-02-12 alembic current 2>&1) || true
info "Revision after migration: ${new_rev:-<unknown>}"
```

### Post-action verification

Verify outcomes via API rather than trusting exit codes alone. For example, after deploying a stack, query its status; after registering a service, confirm it's reachable.

### Summary banner at completion

Print a colored banner at the end summarizing what was done (resources created, endpoints deployed, etc.).

### Step numbering with headers

For multi-phase scripts, use calls like `header "Step 1: Bootstrap"` to produce clear visual separators in output.

### Production safety gate — require explicit `--yes` in non-interactive mode

For destructive or production-facing operations:

- In interactive shells (`-t 0`), require typing full `yes`.
- In non-interactive environments (CI/CD), reject execution unless an explicit `--yes` (or equivalent) flag is set.

```bash
if [[ "$ENVIRONMENT" == "prod" && "$DIFF_ONLY" == "false" ]]; then
  warn "You are about to deploy to PRODUCTION!"

  if [[ -t 0 ]]; then
    read -r -p "Type 'yes' to continue: " reply
    [[ "$reply" == "yes" ]] || { info "Deployment cancelled."; exit 0; }
  else
    [[ "${ASSUME_YES:-false}" == "true" ]] || {
      error "Non-interactive run requires explicit --yes/ASSUME_YES=true for production deploys."
    }
  fi
fi
```

### `source` vs `./` awareness

Scripts that modify the caller's environment (`export` variables) must document that they need to be `source`d. Wrap the entire script body in a function that uses `return` (not `exit`) so sourcing doesn't kill the caller's shell on error:

```bash
#!/bin/bash
# Usage: source aws_sso.sh <environment>

aws_sso_script() {
    set -o pipefail

    if [[ -z "${1:-}" ]]; then
        echo "Error: No environment specified."
        return 1  # return, not exit — safe when sourced
    fi

    export AWS_PROFILE="..."
    # ... script body ...
    return 0
}

aws_sso_script "$@"
```

### Validate input parameters with defaults

Use `${1:-default}` pattern for optional positional arguments. Validate required arguments early with clear error messages.

---

## Tier 3: NICE-TO-HAVE

These patterns apply to specific scenarios.

### Defense-in-depth error checking (stderr despite exit 0)

Some tools (e.g., AWS SSM `send-command`) report success in their exit code while writing errors to stderr. After receiving a success status, still check stderr for known error patterns:

```bash
if [[ "$status" == "Success" ]]; then
    if [[ -n "$stderr_content" ]] && \
       echo "$stderr_content" | grep -qiE "Not Found|404|does not indicate success"; then
        echo -e "${RED}[ERROR]${NC} Command reported Success but stderr contains errors."
        echo "  - Check logs or re-run the script"
        exit 1
    fi
fi
```

### Timeout loops with progress feedback

Poll with inline `echo -n "."` for progress, an elapsed counter, and a hard timeout ceiling:

```bash
local timeout=300 elapsed=0 interval=10

while [[ $elapsed -lt $timeout ]]; do
    local count
    count=$(aws autoscaling describe-auto-scaling-groups \
        --auto-scaling-group-names "$asg_name" \
        --query "AutoScalingGroups[0].Instances[?LifecycleState=='InService'] | length(@)" \
        --output text 2>/dev/null || echo "0")

    if [[ "$count" == "1" ]]; then
        echo ""
        info "Instance is InService"
        break
    fi

    echo -n "."
    sleep $interval
    elapsed=$((elapsed + interval))
done
echo ""

if [[ $elapsed -ge $timeout ]]; then
    error "Timeout waiting for instance to become healthy"
fi
```

### Fallback chains (automated then manual) — interactive pattern

Try the programmatic approach first; if unavailable or failing, fall back to interactive input.
**Note:** The manual `read` fallback requires an interactive terminal. In CI/CD, fail with a clear error instead of blocking.

```bash
local TOKEN=""
if command -v gh &>/dev/null; then
    info "Generating token via gh CLI..."
    TOKEN=$(gh api "repos/${OWNER}/${REPO}/actions/runners/registration-token" \
        --method POST --jq '.token' 2>/dev/null) || true
    if [[ -n "$TOKEN" ]]; then
        info "Token generated automatically"
    else
        warn "gh API call failed — falling back to manual entry"
    fi
else
    warn "gh CLI not available — manual token entry required"
fi

if [[ -z "$TOKEN" ]]; then
    if [[ -t 0 ]]; then
        echo "Please get a token from: https://github.com/${OWNER}/${REPO}/settings/actions/runners/new"
        read -r -p "Paste the token here: " TOKEN
    fi
    if [[ -z "$TOKEN" ]]; then
        error "No token provided. In CI, set RUNNER_TOKEN env var or ensure gh CLI is authenticated."
    fi
fi
```

### Secure secret handling

Use `read -r -s` for hidden input. Generate secrets with `openssl rand` or `python3 -c "from cryptography.fernet import Fernet; ..."`. Filter characters to safe sets for connection strings.

### URL-encoding values for connection strings

Passwords with special characters break URLs. Use Python's `urllib.parse.quote`:

```bash
encoded_pass="$(
  DB_PASS="$db_pass" python3 - <<'PY'
import os
import urllib.parse
print(urllib.parse.quote(os.environ["DB_PASS"], safe=""))
PY
)"
export DATABASE_URL="postgresql+asyncpg://${db_user}:${encoded_pass}@localhost:${port}/${db_name}"
```

### `.DS_Store` cleanup (Node-specific edge case)

macOS Finder can create `.DS_Store` files in project trees. If your toolchain is sensitive (for example certain Node workflows), optionally remove them before install/build.

### Portable date/time parsing

BSD `date` (macOS) and GNU `date` (Linux) have different flags. When parsing ISO 8601 timestamps on macOS, normalize before passing to `date -j -f`:

```bash
# Normalize ISO 8601 for BSD date:
# - "UTC" -> "Z"
# - strip fractional seconds
# - "Z" -> "+0000"
# - remove colon from timezone offset ("+00:00" -> "+0000")
expires_norm=$(
    printf '%s' "$expires_at" |
      sed -E '
        s/UTC$/Z/;
        s/\.[0-9]+(Z|[+-][0-9]{2}:[0-9]{2})/\1/;
        s/Z$/+0000/;
        s/([+-][0-9]{2}):([0-9]{2})$/\1\2/
      '
)
expires_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S%z" "$expires_norm" +%s 2>/dev/null)
```

On Linux (GNU `date`), use:

```bash
expires_epoch=$(date -d "$expires_at" +%s 2>/dev/null)
```

When supporting both platforms in one script, branch on `uname -s` and keep parsing logic in a dedicated helper function.

### File glob safety in loops

When iterating over a glob that may match nothing, the glob expression stays literal on some shells. Guard it:

```bash
for cache_file in "$HOME/.aws/sso/cache"/*.json; do
    [[ -e "$cache_file" ]] || continue
    # ... process file ...
done
```

### Debugging & triage playbook (portable, safe-by-default)

Use these techniques when diagnosing script or runtime issues. Mark commands as interactive-only where relevant.

**Debug mode toggle (do not leave tracing always-on):**

```bash
set -eEuo pipefail
DEBUG="${DEBUG:-0}"
if [[ "$DEBUG" == "1" ]]; then
  export PS4='+ ${BASH_SOURCE##*/}:${LINENO}:${FUNCNAME[0]:-main}: '
  set -x
fi
```

**Structured payload logging (`--debug` flag):**

Complementary to the `set -x` trace above. `set -x` traces *shell execution* (every expanded command); `--debug` captures *structured data* — API requests, responses, normalized comparisons, mismatch details — for diagnosing logic and data issues without the noise (or secret-exposure risk) of full shell tracing.

The pattern has three parts:

1. A `--debug` CLI flag that sets a timestamped log file path (see argument parsing example in Tier 2).
2. A `debug_log` helper that no-ops when the path is empty — zero overhead when `--debug` is not passed.
3. Pretty-printed entries via `jq` (with raw-text fallback) so the log is human-readable.

```bash
debug_log() {
  # No-op when --debug was not passed
  [[ -n "${DEBUG_LOG:-}" ]] || return 0

  local label="$1"
  local data="${2:-}"

  {
    echo "=== ${label} === $(date '+%Y-%m-%d %H:%M:%S')"
    if [[ -n "$data" ]]; then
      echo "$data" | jq . 2>/dev/null || echo "$data"
    fi
    echo ""
  } >> "$DEBUG_LOG"
}
```

Usage throughout the script:

```bash
# Log an API request payload
debug_log "API REQUEST: update ruleset" "$request_body"

# Log a response
debug_log "API RESPONSE: update ruleset" "$response"

# Log a comparison (non-JSON text is fine too)
debug_log "NORMALIZED COMPARISON" "expected: ${expected}
actual:   ${actual}"
```

At the end of execution, remind the operator where the log lives:

```bash
if [[ -n "${DEBUG_LOG:-}" ]]; then
  info "Debug log written to: $DEBUG_LOG"
fi
```

**Log analysis:**

```bash
# Find errors
grep -E "ERROR|FATAL" application.log

# Count top error signatures (adjust field index to your log format)
grep "ERROR" application.log | awk '{print $5}' | sort | uniq -c | sort -nr

# Live filter with color (interactive)
tail -f application.log | grep --color=always -E "ERROR|WARN|INFO"

# JSON logs
jq -c 'select(.level=="error") | {timestamp, message, errorCode}' application.json.log
```

**Process checks:**

```bash
# Find matching processes safely
pgrep -af node

# Open files/ports for PID
lsof -p "$pid"

# Interactive process monitor (platform-specific)
case "$(uname -s)" in
  Darwin) top -pid "$pid" ;;
  *)      top -p "$pid"   ;;
esac
htop                   # if installed (cross-platform)
```

**Network diagnostics:**

```bash
# Port reachability
nc -vz example.com 443

# HTTP diagnostics
curl -v https://api.example.com/status

# DNS
dig +short example.com

# Route
traceroute example.com

# Connections/listeners (Linux/macOS fallback)
ss -tuln 2>/dev/null || netstat -an
```

**System state checks:**

```bash
df -h
du -sh /var/log
uptime
ulimit -a
```

**Quoting/interpolation debugging:**

```bash
debug_var() {
  local name="$1" value="${!1-}"
  printf '%s raw=[%s] escaped=[%q] len=%s\n' "$name" "$value" "$value" "${#value}" >&2
}

# Reveal hidden characters when needed:
# printf '%s' "$suspect_value" | od -An -t x1
```

**Safety caveat — applies to both `set -x` tracing and `--debug` payload logs:**

- `set -x` and `curl -v` print auth headers and expanded variables — never leave tracing on in committed code or CI logs.
- `--debug` log files are designed for sharing during troubleshooting — treat them as potentially public.
- Never log raw API response headers (they often contain `Authorization`, `Set-Cookie`, or token values).
- Project/filter payloads to only the fields needed for diagnosis before passing to `debug_log`. For example, log the request body but not the headers object.
- If a payload might contain secrets (connection strings, tokens, API keys), either skip it entirely or redact sensitive fields before logging:
  ```bash
  # Redact a known secret field before logging
  safe_payload=$(echo "$payload" | jq 'del(.credentials, .token)')
  debug_log "FILTERED PAYLOAD" "$safe_payload"
  ```
- Full environment dumps (`env | sort`) should be filtered to a safe allowlist — never dump the entire environment.

| Task | Preferred | macOS fallback | Linux fallback |
|---|---|---|---|
| Find process | `pgrep -af <name>` | same | same |
| List sockets | `ss -tuln` | `netstat -an` / `lsof -i` | `ss -tuln` |
| Port probe | `nc -vz host port` | same | same |
| Memory summary | `vm_stat` / `memory_pressure` | same | `free -h` |
| CPU details | `sysctl -n machdep.cpu.brand_string` | same | `lscpu` / `/proc/cpuinfo` |

---

## AWS Specifics

- `export AWS_PAGER=""` in every script (mandatory)
- Validate credentials early — branch by auth model (SSO vs IAM role) as described in Tier 2
- Use `--query` and `--output text` for machine-parseable output
- Be diligent about scoping write/delete operations — validate expectations before mutating
- Leverage read-only operations for validation checks before proceeding with writes