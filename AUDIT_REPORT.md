# InvApp: Comprehensive Quality & Security Audit Report
**Date:** February 22, 2026
**Role:** Tech Lead & Orchestrator

## Executive Summary
This audit evaluated the 'InvApp' Django 5.x codebase across security, backend architecture, and frontend performance. While the foundation is solid and adheres to modern Django standards, there are critical performance bottlenecks and configuration risks that must be addressed before further scaling.

---

## 🔴 CRITICAL FINDINGS

### 1. N+1 Query Bottleneck in `dashboard_view`
**File:** `invapp/views.py`
**Observation:** The dashboard iterates over all user events and performs two separate database queries per event to calculate `confirmed_count` and `total_guests_count`. 
**Impact:** As a user accumulates events, the dashboard loading time will increase linearly ($2n+1$ queries), leading to severe performance degradation.
**Recommendation:** Use Django's `.annotate()` with `Count` and `Q` filters to fetch all counts in a single optimized query.

### 2. Insecure Production Defaults
**File:** `wedding_project/settings.py`
**Observation:** `DEBUG` defaults to `True` if the `RENDER` environment variable is missing. Additionally, `SECRET_KEY` has a fallback to a known insecure string.
**Impact:** If the environment is misconfigured or moved from Render, the application might expose sensitive tracebacks or use a weak secret key in production.
**Recommendation:** Default `DEBUG` to `False` and remove the fallback for `SECRET_KEY` in production environments. Force an error if `SECRET_KEY` is missing.

---

## 🟡 WARNINGS

### 1. Inefficient Sorting in `guest_list`
**File:** `invapp/views.py`
**Observation:** Sorting for the guest list is performed in memory using Python's `list.sort()` after fetching all records.
**Impact:** For events with hundreds of guests, this consumes unnecessary server memory and CPU cycles.
**Recommendation:** Move sorting logic to the database level using `.order_by()`.

### 2. Frontend Performance: Tailwind CDN
**File:** `invapp/templates/invapp/base.html`
**Observation:** The project uses the Tailwind Play CDN (`cdn.tailwindcss.com`) in production.
**Impact:** The browser must download a large (~100KB+) script and compile styles on the fly, increasing the "Time to Interactive" (TTI).
**Recommendation:** Compile Tailwind CSS into a minified static file using the `django-tailwind` package or a custom build step.

### 3. Missing CSRF Protection on Preview Endpoints
**File:** `invapp/views.py`
**Observation:** `event_preview` and `event_preview_view` are marked with `@csrf_exempt`.
**Impact:** While these are read-only previews, `@csrf_exempt` should be used sparingly.
**Recommendation:** Ensure these views are strictly used within `<iframe>` contexts with proper `X-Frame-Options` and investigate if CSRF tokens can be passed via the POST request from the frontend.

---

## 🟢 OPTIMIZATIONS

### 1. Database Schema Refinement
**File:** `invapp/models.py`
**Observation:** Several properties on the `Guest` model (like `attending_count`) access related `rsvp_details`. 
**Optimization:** While `select_related` is currently used in views, consider moving these calculations to a Custom QuerySet/Manager to ensure efficiency is maintained across all views automatically.

### 2. Image Optimization (Core Web Vitals)
**File:** `invapp/templates/invapp/landing_page_tailwind.html`
**Observation:** Hero images and design previews are served as high-res PNG/JPG.
**Optimization:** Implement WebP conversion for user-uploaded images and ensure `SiteImage` assets are served from a CDN with appropriate `width/height` attributes to prevent layout shifts (CLS).

### 3. Stripe Idempotency
**File:** `invapp/views.py`
**Observation:** The Stripe webhook handles `checkout.session.completed` but does not explicitly check if a transaction has already been processed (e.g., via a transaction log).
**Optimization:** Add a local `Payment` or `Transaction` model to record processed Stripe Session IDs to ensure 100% idempotency.

---

## QA & SECURITY SIGN-OFF
- **Security Agent:** Identified configuration risks (DEBUG/SECRET_KEY). Verified social auth is correctly restricted.
- **Backend Architect:** Identified N+1 query patterns. Validated schema integrity.
- **Frontend Engineer:** Flagged CDN usage. Confirmed correct use of `{% static %}` and `whitenoise`.

**Status:** ⚠️ **NEEDS ATTENTION** (Fix Critical N+1 and Security Defaults before next release).
