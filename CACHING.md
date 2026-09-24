# API caching

| Endpoint | TTL | Invalidation |
| --- | ---: | --- |
| `/api/articles/latest/` | 60 seconds | Invalidated on Article save/delete |
| `/api/articles/top-stories/` | 60 seconds | Invalidated on Article save/delete |
| `/api/articles/trending/` | 1 hour | Recomputed by Celery every 15 minutes |
| `/api/matches/live/` | 10 seconds | TTL-only; refreshed by polling |
| `/api/standings/` | 5 minutes | TTL-only; refreshed by standings sync |
| `/api/ticker/` | 25 seconds | TTL-only; entries are editor-managed |
| `/api/search/?q=...` | 60 seconds | Per-query TTL; content changes naturally expire |

Redis is the production cache backend. Read endpoints fall back to a database query if Redis is unavailable during local development.
