# invapp/urls.py
from django.urls import path
from django.contrib import admin
# Import views from the current app (we'll create the view next)
from invapp import views
from django.contrib.auth import views as auth_views


app_name = 'invapp'

urlpatterns = [
# --- TEMPORARY FIX URL ---
    path('faq/', views.faq_page, name='faq'),
    path('feedback/', views.submit_feedback, name='submit_feedback'),
    path('fix-domain/', views.fix_site_domain, name='fix_domain'),
    path('admin/', admin.site.urls),
    path('upgrade/<int:plan_id>/', views.manual_upgrade_page_view, name='manual_upgrade_page'),
    path('upgrade/', views.upgrade_plan, name='upgrade_plan'),
    # Keep the root view for now (optional, could be removed later)
    path('', views.landing_page_view, name='landing_page'),
    # path('', views.invitation_view, name='invitation_detail'),
    path('terms-and-conditions/', views.terms_of_service_view.as_view(), name='terms_and_conditions'),
    path('privacy-policy/', views.privacy_policy_view.as_view(), name='privacy_policy'),
    # path('rsvp/<int:guest_id>/', views.rsvp_view, name='rsvp_form'),
    path('accounts/signup/', views.signup_view, name='signup'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='account/login.html'), name='login'),
    # --- Add the new unique invite path ---
    path('event/<int:event_id>/preview-demo/', views.event_preview_demo, name='event_preview_demo'),
    path('invite/<uuid:guest_uuid>/', views.invitation_rsvp_combined_view, name='guest_invite'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('invite/<uuid:guest_uuid>/thank-you/', views.guest_invite_thank_you_view, name='guest_invite_thank_you'),
    path('event/<int:event_id>/tables/', views.TableListView.as_view(), name='table_list'),
    path('event/<int:event_id>/tables/new/', views.TableCreateView.as_view(), name='table_create'),
    path('table/<int:pk>/edit/', views.TableUpdateView.as_view(), name='table_edit'),  # pk = table's primary key
    path('table/<int:pk>/delete/', views.TableDeleteView.as_view(), name='table_delete'),  # pk = table's primary key
    path('event/new/', views.EventCreateView.as_view(), name='event_create'),
    path('event/preview/', views.event_preview_view, name='event_preview'),
    path('event/<int:pk>/edit/', views.EventUpdateView.as_view(), name='event_edit'),  # pk = event's primary key
    path('event/<int:pk>/delete/', views.EventDeleteView.as_view(), name='event_delete'),
    path('event/<int:event_id>/guests/', views.guest_list, name='guest_list'),
    path('guests/<int:guest_id>/update_attendance/', views.update_attendance_view, name='update_attendance'),
    path('guests/<int:guest_id>/mark_sent/', views.mark_invitation_sent_view, name='mark_invitation_sent'),
    path('event/<int:event_id>/guests/new/', views.GuestCreateView.as_view(), name='guest_create'),
    path('guest/<int:pk>/edit/', views.GuestUpdateView.as_view(), name='guest_edit'),
    path('guest/<int:pk>/delete/', views.GuestDeleteView.as_view(), name='guest_delete'),

    # path('events/<int:event_id>/assignments/', views.table_assignment_ui_view, name='table_assignment_ui'),
    # path('events/<int:event_id>/assignments/<int:assignment_id>/unassign/', views.unassign_guest_from_table_view, name='unassign_guest'),

    # --- URL for the Table Assignment UI (we'll create the view later) ---
    path('events/<int:event_id>/assignments/', views.table_assignment_ui_view, name='table_assignment_ui'),
    path('event/<int:event_id>/assign/', views.table_assignment_view, name='table_assignment'),
    path('events/<int:event_id>/assignments/<int:assignment_id>/unassign/', views.unassign_guest_from_table_view,
         name='unassign_guest'),
    path('event/<int:event_id>/assignments/export/', views.export_assignments_csv, name='export_assignments_csv'),

    # === NEW: URLS FOR STRIPE PAYMENT FLOW        ===
    # ==============================================
    path('create-checkout-session/<int:plan_id>/', views.create_checkout_session_view, name='create_checkout_session'),
    path('payment/success/', views.payment_success_view, name='payment_success'),
    path('payment/cancel/', views.payment_cancel_view, name='payment_cancel'),

    # CRITICAL: Webhook URL required for stripe_webhook in views.py
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),

    # ==============================================
    # === NEW: URLS FOR GUEST IMPORT/EXPORT        ===
    # ==============================================
    path('event/<int:event_id>/guests/download-template/', views.download_guest_template_view,
         name='download_guest_template'),
    path('event/<int:event_id>/guests/import/', views.guest_import_view, name='guest_import'),

]