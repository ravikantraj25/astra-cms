<div align="center">

# ✦ Astra CMS

**A modern, AI-powered headless CMS migration and management toolkit.**

[![CI](https://github.com/astra-cms/astra-cms/actions/workflows/ci.yml/badge.svg)](https://github.com/astra-cms/astra-cms/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

</div>

---

## Overview

**Astra CMS** is an open-source toolkit designed to streamline CMS migrations, content management, and AI-powered content transformations. Built with clean architecture principles and a modular plugin system, Astra CMS gives developers full control over their content pipelines.

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
git clone https://github.com/astra-cms/astra-cms.git
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

```bash
# Show the current version
astra version

# Run system diagnostics
astra doctor
```

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
