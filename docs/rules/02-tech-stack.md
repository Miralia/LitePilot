# 02 — Tech Stack

## Runtime and Language

| Item | Detail |
|---|---|
| Language | Python 3.11+ |
| CI Python version | Python 3.12 |
| Async runtime | asyncio (native), integrated with FastAPI/Uvicorn |

---

## Backend Framework

| Item | Detail |
|---|---|
| Web framework | FastAPI |
| ASGI server | Uvicorn |
| Data validation | Pydantic v2 (`BaseModel`, `BaseSettings`, `model_validator`) |
| Settings management | `pydantic-settings` (`BaseSettings` class in `app/core/config.py`) |

---

## Database

| Item | Detail |
|---|---|
| Default database | SQLite |
| Optional database | PostgreSQL (configured via `DB_TYPE` and related env vars) |
| ORM | SQLAlchemy |
| Migration tool | Alembic (`database/versions/`) |
| PostgreSQL extras | `app/modules/postgresql/` module; setup guide at `docs/postgresql-setup.md` |

---

## Caching

| Item | Detail |
|---|---|
| File-based cache | `FileCache` / `AsyncFileCache` in `app/core/cache.py` |
| Redis | Optional; `app/modules/redis/` module; used for distributed caching when configured |
| In-process cache | Decorator helpers `fresh` / `async_fresh` on `FileCache` |

---


## Module Integrations

### Download Clients
| Module | Directory |
|---|---|
| qBittorrent | `app/modules/qbittorrent/` |

### Media Servers
| Module | Directory |
|---|---|
| Emby | `app/modules/emby/` |

### Message Channels
| Module | Directory |
|---|---|
| Telegram | `app/modules/telegram/` |

### Metadata Sources
| Module | Directory |
|---|---|
| TMDB | `app/modules/themoviedb/` |
| Bangumi | `app/modules/bangumi/` |

---

## Dependency Management

| Item | Detail |
|---|---|
| Runtime source | `requirements.in` — production/runtime dependencies only |
| Dev/test/lint/build source | `requirements-dev.in` — includes runtime plus pytest, coverage tooling, pylint, and build support |
| Compatibility entry | `requirements.txt` — delegates to `requirements.in`; not a committed cross-platform lock |
| Runtime install | `pip install -r requirements.txt` |
| Dev/test/lint/build install | `pip install -r requirements-dev.in` |

---

## Quality Tooling

| Tool | Purpose | Command |
|---|---|---|
| pytest | Test runner | `pytest tests/test_xxx.py` |
| pylint | Static analysis | `pylint app/` |
| safety | Dependency vulnerability scan | `safety check -r requirements.txt --policy-file=safety.policy.yml` |

---

## Deployment

| Method | Detail |
|---|---|
| systemd + nginx | 唯一部署方式；后端常驻服务，前端静态产物由 nginx 托管 |
| Local CLI | `moviepilot` CLI for source-based install; see `docs/cli.md` |
| Frontend | Vue/TypeScript SPA served from `public/`; source in `web/` |
| Frontend proxy | Local Node `service.js` proxies `/api` to the backend for CLI-managed development installs |

*Last Updated: 2026-11-26*
