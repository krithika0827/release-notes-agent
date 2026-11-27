# FastAPI Release Notes: `0.162.0` → `0.165.0`

Covers every release after `0.162.0` up to and including `0.165.0` (`git log 0.162.0..0.165.0`, 189 commits: 0.162.1–0.162.7, 0.163.0–0.163.2, 0.164.0, 0.165.0).
Only the commits that affect users are listed. The rest were translation syncs, release-notes bot commits, docs/theme work, CI and dev-dependency bumps, and are omitted.

## Upgrade checklist

- Your project must run **Python 3.11 or newer**.
- Your environment must resolve **Starlette ≥ 1.6.0** and **AnyIO ≥ 4.1.0**. These are now hard install requirements.
- Nothing else in the public API was removed or renamed. All new parameters are optional and default to `None`, which keeps the old behavior.

---

## 💥 Breaking Changes

### Python 3.10 is no longer supported (0.162.6)
- `28eaf6a` Drop support for Python 3.10. `requires-python` is now `>=3.11` and the 3.10 trove classifier is gone.
  - **Migration:** Upgrade the interpreter to 3.11+. Projects pinned to 3.10 will stay on `fastapi<=0.162.5`, because pip refuses to install newer versions there.
  - The coroutine-detection fallback for Python 3.11 and 3.12 is now documented in a code comment. Detection behavior is unchanged.

### Minimum Starlette raised from `0.46.0` to `1.6.0` (0.164.0)
- `55ee14b` The request body limit feature builds on Starlette's `RequestBodyLimitMiddleware`, so `pyproject.toml` now requires `starlette>=1.6.0`. This is a dependency-floor change shipped inside a feature commit and is easy to miss.
  - **Migration:** Upgrade Starlette to 1.6.0 or newer. If you pin Starlette, relax the pin. Check any custom middleware or `starlette` subclasses against Starlette 1.x.

### AnyIO ≥ 4.1.0 is now required at runtime (0.162.4)
- `0902e8b` `anyio>=4.1.0` is now declared as a direct dependency. Previously FastAPI imported AnyIO without declaring it, and relied on Starlette to pull in a compatible version.
  - **Migration:** Environments pinned to AnyIO 3.x or 4.0.x must upgrade.

> No public function signatures were removed or changed incompatibly. The new `max_body_size`, `form_limits` and `max_concurrency` parameters are additive keyword arguments with `None` defaults.

---

## ✨ Features

### Dependency concurrency limits: `Depends(max_concurrency=...)` (0.163.0)
- `fc07dde` `Depends()` accepts a new keyword-only `max_concurrency: int | None = None` argument. It caps how many calls to a dependency run at once, for example to protect a database connection pool. Extra calls wait on an AnyIO semaphore and don't occupy worker threads.
  - **Dependencies with `yield`:** the slot is held until the cleanup code after `yield` finishes, at the time set by `scope`.
  - **Sharing a limit:** reuse the same `Depends(...)` object, for example an `Annotated` alias. Each new `Depends()` object gets its own limit, even for the same function.
  - **Scope of the limit:** it is per event loop and per worker process. A dependency value reused through the per-request cache doesn't count as another call.
  - **Validation:** the value must be a positive `int` or `None`. Anything else, including `bool`, `0` and negatives, raises `ValueError` when the declaration is created.
  ```python
  DBDep = Annotated[DBSession, Depends(get_db, max_concurrency=5)]
  ```
  - Docs: *Advanced → Advanced Dependencies → Limit dependency concurrency*.

### Configurable request body size limits: `max_body_size` (0.164.0)
- `55ee14b` New `max_body_size` (bytes) option on `FastAPI(...)`, `APIRouter(...)`, `include_router()`, `add_api_route()`, and every HTTP method decorator (`get`, `post`, `put`, `delete`, `options`, `head`, `patch`, `trace`).
  - The most specific setting wins: path operation, then router or `include_router()`, then app. `None` inherits from the enclosing level, and means unlimited if nothing is set. `0` allows only an empty body.
  - The limit counts the **whole body**, including form fields, all files and multipart overhead. Headers and URL are excluded. FastAPI counts bytes as they are read, so chunked uploads without `Content-Length` are covered too.
  - If the limit is exceeded before the response starts, FastAPI returns **HTTP 413**. Mounted apps inherit the parent app's limit and share its byte counter.
  - Invalid values (negative, non-int, `bool`) raise `ValueError`.
  - Caveat: middleware that reads the body before routing is subject to the app-level limit. See the "Middleware that reads the body" note in the docs.
  - Docs: *Advanced → Request Body Limits*.

### Configurable form parsing limits: `form_limits` (0.165.0)
- `b0a616d` New `form_limits` option, accepted in all the same places as `max_body_size`. It is a typed dict with `max_fields`, `max_files` and `max_part_size`. FastAPI forwards it to Starlette's `request.form(...)` when parsing `Form`, `File` and `UploadFile` parameters, including those declared in dependencies.
  - `max_fields`: maximum number of non-file fields (default 1,000).
  - `max_files`: maximum number of files in a multipart form (default 1,000).
  - `max_part_size`: maximum size in bytes of each text field (default 1 MiB).
  - Each key inherits independently across the app, router, `include_router()` and path operation levels.
  - Exceeding a parser limit returns **HTTP 400**. Use `max_body_size` to bound the total request size.
  - Keys are validated strictly (non-negative ints, unknown keys rejected).
  - If you call `request.form()` yourself, pass the limits on the first call, because Starlette caches the parsed form.
  - Docs: *Advanced → Request Body Limits → Set limits for form fields and files*.

### Python 3.15 support (0.162.3)
- `ed6f566` Added the Python 3.15 classifier and test coverage. A later change (`980cee9`, CI only) limits the full test matrix to 3.15.

---

## 🐛 Bug Fixes & Improvements

### Dependency cleanup under cancellation
- `eb2f492` **Fix synchronous dependency cleanup on cancellation** (0.162.5). For sync generator dependencies, `__enter__` now runs outside the `try` block, so `__exit__` is only called after a successful enter. Cleanup now also runs for `BaseException`, which includes cancellation. Previously only `Exception` was handled. `__exit__` runs inside a shielded cancel scope, so it can finish in a worker thread even if the request is cancelled, for example on client disconnect.
- `5f4f9c1` **Fix async yield dependency cleanup on cancellation** (0.162.7). The code after `yield` in `async def` dependencies now runs in a shielded scope, so cancellation (such as a disconnect or timeout) no longer interrupts the teardown of resources like DB sessions or locks. The scope is shared per request stack so exit order stays last-in-first-out, and cancellation is re-raised after cleanup.

### OpenAPI
- `a1a05b7` **Fix OpenAPI for response models with nested computed fields** (0.163.1, #14490). Computed-field detection previously inspected only the top-level model. It now walks nested models and generic arguments (it is cycle-safe), so `@computed_field` properties on nested models are included correctly in the generated schemas, in particular with `separate_input_output_schemas=False`.

### Performance / internals
- `2d64371` **Refactor query, header and form parameter extraction** (0.163.2). Extra (undeclared) params and form fields for Pydantic parameter models are now grouped in a single pass, instead of rescanning for each key. Repeated keys keep their list semantics, and form extraction is skipped when no non-model form fields are declared. This is intended as a behavior-preserving change with a new test suite (`tests/test_parameter_extraction.py`).

### AI-agent tooling shipped in the package
- `a1c96b4` Add parameter-model guidance to the bundled FastAPI agent skill (0.162.1).
- `afd2a57` Add FastAPI Cloud guidance to the bundled skill (0.162.2).
- `fc07dde`, `55ee14b` and `b0a616d` also update the bundled skill with guidance for `max_concurrency`, `max_body_size` and `form_limits`.
- `ed6f37b` Add "Developing FastAPI apps with AI" documentation (0.162.2).

---

## Version map

| Release | Notable commits |
|---|---|
| 0.162.1 | `a1c96b4` |
| 0.162.2 | `afd2a57`, `ed6f37b` |
| 0.162.3 | `ed6f566` (Python 3.15) |
| 0.162.4 | `0902e8b` (AnyIO ≥ 4.1.0) |
| 0.162.5 | `eb2f492` (sync cleanup fix) |
| 0.162.6 | `28eaf6a` (**drop Python 3.10**) |
| 0.162.7 | `5f4f9c1` (async cleanup fix) |
| 0.163.0 | `fc07dde` (`max_concurrency`) |
| 0.163.1 | `a1a05b7` (computed fields in OpenAPI) |
| 0.163.2 | `2d64371` (param extraction refactor) |
| 0.164.0 | `55ee14b` (`max_body_size`, **Starlette ≥ 1.6.0**) |
| 0.165.0 | `b0a616d` (`form_limits`) |

*Omitted as non-user-facing:* translation updates, release-notes bot commits, docs-only changes (Zensical theme, snippet layout, AI-agent notice), CI/workflow changes, sponsor and people updates, and dev/test/docs dependency bumps (for example `1c78a21` `pydantic-ai-slim`, which only affects the translations tooling group).
