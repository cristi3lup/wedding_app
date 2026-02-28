# InvApp: Lessons Learned & Engineering Insights

## 🚀 Backend Performance
- **N+1 Query Resolution:** Always use `.annotate(Count('related_model'))` for statistics on list views (like dashboards). Avoid calculating counts inside a Python loop, as it triggers $O(n)$ database hits.
- **Queryset Optimization:** Use `select_related` for OneToOne/ForeignKey and `prefetch_related` for ManyToMany to minimize database roundtrips.

## 🔒 Security & Configuration
- **Fail-Safe Defaults:** `DEBUG` should always default to `False` in code. Use environment variables to explicitly enable it for local development.
- **Secret Protection:** Never provide a default fallback for `SECRET_KEY` in production code. Use `ImproperlyConfigured` exceptions to force environment variable setup during deployment.
- **Environment Parity:** Switching `DEBUG` from `False` to `True` locally can expose missing dependencies (like `cloudinary-storage`) that were only being initialized in specific environment paths.
- **CSRF in Proxy Environments (Render/Cloudflare):** When running behind multiple proxies (Cloudflare -> Render), standard cookie-based CSRF often fails due to Origin/Referer mismatches. 
    - **Fix:** Set `CSRF_USE_SESSIONS = True` to store tokens in the session instead of a separate cookie. 
    - **Fix:** Explicitly define `SESSION_COOKIE_DOMAIN = '.yourdomain.ro'` to ensure cookies work across root and subdomains (like `www`).
    - **Harden:** Ensure `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` and `CSRF_TRUSTED_ORIGINS` are correctly configured with the actual production domain.

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
- **Invitation Method Terminology:** Using "Digital" and "On Paper" instead of "Physical Invitation" resonates better with users. Consistently updating model labels, form fields, and help texts ensures a seamless UX across the guest creation and management workflow.
- **Field vs. Property Conflicts:** Avoid defining a database field with the same name as a model property (e.g., `attending_count`). This can lead to unpredictable behavior in forms and QuerySets. Always prefer the property for calculated logic and rename the underlying field if persistence is required.
- **English-First Strategy (Mandatory):** Always use English as the primary source language in code, model labels, and templates. Mark strings for translation using `_()` or `{% translate %}`. This ensures a clean base for `makemessages` and prevents character encoding issues. Even if the user requests specific non-English text, implement it as a translation of an English original.

## 📱 Mobile-First UX & Foldable Optimization
- **Fold-Aware Design:** For devices like the Galaxy Fold 5, using flex-based adaptive containers rather than fixed widths ensures the UI remains professional on both narrow cover screens and wide tablet-like displays.
- **Tactile Inputs:** High-density tactile wrappers for system pickers (like Time/Date) increase usability by providing larger tap targets without losing the native OS accessibility benefits.
- **Background Autosave UX:** Implementing debounced AJAX saves during complex multi-step wizards prevents data loss and builds user confidence via visual "Last Saved" indicators.
- **User Redirection & Proactive Feedback:** After multi-step form completion (like Event Publishing), redirecting to a central hub (Dashboard) instead of the same form prevents confusion. Supplementing this with "Attention" messages (`messages.warning`) about non-critical missing data (e.g., missing photos or logistics) encourages completion without blocking the primary workflow.

## 🎨 UI/UX & Mobile Optimization
- **Urgency Bars & Mobile Readability:** Avoid making text too small (e.g., below 10px) even to save space. Users prefer readability over a crowded bar. Large, bold elements like fire emojis and countdowns should remain prominent. Always prioritize clear, high-contrast visibility for marketing elements on mobile screens.

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

## 💳 Payments, Vouchers & Conversions
- **Payment Bypass for 100% Vouchers:** When implementing discount systems, ensure that 100% vouchers (Free Upgrades) completely bypass the payment gateway (Stripe) to reduce friction and avoid processing errors for zero-value transactions.
- **Inline Voucher UI:** For mobile-first SaaS, keep voucher inputs inline rather than in modals. Using Alpine.js for real-time validation provides immediate feedback without full page reloads.
- **Backend Validation (Security):** Never trust the price calculated by the frontend. Always re-verify the voucher validity and discount percentage on the backend before performing an upgrade.

## 📈 Marketing & Growth Engines
- **Wedding Fair "Fair Mode":** High-urgency campaigns benefit from fixed top banners with real-time countdowns. Driving traffic to WhatsApp for personalized lead generation provides higher conversion than static forms.
- **Single-Use URL Vouchers:** Automating the application of vouchers via URL parameters (`?v=CODE`) reduces friction. Persisting these in the user's session ensures they are applied even if the user navigates away before signing up.
- **Campaign Attribution:** Tracking `campaign_name`, `used_at`, and `used_by` on vouchers is essential for measuring ROI on specific marketing events (like wedding fairs).
- **Automated Voucher Generation:** Using Django management commands to generate batches of unique codes and exporting them to CSV allows for quick distribution via WhatsApp or email after physical contracts are signed.
- **Plan-Specific Vouchers:** Restricting vouchers to specific subscription tiers prevents revenue leakage (e.g., applying a "Basic" discount to a "Premium" plan).
- **Bulk Create & M2M Relations:** When using `bulk_create` for performance, remember that it does not handle ManyToMany relationships. You must manually assign these (e.g., using `.set()`) after the main objects are created.
- **Scheduled Vouchers:** Adding a `valid_from` field allows marketing teams to generate and distribute vouchers ahead of a campaign start date without worrying about early redemption.
# #   <ب�  L a n d i n g   P a g e   U X :   B o t t o m   D o c k   N a v i g a t i o n 
 -   * * F l o a t i n g   N a v i g a t i o n   S t r a t e g y : * *   I m p l e m e n t i n g   a   ' B o t t o m   D o c k '   u s i n g    a c k d r o p - b l u r - m d   a n d    i x e d   b o t t o m - 6   p r o v i d e s   a   m o d e r n ,   a p p - l i k e   f e e l   f o r   l a n d i n g   p a g e s . 
 -   * * S e l e c t i v e   N a v   H i d i n g : * *   W h e n   a   l a n d i n g   p a g e   r e q u i r e s   a   c u s t o m   n a v i g a t i o n   p a t t e r n   ( l i k e   a   d o c k ) ,   u s e   C S S   o v e r r i d e s   i n   t h e   h e a d _ e x t r a   b l o c k   ( e . g . ,    o d y   >   d i v   >   n a v   {   d i s p l a y :   n o n e   ! i m p o r t a n t ;   } )   t o   h i d e   t h e   s t a n d a r d    a s e . h t m l   n a v i g a t i o n   w i t h o u t   a f f e c t i n g   o t h e r   p a g e s . 
 -   * * L a y e r i n g   ( z - i n d e x ) : * *   E n s u r e   t h e   b o t t o m   d o c k   h a s   a   h i g h   z - i n d e x   ( e . g . ,   z - [ 1 0 0 ] )   t o   s t a y   a b o v e   a l l   s e c t i o n   c o n t e n t ,   e s p e c i a l l y   o n   m o b i l e . 
 -   * * F a i r   B a n n e r   C o m p a t i b i l i t y : * *   W h e n   h i d i n g   t h e   t o p   n a v ,   e n s u r e   c r i t i c a l   m a r k e t i n g   e l e m e n t s   ( l i k e   F a i r   B a n n e r s )   a r e   e x p l i c i t l y   e x c l u d e d   f r o m   t h e   h i d e   r u l e   i f   t h e y   a r e   a l s o   u s i n g    i x e d   t o p - 0 .  
 