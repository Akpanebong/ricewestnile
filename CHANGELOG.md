# Changelog

This documents the audit-and-fix engagement covering security, multicurrency
accounting, navigation, and UI/UX across the RICE West Nile enterprise system
(HR, Procurement, Finance/Accounting, M&E, GARCIS, Communication, Assets).

## Site-wide Crash Fixes

A systematic crawl of every registered URL (parameterless routes hit directly,
parameterized ones filled from real DB rows or synthetic IDs where no row
existed) plus static template sweeps (broken `{% url %}` names, missing
`template_name`/`render()` targets, and unsafe `{{ x|default:y }}` fallbacks)
turned up the following live 500s, all fixed:

- **`/notification/dashboard/`** — `NotificationDashboardView` pointed at a
  template that never existed. Added `templates/notifications/dashboard.html`.
- **`/garcis/compliance/documents/`** — the "Upload" button linked to a URL
  name with no view behind it at all. Added `ComplianceDocumentCreateView` +
  route, and fixed `ComplianceDocumentUpdateView` (also pointed at a
  non-existent template) — both now use the shared `compliance/form.html`,
  which now sets `enctype="multipart/form-data"` so the file field actually
  uploads.
- **M&E PDF exports** — `{{ now|default:today }}` in `reports/data_pdf.html`
  crashed because `today` was never a real context variable (Django doesn't
  silently swallow a failed `default` *argument*, only a failed main value).
  Also discovered `mne/monitoring/utils.py` was the only PDF export in the
  app built on `pdfkit`/`wkhtmltopdf` (an external binary) while every other
  module uses pure-Python `xhtml2pdf` — switched it to match, removing an
  environment dependency along with the bug. Dropped `pdfkit` from
  `requirements.txt`.
- **Assets "Add Maintenance" modal** — wrong URL namespace (`add_maintenance`
  instead of `asset:add_maintenance`), and the view's own error/GET path
  rendered a template that doesn't exist (it's modal-only, no standalone
  page) — both now redirect back to the asset detail page.
- **`hr/recruitment/jobs/<pk>/modal/`** — used `.get(pk=pk)` instead of
  `get_object_or_404`, so a stale/deleted job ID crashed instead of 404ing.
- **Procurement requisition detail** — `{{ po.reviewed_by.get_full_name|default:po.reviewed_by.username }}`
  (and the same for `checked_by`/`approved_by`) crashed whenever that field
  was still null, i.e. before that approval step happens — a normal state,
  not an edge case. Guarded all three in `templates/procurement/req_detail.html`.
- **Finance's `approval_flow.html`** referenced two URL names that don't
  exist (`approve_requisition`, `requisition_pdf` instead of the real
  `finance:approve_cash_req`/`finance:cash_req_pdf`) — not currently wired to
  any view, but fixed for correctness.

Also identified two dead, unreachable templates with the same class of stale
URL reference (`hr/device_list.html`, `com_app/communication/templates/communication/notifications.html`)
— neither is rendered by any view, so left as-is rather than building out
the missing functionality unprompted.

## Security & Infrastructure

- **Unauthenticated access to entire subsystems fixed.** Added
  `RequireLoginForModulesMiddleware` (`core/middleware.py`) protecting
  `/garcis/`, `/mne/monitoring/`, and `/asset/` at the middleware level
  (defense-in-depth, independent of any per-view decorator), redirecting
  anonymous requests to login.
- **Finance module had no access control on org-wide financial views.**
  Added `_is_finance_staff()` guard (superuser, or member of the Finance or
  Operations group) to `financial_ledger`, `financial_ledger_export`,
  `record_transaction`, and `chart_of_accounts` (`finance_app/finance/views.py`).
- **Insecure `DEBUG`/`SECRET_KEY`/`ALLOWED_HOSTS` defaults.** `enterprise/settings.py`
  now loads `.env` via `python-dotenv`, defaults to `DEBUG=False`, refuses to
  start with `DEBUG=False` and no `DJANGO_SECRET_KEY` set, and only allows
  `ALLOWED_HOSTS=["*"]` in debug mode. Added `.env.example` documenting the
  required variables and `.env` (gitignored) for local dev.
- **Password reset bypassed Django's password validators.** `account/views.py`
  `reset_password` now calls `validate_password()` and surfaces validation
  errors instead of accepting any string.
- **Custom error pages were dead/unwired.** Added `templates/400.html`,
  `403.html`, `404.html`, `500.html` (self-contained, branded, no traceback
  leakage) at the top-level templates directory where Django auto-discovers
  them.
- **Unbounded list-view queries.** Added pagination (`Paginator`, 25/page) to
  `asset_list`, `supplier_list`, `requisition_list`, and 9 GARCIS list views
  (policies, controls, decisions, stakeholder engagements, audit logs,
  findings, evidence, external audit engagements/findings), plus a
  redesigned shared `templates/pagination.html` include.

## Multicurrency & Accounting

- **Configurable organization base currency.** New `OrganizationSettings`
  singleton model (`core/models.py`) lets a deployment pick its base currency
  (not hardcoded UGX) once, locked automatically once real financial,
  procurement, or asset data exists (`has_existing_financial_data()`), and
  restricted to superusers. `core/services.get_base_currency()` is now the
  single source of truth, threaded through `format_money`,
  `display_amount_from_ugx`, `user_amount_to_ugx`, `currency_context`, and
  `FinancialTransaction`.
- **Genuine multicurrency ledger.** `FinancialTransaction` (`finance_app/finance/models.py`)
  now carries `currency`, `original_amount`, and `exchange_rate_used`
  alongside the existing base-currency `amount`, so donor reports can show
  the real originally-recorded figure, not just the converted one.
  `record_manual_transaction()` and the manual "Record Transaction" flow use
  this end-to-end.
- **Fixed: the three auto-populated transaction paths couldn't preserve
  original currency.** `record_cash_advance`, `record_accounting_expense`,
  and `record_admin_expense` used to hardcode the base currency because the
  upstream forms converted to base currency at entry time before the ledger
  ever saw the real currency. Fixed by:
  - Adding `currency` + `exchange_rate_used` to `CashRequisition` and
    `AdminExpenseNote`, and `currency` + `exchange_rate_used` to
    `AccountingForm`.
  - Adding `original_unit_cost` to `CashRequisitionItem` and
    `original_amount_received`/`original_amount_spent` to `AccountingItem`,
    and `original_proposed_budget` to `AdminExpenseNote`.
  - The existing base-currency fields (`unit_cost`, `proposed_budget`,
    `amount_spent`/`amount_received`) are **unchanged** — every existing
    template, report, and aggregate keeps working exactly as before.
  - The three entry forms (Fund Requisition, Admin Expense, Retirement) now
    have an explicit currency selector instead of silently assuming the
    submitting user's own display-currency preference.
  - Verified end-to-end with a real USD requisition, KES admin expense, and
    USD retirement, plus a simulated legacy row to confirm old data falls
    back safely to base-currency/rate 1.
- **Currency & Region settings page rebuilt** (`templates/core/currency_settings.html`)
  with a sub-nav + section-card layout: base currency (locked once data
  exists), per-user display currency, exchange rate table, and a currency
  equivalence matrix.
- Chart of Accounts (12 seeded default categories), Financial Ledger (with
  currency filter/breakdown and Excel export), and Record Transaction pages
  added under Finance.

## Navigation, Branding & Information Architecture

- **Finance → Accounting rebrand.** Renamed the module's *display* name from
  "Finance" to "Accounting" everywhere it appears as branding (page titles,
  sidebar headers, Quick Access, command palette) — the underlying Django
  app, URLs, and the "Finance" Group/role used in permission checks and
  workflow labels were deliberately left untouched.
- Added the missing **Accounting entry to the Quick Access dropdown** and the
  Cmd/Ctrl+K command palette (`templates/base.html`).
- Fixed a stale `reverse('core:currency_settings')` reference that would
  have 500'd the Procurement dashboard.
- Fixed empty-sidebar dead-ends in HR self-service (`leave_list` redirect
  messages now say what to do) and added a proper
  `account/includes/account_sidebar.html` for the My Account / profile area.

## UI/UX Redesign (Gentelella-inspired)

Adapted structural/visual patterns from the Gentelella v4 admin template
while keeping the app's own brand colors and architecture — elevation
tokens, spacing scale, and iconography stayed ours; only the layout patterns
were borrowed.

- **Design tokens** (`static/css/variables.css`): tightened elevation
  (`--surface-1-border`, `--surface-1-shadow`), added `--icon-tint-*` tokens
  (8% opacity) distinct from the existing 12%-opacity `--status-*` badge
  tokens.
- **Shared components** (`static/css/components.css`): `.page-header`
  (eyebrow/title/subtitle/actions), `.settings-layout`/`.settings-nav`/
  `.settings-section`/`.settings-row` (sub-nav + section-card pattern),
  `.metric-icon-tint`/`.metric-trend`/`.metric-value-row` (KPI cards),
  `.app-pagination`, `.avatar-circle` (+ 6 tone colors), `.badge-outline`,
  `.status-dot`, refined `.table`/`.btn-outline-*`/`.btn-icon`.
- **Buttons & tables** restyled system-wide (hairline borders, subtler
  headers, tighter padding) via the shared stylesheet — no per-template
  changes needed.
- Rolled the `.page-header` pattern out to Assets and Communication
  dashboards (Procurement/GARCIS/M&E kept their existing hero-banner
  headers, which already serve the same purpose).
- **"All Apps" hub redesigned** (`templates/enterprise/system_home.html`):
  distinctly-tinted per-module icon tiles (was: one accent color for all 7,
  flagged in the original audit as visually undifferentiated), `.page-header`,
  and `.settings-section` panels for Notifications, Compliance & Risk, and
  Account & Settings — the first two now show **real data** (unread
  notifications, live GARCIS risk/finding counts) instead of the previous
  static placeholder content.
- **Sidebar navigation redesigned** (`static/css/sidebar.css`): icons are now
  bare flat glyphs instead of boxed chips, active rows are bold in addition
  to the existing highlight, and the submenu no longer carries a persistent
  vertical rail — only the active item gets a tick mark. Pure CSS change,
  so it applies to every subsystem's sidebar automatically.
- **Forms redesigned** (`static/css/components.css`): added `.form-label`
  styling (previously unstyled), muted background on disabled/readonly
  fields, `.form-text` hint styling, brand-accent checkbox/switch color, and
  a quieter `.input-group-text` treatment for currency-symbol/unit chips.
  Applies to every form across the app via the shared stylesheet.
- Supplier list avatars switched from a single-color square to
  `.avatar-circle` with rotating tone colors.
- Cleaned up ~460 lines of dead, unrendered leftover content sitting after
  `{% endblock %}` in `templates/finance/account_form.html`.

## Migrations

- `account/0003_profile_display_currency` — per-user display currency.
- `core/0002_organizationsettings` — the base-currency singleton.
- `finance/0002_financialcategory_financialtransaction`,
  `0003_seed_chart_of_accounts`, `0004_financialtransaction_currency_and_more`,
  `0005_backfill_transaction_currency`,
  `0006_accountingform_currency_and_more` — the ledger and its currency
  fields, seeded chart of accounts, and the requisition/expense/retirement
  currency-capture fields described above.
