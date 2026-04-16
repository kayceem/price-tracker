 # Full-Codebase Refactor Plan for price-tracker

  ## Summary

  Refactor the repository into a modular monolith with strict boundaries between:

  - Application composition: app startup, schedulers, dependency wiring, settings
  - Domain modules: portfolio, market data, alerts, messaging, user credentials
  - Infrastructure adapters: NEPSE HTTP client, Telegram, Twilio, Playwright/MeroShare, SQLAlchemy, filesystem/CSV
  - Interfaces: FastAPI HTTP routes, background jobs, CLI commands

  The refactor should be treated as a full redesign for maintainability, not a file shuffle. The main outcomes are:

  - remove direct cross-layer imports from routes/services into ORM and external clients
  - replace stateful globals and module-level side effects with injected services
  - isolate CSV/pandas portfolio analysis from the rest of the runtime
  - make the app testable with clear contracts and adapter seams
  - consolidate startup/runtime entrypoints so API, web UI, jobs, and CLI tools compose cleanly

  ## Implementation Changes

  ### 1. Establish the new architecture and boundaries

  Adopt this package shape as the target:

  - src/app/
      - app factory, DI wiring, startup/shutdown, scheduler registration, shared dependencies
  - src/modules/portfolio/
      - domain models, service layer, CSV repositories, analytics/report builders, HTTP handlers
  - src/modules/market_data/
      - script catalog, script details refresh, floorsheet ingestion/query services
  - src/modules/alerts/
      - tracker rules, tracker CRUD, alert evaluation, scheduling use cases
  - src/modules/messaging/
      - Telegram/WhatsApp command handling mapped onto application services
  - src/modules/users/
      - user registration, MeroShare credential management
  - src/infrastructure/db/
      - engine/session setup, ORM mappings, repositories, migrations support
  - src/infrastructure/clients/
      - NEPSE client, Twilio adapter, Telegram adapter, MeroShare/Playwright adapter
  - src/infrastructure/files/
      - CSV access, report output, file path policies
  - src/interfaces/http/
      - FastAPI routers for API and server-rendered web
  - src/interfaces/cli/
      - CLI entrypoints for refresh/fetch/report jobs
  - src/shared/
      - config, clock/timezone helpers, logging, common exceptions, result types

  Rules to enforce:

  - routes call application services only
  - repositories hide SQLAlchemy queries from routes and bot handlers
  - external APIs are accessed only through adapters
  - pandas/DataFrame logic stays inside the portfolio module and never leaks into route handlers
  - no module-level runtime singletons except pure config/logging bootstrap

  ### 2. Replace current coupling hotspots

  Refactor the current problem areas in this order:

  1. Startup/runtime composition

  - Replace src/api/main.py, src/web/app.py, and web.py with app factories.
  - Move scheduler setup, bot lifecycle, webhook registration, and cron definitions into src/app/bootstrap.py or
    equivalent.
  - Split “HTTP API”, “web UI”, and “background jobs” into separately composable startup units.

  2. Database boundary

  - Split current src/database into:
      - ORM models
      - repository layer
      - Pydantic DTOs / API schemas
      - session/unit-of-work utilities
  - Stop exporting mixed ORM + schema + session objects from a single __init__.py.
  - Introduce repository interfaces for scripts, script details, trackers, brokers, floorsheets, users, and MeroShare
    users.

  3. Market data module

  - Move NEPSE client/auth/token/WASM logic behind a NepseMarketDataClient.
  - Extract script refresh and floorsheet ingestion into separate use cases:
      - RefreshScriptDetails
      - FetchFloorsheetForDate
      - QueryFloorsheet
  - Move payload mapping out of ORM persistence flows.
  - Normalize naming from script to either security or stock; choose one term and use it everywhere.

  4. Alerts and messaging

  - Separate tracker lifecycle from Telegram conversation state.
  - Create application services for:
      - register user
      - create tracker
      - list trackers
      - evaluate trackers
      - send alert
  - Make Telegram and WhatsApp thin adapters that translate inbound messages to use-case calls and format responses.
  - Remove direct bot handlers querying ORM models or calling NEPSE refresh logic.

  5. Portfolio module

  - Split the 475-line analyzer into:
      - CSV readers/loaders
      - transaction normalization
      - holdings engine
      - realized P&L engine
      - interest engine
      - report/query service
  - Replace the global analyzer = PortfolioAnalyzer(config.username) with request-scoped or dependency-provided
    services.
  - Route handlers should return typed response DTOs instead of hand-shaped DataFrame conversions inline.
  - Keep pandas internal to analytics/report generation only.

  6. Scripts and notebooks

  - Move reusable logic from scripts/ into src/interfaces/cli/ and keep scripts as thin wrappers or remove them.
  - Treat notebooks as exploratory only; do not let production logic depend on notebook code.
  - Define one supported CLI surface for recurring jobs: report generation, floorsheet fetch, script refresh,
    MeroShare sync.

  7. Shared concerns

  - Move timezone helpers, encryption helpers, and validation helpers out of the generic utils bucket into named
    modules under shared.
  - Replace broad except: and stringly-typed errors with domain-specific exceptions and HTTP error translation at the
    edge.
  - Centralize logging format and config loading.

  ### 3. Public interfaces and contracts to introduce/change

  Introduce explicit interfaces and DTOs:

  - Settings object for all config, replacing scattered module constants
  - Repository contracts:
      - ScriptRepository
      - ScriptDetailsRepository
      - FloorsheetRepository
      - TrackerRepository
      - UserRepository
      - MeroShareUserRepository
  - Service/use-case contracts:
      - PortfolioQueryService
      - TrackerService
      - AlertEvaluationService
      - ScriptRefreshService
      - FloorsheetIngestionService
      - MessagingCommandService
  - API response models for portfolio and floorsheet endpoints
  - Command DTOs for inbound Telegram/WhatsApp actions
  - Typed exceptions:
      - NotFoundError
      - ValidationError
      - ExternalServiceError
      - AuthenticationError
      - ConflictError

  API changes to plan for:

  - keep endpoint URLs stable initially where possible
  - change route internals to use DTOs and service calls
  - if response shapes need redesign, version them or batch them into one documented API cleanup pass after service
    extraction

  ### 4. Execution sequence

  Implement the refactor in these phases:

  1. Foundation

  - create the target package layout
  - introduce shared settings, logging, exceptions, and app factory
  - add contract tests and fixtures before moving behavior

  2. Data layer extraction

  - split ORM/session/schema concerns
  - create repositories and migrate HTTP/bot code to use them
  - keep tables and Alembic history intact during this phase

  3. Market data extraction

  - move NEPSE client and script/floorsheet use cases behind services
  - move schedulers to app bootstrap
  - remove direct refresh calls from handlers

  4. Portfolio extraction

  - isolate CSV repositories and analytics engines
  - replace route-level DataFrame shaping with DTO mappers
  - define stable interfaces for portfolio summary, holdings, transactions, pools, interest, stats

  5. Messaging/alerts extraction

  - move Telegram and WhatsApp into adapters around tracker services
  - remove bot-global lifecycle assumptions from module import time

  6. CLI/reporting cleanup

  - convert report/fetch scripts to formal CLI commands
  - keep notebooks out of runtime architecture

  7. Final cleanup

  - delete dead code, empty packages, stray re-exports, unused imports


  Add tests before and during the refactor in this minimum set:

  - Unit tests for:
      - NEPSE payload mapping
      - tracker price-range and cooldown evaluation
      - portfolio holdings, realized P&L, and interest calculations
      - floorsheet grouping and summary logic
      - encryption/decryption and settings parsing
  - Repository tests for:
      - script/floorsheet/tracker CRUD behavior
      - idempotent floorsheet ingestion
      - broker/script upsert behavior
      - webhook endpoints for Telegram and WhatsApp
  - Adapter tests with mocks/fakes for:
      - NEPSE client
      - Telegram bot
      - Twilio client
      - Playwright/MeroShare flows where practical
  - Regression fixtures:
      - sample CSV files for one user
      - sample NEPSE today-price payload
      - sample floorsheet payload pages
  - Acceptance scenarios:
      - refreshing tracked prices updates script details without route involvement
      - tracker alerts trigger once, respect cooldown, and send formatted messages
      - portfolio dashboard endpoints produce stable numbers from fixture CSVs
  - This is a full redesign refactor, so module responsibilities, startup structure, and internal interfaces can
    change substantially.
  - Primary optimization is maintainability and testability, not short-term delivery speed.
  - Database schema should remain compatible unless a later dedicated migration phase is explicitly planned.
  - Existing endpoint paths should stay stable during the first refactor pass unless a route is clearly broken or
    redundant.
  - scripts/ and notebooks/ are in scope for cleanup, but notebooks are not part of the supported production surface.
  - Current baseline has no meaningful tests, so test scaffolding is a prerequisite, not a finishing step.