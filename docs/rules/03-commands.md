# 03 — Commands

Only suggest or execute commands that appear in this document. Do not assume standard tool defaults, global flags, or operating-system-specific behavior unless explicitly listed here.

---

## Development Environment Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
.\venv\Scripts\activate           # Windows

# Install runtime dependencies
pip install -r requirements.txt

# Install development/test/lint/build dependencies
pip install -r requirements-dev.in
```

---

## Dependency Management

```bash
# Install runtime dependencies
pip install -r requirements.txt

# Install test/lint/build dependencies
pip install -r requirements-dev.in
```

**Rules:**
- Runtime dependencies belong in `requirements.in`.
- Test, coverage, lint, and explicit build tooling belong in `requirements-dev.in`.
- `requirements.txt` is a compatibility entry that delegates to `requirements.in`; do not replace it with a local cross-platform lock file.

---

## Testing

```bash
# Run a specific test file
pytest tests/test_xxx.py

# Run all tests
pytest

# Run tests with verbose output
pytest -v tests/test_xxx.py

# Run a specific test function
pytest tests/test_xxx.py::test_function_name
```

**Rules:**
- Run at minimum the tests directly related to the change.
- 影响公共模块、启动流程或 CLI 行为时，跑完整测试套件。
- If the task only changes documentation, state explicitly that tests were not run. Do not claim checks that were not executed.

---

## Static Analysis

```bash
# Run pylint on the application package
pylint app/

# Run pylint on a specific module
pylint app/chain/download.py
```

**Rules:**
- After Python code changes, ensure no new error-level issues are introduced.
- Warning-level issues in new code should be minimized but are not an absolute gate.

---

## Security Scan

```bash
# Run safety check against the runtime compatibility entry
safety check -r requirements.txt --policy-file=safety.policy.yml

# Save report to file
safety check -r requirements.txt --policy-file=safety.policy.yml > safety_report.txt
```

**Rules:**
- Run after runtime dependency changes; include `requirements-dev.in` when development/test/lint/build dependencies change.
- No new high-severity vulnerabilities may be introduced.

---

## Local CLI — Service Management

```bash
moviepilot start
moviepilot start --timeout 60
moviepilot stop
moviepilot stop --timeout 30 --force
moviepilot restart
moviepilot restart --start-timeout 60 --stop-timeout 30
moviepilot status
moviepilot version
moviepilot doctor
moviepilot doctor --json
moviepilot doctor --fix
moviepilot doctor --deep
moviepilot doctor --json --fix
moviepilot start --safe
```

```bash
moviepilot logs
moviepilot logs --lines 100
moviepilot logs --stdio
moviepilot logs --frontend
moviepilot logs --follow
moviepilot logs --frontend --follow
moviepilot logs --stdio --follow
```

---

## Local CLI — Installation and Setup

```bash
# One-line bootstrap installer
curl -fsSL https://raw.githubusercontent.com/jxxghp/MoviePilot/v2/scripts/bootstrap-local.sh | bash

# Install backend dependencies
moviepilot install deps
moviepilot install deps --python python3.11
moviepilot install deps --venv /path/to/venv
moviepilot install deps --recreate

# Install frontend release
moviepilot install frontend
moviepilot install frontend --version latest
moviepilot install frontend --version v2.9.31

# Install resource files
moviepilot install resources

# Initialize local config
moviepilot init
moviepilot init --wizard
moviepilot init --force-token
moviepilot init --superuser admin --superuser-password 'ChangeMe123!'

# All-in-one setup
moviepilot setup
moviepilot setup --wizard
moviepilot setup --recreate
moviepilot setup --superuser admin --superuser-password 'ChangeMe123!'

# Uninstall
moviepilot uninstall
```

---

## Local CLI — Update

```bash
moviepilot update backend
moviepilot update backend --ref latest
moviepilot update backend --ref v2.9.31

moviepilot update frontend
moviepilot update frontend --frontend-version latest

moviepilot update all
moviepilot update all --ref latest --frontend-version latest
moviepilot update all --skip-resources
```

---

## Local CLI — Startup on Boot

```bash
moviepilot startup status
moviepilot startup enable
moviepilot startup disable
moviepilot startup enable --venv /path/to/venv
```

---

## Local CLI — Configuration

```bash
moviepilot config path
moviepilot config list
moviepilot config list --show-secrets
moviepilot config get PORT
moviepilot config set PORT 3001
moviepilot config keys
moviepilot config keys DB_
moviepilot config keys --show-current
moviepilot config describe PORT
moviepilot config describe API_TOKEN --show-secrets
```

---

## Local CLI — Tools and Scheduler

```bash

## Local CLI — Help Discovery

```bash
moviepilot --help
moviepilot help
moviepilot commands
moviepilot help install
moviepilot help init
moviepilot help setup
moviepilot help update
moviepilot help config
moviepilot help tool
moviepilot help scheduler
```

---


