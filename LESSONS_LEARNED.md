# InvApp: Lessons Learned & Engineering Insights

## 🚀 Backend Performance
- **N+1 Query Resolution:** Always use `.annotate(Count('related_model'))` for statistics on list views (like dashboards). Avoid calculating counts inside a Python loop, as it triggers $O(n)$ database hits.
- **Queryset Optimization:** Use `select_related` for OneToOne/ForeignKey and `prefetch_related` for ManyToMany to minimize database roundtrips.

## 🔒 Security & Configuration
- **Fail-Safe Defaults:** `DEBUG` should always default to `False` in code. Use environment variables to explicitly enable it for local development.
- **Secret Protection:** Never provide a default fallback for `SECRET_KEY` in production code. Use `ImproperlyConfigured` exceptions to force environment variable setup during deployment.
- **Environment Parity:** Switching `DEBUG` from `False` to `True` locally can expose missing dependencies (like `cloudinary-storage`) that were only being initialized in specific environment paths.

## 🛠 Admin & UX
- **Bulk Data Handling:** Integrating `django-import-export` early provides massive value for non-technical administrators (Directors) by allowing CSV/Excel management of core models.
- **Admin Inlines:** Use `TabularInline` for related models (like `GalleryImage` or `ScheduleItem`) to provide a "Single Page" editing experience for complex entities like `Event`.

## 📈 SEO & Marketing
- **Semantic HTML:** Ensure `<h1>` tags are keyword-rich rather than purely functional.
- **Meta Overrides:** Each major template should override the `title` and `meta_description` blocks from `base.html` to prevent duplicate content flags.
- **Performance vs. UX:** Avoid heavy social media iframes; use high-performance SVG icons and direct links for cross-promotion to maintain high PageSpeed scores.

## 🌍 Internationalization (i18n)
- **English-First Strategy:** Always use English as the primary source language in code and templates. This ensures a clean base for `makemessages` and avoids character encoding issues (UTF-8) common with non-ASCII source strings.
- **Translation Marking:** Consistently wrap all user-facing strings in `_()` (backend) or `{% translate %}` (frontend). Use `{% blocktranslate %}` for strings containing variables or complex HTML.
- **Dynamic Language Selection:** Implementing `preferred_language` on models (like `Guest`) allows for personalized UX while maintaining a system-wide default (Romanian).

## 👥 Guest Management & RSVP Tracking
- **RSVP Source Verification:** Distinguishing between digital RSVPs (via the platform) and manual updates (phone/physical) using visual "ticks" (e.g., Purple for Digital, Blue for Manual) significantly reduces host confusion.
- **Invitation Lifecycle Tracking:** Tracking the delivery method (Digital vs. Paper) allows hosts to manage their physical stationery budget while leveraging the speed of digital links.
- **Bulk Import Flexibility:** Customizing the Excel import logic to map human-readable strings (like "digital" or "paper") to model constants ensures data consistency during high-volume guest list setup.

## 📱 Mobile-First UX & Foldable Optimization
- **Fold-Aware Design:** For devices like the Galaxy Fold 5, using flex-based adaptive containers rather than fixed widths ensures the UI remains professional on both narrow cover screens and wide tablet-like displays.
- **Tactile Inputs:** High-density tactile wrappers for system pickers (like Time/Date) increase usability by providing larger tap targets without losing the native OS accessibility benefits.
- **Background Autosave UX:** Implementing debounced AJAX saves during complex multi-step wizards prevents data loss and builds user confidence via visual "Last Saved" indicators.
- **User Redirection & Proactive Feedback:** After multi-step form completion (like Event Publishing), redirecting to a central hub (Dashboard) instead of the same form prevents confusion. Supplementing this with "Attention" messages (`messages.warning`) about non-critical missing data (e.g., missing photos or logistics) encourages completion without blocking the primary workflow.

## 💾 Database Migrations (SQLite Specific)
- **Table Recreation Issues:** SQLite does not support robust `ALTER COLUMN` operations. Adding a `NOT NULL` constraint to an existing column during a complex refactor can trigger `IntegrityError` if the migration fails to handle default values correctly during table recreation.
- **Recovery Strategy:** If a migration gets "stuck" due to faked states or SQLite limitations:
    1. Manually sync the schema using `cursor.execute('ALTER TABLE ... ADD COLUMN ...')`.
    2. Reset the migration history for that app in `django_migrations`.
    3. Run `makemigrations` and `migrate --fake-initial` to let Django take over the current state.

## 🎨 Premium Live Builder & Split-Screen UX
- **Split-Screen Strategy:** For desktop-class SaaS builders, moving from a stacked grid to a `flex-row` split-screen layout (70/30 or 60/40) provides immediate visual feedback. The form stays on the left (scrollable), while the preview stays sticky on the right.
- **Smartphone Mockup Realism:** Using realistic aspect ratios (9:19) and "hardware" details like thick bezels and a top notch significantly improves the perceived value of the product during the creation phase.
- **Contextual Headers:** Moving the wizard's progress and status indicators *inside* the scrollable form column (instead of spanning the whole width) maintains a better visual connection with the fields being edited.
- **Responsive Layout:** Always use `lg:flex-row flex-col` to ensure the split-screen automatically stacks back into a mobile-friendly layout without duplicating code or complex media queries.

## 🛠 Template System & Path Resolution
- **Standard Paths:** Always use forward slashes `/` in `{% extends %}` and `{% include %}` tags (e.g., `"invapp/base.html"`). Using colons `:` or other delimiters will trigger a `TemplateDoesNotExist` error, as Django's standard loader expects filesystem-style paths relative to the `templates` directories.
