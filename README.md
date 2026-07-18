<div align="center">

# ✦ Astra CMS

**AI-powered Editorial Operating System for WordPress.**

[![CI](https://github.com/ravikantraj25/astra-cms/actions/workflows/ci.yml/badge.svg)](https://github.com/ravikantraj25/astra-cms/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

</div>

---

## Overview

**Astra CMS** is an open-source toolkit designed to streamline editorial workflows by providing an AI-powered operating system for WordPress. Built with clean architecture principles and a modular plugin system, Astra CMS gives developers and editors full control over content analysis, planning, and generation without ever compromising the structural integrity of your HTML.

### Key Design Principles

- **Clean Architecture** — Domain, Application, Infrastructure, and Presentation layers are fully decoupled.
- **Type-Safe** — Strict type hints and Pydantic v2 models throughout the codebase.
- **Extensible** — Plugin-friendly provider system for CMS platforms and AI services.
- **Developer-First** — Rich CLI powered by Typer with beautiful terminal output.

---

## Quick Start

### Prerequisites

| Tool   | Version  |
|--------|----------|
| Python | ≥ 3.11   |
| uv     | latest   |

### Installation

```bash
# Clone the repository
git clone https://github.com/ravikantraj25/astra-cms.git
cd astra-cms

# Create virtual environment & install dependencies
uv venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Verify the installation
astra version
```

### Environment Setup

```bash
cp .env.example .env
# Edit .env with your configuration
```

---

## Usage

### General Commands

```bash
# Show the current version
astra version

# Run system diagnostics
astra doctor
```

### WordPress Connection

Test the connection to your WordPress site:

```bash
# Set credentials in .env
# WP_BASE_URL=https://your-site.com
# WP_USERNAME=admin
# WP_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Test the connection
astra wp test
```

### Fetch Posts

Fetch posts from WordPress and display them in a table:

```bash
# Fetch the latest 10 posts
astra wp fetch

# Fetch 5 posts
astra wp fetch --limit 5

# Fetch page 2
astra wp fetch --page 2

# Search posts
astra wp fetch --search "Diwali"

# Fetch drafts
astra wp fetch --status draft
```

**Example output:**

```
  Fetching posts...
  ✔ Connected

  Retrieved 5 posts

  ID      Status      Title
  ──────────────────────────────────────────────
  120     publish     Diwali NYC 2026
  121     publish     Chhath USA
  122     draft       Holi Boston
  123     publish     Ganesh Dallas
  124     publish     Dussehra Sydney
```

---

### AI Editorial Pipeline

Run your WordPress content through the full AI-powered editorial lifecycle:

```bash
# 1. Fetch raw HTML, analyze it, and build an update plan ALL in one command!
astra workflow analyze 123

# 2. Generate updated HTML + telemetry report (output/update_report.json)
astra workflow generate 123

# 3. Preview changes visually (optional)
astra diff output/post_123.html output/post_123_updated.html

# 4. Push safely back to WordPress as a Draft for review!
astra workflow publish 123
```

You can also run granular individual commands:
```bash
# Standalone generation
astra generate output/update_plan.json --article output/post_123.html

# Standalone draft upload
astra wp draft 123 output/post_123_updated.html
```

---

### Automated Batch Processing (`astra auto update`)

Update multiple WordPress posts across categories or tags in a single batch, with per-post error resiliency and summary telemetry reports:

```bash
# Update up to 10 published posts (default limit)
astra auto update

# Update up to 5 posts in the 'Technology' category as a dry run (local preview without publishing drafts)
astra auto update --category Technology --limit 5 --dry-run

# Update posts tagged with 'AI' and publish them directly as drafts for manual review
astra auto update --tag AI --all
```

**Summary Report Generated:** `output/batch_summary_report.json`

---

## Project Structure

```
astra-cms/
├── app/
│   ├── domain/              # Enterprise business rules & entities
│   ├── application/         # Use cases & application services
│   ├── infrastructure/      # External concerns
│   │   ├── config/          #   App settings (Pydantic Settings)
│   │   ├── database/        #   Database adapters
│   │   ├── logging/         #   Structured logging
│   │   ├── providers/       #   Third-party service adapters
│   │   └── wordpress/       #   WordPress REST API client
│   ├── presentation/        # User-facing interfaces
│   │   └── cli/             #   Typer CLI application
│   └── shared/              # Cross-cutting utilities & constants
├── tests/                   # Pytest test suite
├── docs/                    # Documentation
├── config/                  # Runtime configuration files
├── logs/                    # Application log files
├── backups/                 # Content backups
├── output/                  # Generated output
└── data/                    # Local data store
```

---

## Development

### Setup

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Commands

```bash
# Lint
ruff check app/ tests/

# Format
black app/ tests/

# Type-check
mypy app/

# Test
pytest

# Test with coverage
pytest --cov=app --cov-report=html
```

---

## Architecture

Astra CMS follows **Clean Architecture** (Hexagonal / Ports & Adapters):

```
┌─────────────────────────────────────────────┐
│              Presentation (CLI)             │
├─────────────────────────────────────────────┤
│              Application (Use Cases)        │
├─────────────────────────────────────────────┤
│              Domain (Entities & Rules)      │
├─────────────────────────────────────────────┤
│              Infrastructure (Adapters)      │
│   Config · Database · Providers · WP API    │
└─────────────────────────────────────────────┘
```

Dependencies point **inward** — outer layers depend on inner layers, never the reverse.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please make sure all CI checks pass before requesting a review.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <sub>Built with ♥ by the Astra CMS community</sub>
</div>
