from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialAccount
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.contrib.auth.models import User
from django.db.models import Count, Q
from .models import (
    UserProfile, Event, Guest, RSVP, Table, TableAssignment, 
    CardDesign, Plan, FAQ, AboutSection, FutureFeature, Testimonial, Voucher,
    MarketingCampaign
)
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
import pandas as pd
import urllib.parse
import json
import csv
import base64
import sys
import stripe
from datetime import datetime, timedelta, time
from types import SimpleNamespace
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from .forms import (
    GuestForm, EventForm, GuestContactForm, AssignGuestForm,
    RSVPForm, TableForm, CustomUserCreationForm, TableAssignmentForm,
    GuestCreateForm, GodparentFormSet, ScheduleItemFormSet, ReviewForm, GalleryImageFormSet
)


@csrf_exempt
@xframe_options_exempt
def event_preview(request):
    """
    Preview logic with Debugging for Cloudinary URL issues.
    """
    if request.method == 'POST':
        try:
            # 1. Extract Data
            if request.content_type == 'application/json':
                try:
                    data = json.loads(request.body)
                except json.JSONDecodeError:
                    return HttpResponse("Invalid JSON", status=400)
            else:
                data = request.POST.dict()

            print(f"DEBUG: Preview Data Received. Keys: {list(data.keys())}")

            # 2. Build Mock Event
            event_data = {}
            for key, value in data.items():
                if value == "":
                    event_data[key] = None
                else:
                    event_data[key] = value

            # --- 2.1 Process Dates/Times ---
            if 'event_date' in event_data and event_data['event_date']:
                try:
                    event_data['event_date'] = datetime.strptime(event_data['event_date'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            if 'party_time' in event_data and event_data['party_time']:
                try:
                    event_data['party_time'] = datetime.strptime(event_data['party_time'], '%H:%M').time()
                except ValueError:
                    pass

            if 'ceremony_time' in event_data and event_data['ceremony_time']:
                try:
                    event_data['ceremony_time'] = datetime.strptime(event_data['ceremony_time'], '%H:%M').time()
                except ValueError:
                    pass

            # 3. FIX IMAGES (Cloudinary & Base64)
            image_fields = ['couple_photo', 'landscape_photo', 'main_invitation_image']

            for field_name in image_fields:
                raw_val = data.get(field_name)

                if raw_val and isinstance(raw_val, str):
                    # CRITICAL: Clean whitespace
                    raw_val = raw_val.strip()

                    print(f"DEBUG: Processing {field_name}. Value starts with: '{raw_val[:10]}...'")

                    # CASE 1: Absolute URL (Cloudinary/S3)
                    if 'http://' in raw_val or 'https://' in raw_val:
                        if not raw_val.startswith('http'):
                            start = raw_val.find('http')
                            if start != -1:
                                raw_val = raw_val[start:]

                        event_data[field_name] = SimpleNamespace(url=raw_val)
                        print(f"DEBUG: {field_name} treated as Absolute URL: {raw_val}")

                    # CASE 2: Base64 (New Upload)
                    elif raw_val.startswith('data:image'):
                        event_data[field_name] = SimpleNamespace(url=raw_val)
                        print(f"DEBUG: {field_name} treated as Base64")

                    # CASE 3: Relative Path (Local Dev or partial path)
                    elif raw_val:
                        clean_val = raw_val.replace('/media/', '')
                        media_url = settings.MEDIA_URL.rstrip('/')
                        final_url = f"{media_url}/{clean_val.lstrip('/')}"

                        event_data[field_name] = SimpleNamespace(url=final_url)
                        print(f"DEBUG: {field_name} treated as Local URL: {final_url}")
                else:
                    event_data[field_name] = None

            # Convert dict to object
            event_instance = SimpleNamespace(**event_data)

            # 4. Design & Template
            design_id = data.get('selected_design')
            template_name = 'invapp/invites/default_invite.html'

            if design_id:
                try:
                    design = CardDesign.objects.get(pk=design_id)
                    template_name = design.template_name
                    event_instance.selected_design = design
                except (CardDesign.DoesNotExist, ValueError):
                    pass

            print(f"DEBUG: Rendering template {template_name}")

            # 5. Context
            context = {
                'event': event_instance,
                'guest': None,
                'is_preview': True,
                'godparents': [],
                'schedule_items': [],
                'gallery_images': []
            }

            return render(request, template_name, context)

        except Exception as e:
            print(f"ERROR in Preview: {e}")
            return HttpResponse(f"Error generating preview: {str(e)}", status=500)

    return HttpResponse("Method not allowed", status=405)


# --- CSV Export View ---
@login_required
def export_assignments_csv(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if event.owner != request.user:
        return HttpResponseForbidden(_("You do not have permission to export data for this event."))

    response = HttpResponse(content_type='text/csv')
    response[
        'Content-Disposition'] = f'attachment; filename="event_{event.title.replace(" ", "_")}_table_assignments.csv"'

    # Add BOM (Byte Order Mark) for Excel to recognize UTF-8 (Special characters like ă, î, ș, ț)
    response.write(u'\ufeff'.encode('utf8'))

    writer = csv.writer(response)

    # TRANSLATED HEADERS
    writer.writerow([
        str(_('Type')),
        str(_('Guest Name')),
        str(_('Phone Number')),
        str(_('Email')),
        str(_('Assigned Table')),
        str(_('Number Attending')),
        str(_('Invitation Method')),
        str(_('Meal Preferences'))
    ])

    assignments = TableAssignment.objects.filter(table__event=event) \
        .select_related('guest', 'table', 'guest__rsvp_details') \
        .order_by('table__name', 'guest__name')

    for assignment in assignments:
        guest = assignment.guest
        writer.writerow([
            guest.get_honorific_display(),
            guest.name,
            guest.phone_number if guest.phone_number else '',
            guest.email if guest.email else '',
            assignment.table.name,
            guest.attending_count,
            guest.get_invitation_method_display(),
            guest.rsvp_details.meal_preference if hasattr(guest, 'rsvp_details') else '',
        ])
    return response


# --- Invitation & RSVP View ---
@xframe_options_exempt
def invitation_rsvp_combined_view(request, guest_uuid):
    """
    Handles displaying the invitation and the RSVP form for a specific guest.
    """
    guest = get_object_or_404(Guest.objects.select_related('event__selected_design'), unique_id=guest_uuid)
    event = guest.event

    # --- SMART LANGUAGE REDIRECT ---
    from django.utils import translation
    current_lang = translation.get_language()
    
    # Use a session key unique to this guest to allow manual overrides later
    session_key = f'lang_forced_{guest_uuid}'
    
    if current_lang != guest.preferred_language and not request.session.get(session_key):
        # 1. Mark that we've performed the auto-redirect
        request.session[session_key] = True
        # 2. Set the language in the session (standard Django way)
        request.session['_language'] = guest.preferred_language
        # 3. Actually activate it for the current thread
        translation.activate(guest.preferred_language)
        # 4. Redirect to the URL with the correct prefix
        return redirect(reverse('invapp:guest_invite', kwargs={'guest_uuid': guest_uuid}))

    # Extra safety: Ensure the current thread matches the URL prefix (already handled by LocaleMiddleware)
    # but we can force it just in case if session didn't stick
    if current_lang != translation.get_language():
        translation.activate(current_lang)

    try:
        existing_rsvp = guest.rsvp_details
    except (RSVP.DoesNotExist, AttributeError):
        existing_rsvp = None

    if request.method == 'POST':
        form = RSVPForm(request.POST, instance=existing_rsvp, guest=guest)
        if form.is_valid():
            rsvp = form.save(commit=False)
            rsvp.guest = guest
            rsvp.save()

            # Mark source as automatic and clear manual overrides
            guest.rsvp_source = Guest.RSVPSourceChoices.AUTOMATIC
            if guest.manual_is_attending is not None:
                guest.manual_is_attending = None
                guest.manual_attending_count = None
            guest.save()

            messages.success(request, _("Confirmation details are updated. Thank you!") if existing_rsvp else _(
                'Thank you for confirmation!'))
            return redirect('invapp:guest_invite_thank_you', guest_uuid=guest.unique_id)
    else:
        form = RSVPForm(instance=existing_rsvp, guest=guest)

    # --- UPDATED: Calendar Link Generation ---
    google_calendar_link = None
    if event.event_date:
        # 1. Determine Time: Party Time -> Ceremony Time -> Midnight
        event_time = event.party_time or event.ceremony_time or datetime.min.time()

        # 2. Combine Date and Time
        start_time = datetime.combine(event.event_date, event_time)
        end_time = start_time + timedelta(hours=5)

        # 3. Format for Google (UTC format essentially)
        fmt = "%Y%m%dT%H%M%SZ"
        utc_start = start_time.strftime(fmt)
        utc_end = end_time.strftime(fmt)

        params = {
            'action': 'TEMPLATE',
            'text': event.title,
            'dates': f"{utc_start}/{utc_end}",
            'details': event.calendar_description or _("Join us for %(title)s!") % {'title': event.title},
            'location': f"{event.venue_name}, {event.venue_address}",
            'trp': 'false'
        }
        google_calendar_link = f"https://www.google.com/calendar/render?{urllib.parse.urlencode(params)}"

    template_to_render = event.selected_design.template_name if event.selected_design and event.selected_design.template_name else 'invapp/invites/default_invite.html'

    context = {
        'event': event,
        'guest': guest,
        'form': form,
        'google_calendar_link': google_calendar_link,
        'is_preview': False,
    }
    return render(request, template_to_render, context)


# --- Thank You View ---
def guest_invite_thank_you_view(request, guest_uuid):
    guest = get_object_or_404(Guest, unique_id=guest_uuid)
    event = guest.event
    google_calendar_link = None

    # --- UPDATED: Calendar Link Generation ---
    if event.event_date:
        event_time = event.party_time or event.ceremony_time or datetime.min.time()
        start_time = datetime.combine(event.event_date, event_time)
        end_time = start_time + timedelta(hours=5)

        fmt = "%Y%m%dT%H%M%SZ"
        utc_start = start_time.strftime(fmt)
        utc_end = end_time.strftime(fmt)

        params = {
            'action': 'TEMPLATE',
            'text': event.title,
            'dates': f"{utc_start}/{utc_end}",
            'details': event.calendar_description or _("Join us for %(title)s!") % {'title': event.title},
            'location': f"{event.venue_name}, {event.venue_address}",
        }
        google_calendar_link = f"https://www.google.com/calendar/render?{urllib.parse.urlencode(params)}"

    if request.method == 'POST':
        form = GuestContactForm(request.POST, instance=guest)
        if form.is_valid():
            form.save()
            messages.success(request, _("Thank you! Your contact information has been updated."))
            return redirect('invapp:guest_invite_thank_you', guest_uuid=guest.unique_id)
    else:
        form = GuestContactForm(instance=guest)

    context = {
        'guest': guest,
        'event': event,
        'form': form,
        'google_calendar_link': google_calendar_link,
    }
    return render(request, 'invapp/rsvp_thank_you.html', context)


# --- Generic Landing/Invitation ---
def invitation_view(request):
    event = Event.objects.first()
    if event:
        return render(request, 'invapp/invitation_detail_generic.html', {'event': event})
    else:
        return render(request, 'invapp/no_event.html')


# --- Landing Page ---
def landing_page_view(request):
    # Capture Voucher from URL (?v=CODE)
    voucher_code = request.GET.get('v')
    if voucher_code:
        try:
            voucher = Voucher.objects.get(code__iexact=voucher_code, active=True, is_used=False)
            # Check activation and expiration
            is_active = not (voucher.valid_from and voucher.valid_from > timezone.now())
            is_not_expired = not (voucher.valid_until and voucher.valid_until < timezone.now())
            
            if is_active and is_not_expired:
                request.session['active_voucher'] = voucher.code
                print(f"DEBUG: Voucher {voucher.code} captured in session.")
        except Voucher.DoesNotExist:
            pass

    plans = Plan.objects.filter(is_public=True).prefetch_related('card_designs').order_by('price')

    # UPDATED: Order by priority (descending), then by name
    designs = CardDesign.objects.filter(
        is_public=True
    ).distinct().order_by('-priority', 'name')

    recent_reviews = Testimonial.objects.filter(is_active=True).order_by('-created_at')[:10]

    # === NEW DATA FETCHING ===
    # 1. About Section (Take first active)
    about_section = AboutSection.objects.filter(is_active=True).first()

    # 2. Future Features (Only public ones)
    future_features = FutureFeature.objects.filter(is_public=True).order_by('-priority', 'target_date')

    # 3. Marketing Campaign
    active_campaign = MarketingCampaign.objects.filter(is_active=True).select_related('partner').first()

    context = {
        'reviews': recent_reviews,
        'designs': designs,
        'plans': plans,
        'about_section': about_section,
        'future_features': future_features,
        'active_campaign': active_campaign,
    }
    return render(request, 'invapp/landing_page_tailwind.html', context)

# --- Signup ---
def signup_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Email logic
            subject = _('Welcome to InvApp!')
            message = _(
                'Hello %(username)s,\n\nThank you for creating an account on our platform. You can now login to create invitations.\n\nRespectfully,\nInvApp Team') % {'username': user.username}
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            try:
                send_mail(subject, message, from_email, recipient_list)
                messages.success(request, _("Registration successful! A confirmation email has been sent."))
            except Exception:
                messages.warning(request, _("Registration successful, but we could not send a confirmation email."))

            login(request, user)
            
            # --- Apply Voucher from Session if any ---
            voucher_code = request.session.get('active_voucher')
            if voucher_code:
                try:
                    voucher = Voucher.objects.get(code__iexact=voucher_code, active=True, is_used=False)
                    # Expiration & Activation checks
                    is_expired = voucher.valid_until and voucher.valid_until < timezone.now()
                    is_not_active_yet = voucher.valid_from and voucher.valid_from > timezone.now()
                    
                    if not is_expired and not is_not_active_yet:
                        # 1. Update Profile Plan
                        profile, created = UserProfile.objects.get_or_create(user=user)
                        
                        # Find the first paid plan (or Premium if we want to be specific)
                        premium_plan = Plan.objects.filter(price__gt=0).order_by('-price').first()
                        if premium_plan:
                            profile.plan = premium_plan
                            profile.save()
                            
                            # 2. Mark Voucher as Used
                            voucher.is_used = True
                            voucher.used_by = user.email
                            voucher.used_at = timezone.now()
                            voucher.current_uses += 1
                            voucher.save()
                            
                            messages.success(request, _("Welcome! Your account has been upgraded to %(plan)s for free thanks to your voucher.") % {'plan': premium_plan.name})
                            
                            # 3. Clear session
                            del request.session['active_voucher']
                except Voucher.DoesNotExist:
                    pass

            return redirect('invapp:dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup_tailwind.html', {'form': form})


# --- Dashboard ---
@login_required
def dashboard_view(request):
    # Fetch events with annotations to avoid N+1 query
    events = Event.objects.filter(owner=request.user).select_related('selected_design').annotate(
        confirmed_count=Count('guests', filter=Q(guests__rsvp_details__attending=True)),
        total_guests_count=Count('guests')
    ).order_by('-event_date')

    user_guests = Guest.objects.filter(event__owner=request.user)
    guest_count = user_guests.count()

    active_plan = request.user.userprofile.plan if hasattr(request.user, 'userprofile') else None

    context = {
        'events': events,
        'guests': user_guests,
        'guest_count': guest_count,
        'active_plan': active_plan,
    }
    return render(request, 'invapp/dashboard.html', context)


# --- Mixins ---
class EventOwnerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        if hasattr(self, 'get_event'):
            event = self.get_event()
            return event.owner == self.request.user
        elif hasattr(self, 'get_object'):
            obj = self.get_object()
            if hasattr(obj, 'event') and hasattr(obj.event, 'owner'):
                return obj.event.owner == self.request.user
            elif hasattr(obj, 'owner'):
                return obj.owner == self.request.user
        return False


# --- Table Views ---
class TableListView(EventOwnerRequiredMixin, ListView):
    model = Table
    template_name = 'invapp/table_list_tailwind.html'
    context_object_name = 'tables'

    def get_event(self):
        return get_object_or_404(Event, pk=self.kwargs.get('event_id'))

    def get_queryset(self):
        return Table.objects.filter(event=self.get_event()).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event'] = self.get_event()
        return context


class TableCreateView(LoginRequiredMixin, CreateView):
    model = Table
    form_class = TableForm
    template_name = 'invapp/table_form_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event'] = get_object_or_404(Event, id=self.kwargs['event_id'])
        return context

    def form_valid(self, form):
        event = get_object_or_404(Event, id=self.kwargs['event_id'])
        form.instance.event = event
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('invapp:table_list', kwargs={'event_id': self.kwargs['event_id']})


class TableUpdateView(LoginRequiredMixin, UpdateView):
    model = Table
    form_class = TableForm
    template_name = 'invapp/table_form_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event'] = self.object.event
        return context

    def get_success_url(self):
        return reverse_lazy('invapp:table_list', kwargs={'event_id': self.object.event.id})


class TableDeleteView(EventOwnerRequiredMixin, DeleteView):
    model = Table
    template_name = 'invapp/table_confirm_delete.html'
    context_object_name = 'table'

    def get_success_url(self):
        return reverse_lazy('invapp:table_list', kwargs={'event_id': self.object.event.id})

    def form_valid(self, form):
        table_name = self.object.name
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, _("Table '%(name)s' deleted successfully.") % {'name': table_name})
        return redirect(success_url)


# --- Table Assignment Views ---
@login_required
def table_assignment_view(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if event.owner != request.user:
        return HttpResponseForbidden(_("You do not have permission to manage assignments."))

    if request.method == 'POST':
        if request.POST.get('action') == 'unassign':
            assignment_id = request.POST.get('assignment_id')
            try:
                assignment = get_object_or_404(TableAssignment, pk=assignment_id)
                if assignment.table.event == event:
                    assignment.delete()
                    messages.success(request, _("Guest unassigned successfully."))
            except Exception as e:
                messages.error(request, _("Error: %(error)s") % {'error': e})
            return redirect('invapp:table_assignment', event_id=event.id)
        else:
            form = AssignGuestForm(request.POST, event=event)
            if form.is_valid():
                guest = form.cleaned_data['guest']
                table = form.cleaned_data['table']
                if TableAssignment.objects.filter(guest=guest).exists():
                    messages.error(request, _("%(name)s is already assigned.") % {'name': guest.name})
                else:
                    TableAssignment.objects.create(guest=guest, table=table)
                    messages.success(request, _("Assigned %(guest)s to %(table)s.") % {'guest': guest.name, 'table': table.name})
                return redirect('invapp:table_assignment', event_id=event.id)
            else:
                assignment_form = form
                messages.error(request, _("Invalid selection."))

    tables = Table.objects.filter(event=event).prefetch_related('assigned_guests__guest')
    assigned_ids = TableAssignment.objects.filter(table__event=event).values_list('guest_id', flat=True)
    unassigned_guests = Guest.objects.filter(event=event, rsvp_details__attending=True).exclude(id__in=assigned_ids)

    if 'assignment_form' not in locals():
        assignment_form = AssignGuestForm(event=event)

    context = {
        'event': event,
        'tables': tables,
        'unassigned_guests': unassigned_guests,
        'assignment_form': assignment_form,
    }
    return render(request, 'invapp/table_assignment.html', context)


@login_required
def table_assignment_ui_view(request, event_id):
    if not request.user.userprofile.plan.has_table_assignment:
        messages.error(request, _("Table assignment is not included in your plan."))
        return redirect(reverse('invapp:landing_page') + '#pricing')

    event = get_object_or_404(Event, id=event_id, owner=request.user)

    if request.method == 'POST':
        form = TableAssignmentForm(request.POST, event=event)
        if form.is_valid():
            selected_guests = form.cleaned_data['guests']
            target_table = form.cleaned_data['table']
            for guest in selected_guests:
                TableAssignment.objects.create(guest=guest, table=target_table)
            messages.success(request, _("%(count)d guest(s) assigned to %(table)s.") % {'count': len(selected_guests), 'table': target_table.name})
            return redirect('invapp:table_assignment_ui', event_id=event.id)
    else:
        form = TableAssignmentForm(event=event)

    tables = Table.objects.filter(event=event).prefetch_related('assigned_guests__guest__rsvp_details').order_by('name')
    context = {'event': event, 'tables': tables, 'assignment_form': form}
    return render(request, 'invapp/table_assignment_ui.html', context)


@login_required
def unassign_guest_from_table_view(request, event_id, assignment_id):
    assignment = get_object_or_404(TableAssignment, id=assignment_id, table__event__owner=request.user,
                                   table__event_id=event_id)
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, _("Guest unassigned."))
    return redirect('invapp:table_assignment_ui', event_id=event_id)


# --- Event CRUD Views ---
class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'invapp/event_form_tailwind.html'

    def dispatch(self, request, *args, **kwargs):
        user = self.request.user
        try:
            if hasattr(user, 'userprofile') and user.userprofile.plan:
                current_count = Event.objects.filter(owner=user).count()
                limit = user.userprofile.plan.max_events
                if current_count >= limit:
                    messages.warning(self.request, _("Event limit reached. Upgrade to create more."))
                    return redirect(reverse('invapp:landing_page') + '#pricing')
        except ObjectDoesNotExist:
            return redirect('invapp:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 1. Design Logic
        available_designs = CardDesign.objects.none()
        if hasattr(user, 'userprofile') and user.userprofile.plan:
            available_designs = user.userprofile.plan.card_designs.all()
        else:
            try:
                free_plan = Plan.objects.get(price=0)
                available_designs = free_plan.card_designs.all()
            except Plan.DoesNotExist:
                pass

        # 2. Special Fields Logic
        design_fields = {}
        for design in available_designs.prefetch_related('special_fields'):
            names = [f.name for f in design.special_fields.all()]
            if names:
                design_fields[slugify(design.name)] = names

        context['design_specific_fields_json'] = json.dumps(design_fields)
        context['available_designs'] = available_designs

        # 3. Formsets (Include Gallery)
        if self.request.POST:
            context['godparent_formset'] = GodparentFormSet(self.request.POST, self.request.FILES)
            context['schedule_item_formset'] = ScheduleItemFormSet(self.request.POST, self.request.FILES)
            context['gallery_image_formset'] = GalleryImageFormSet(self.request.POST, self.request.FILES)
        else:
            context['godparent_formset'] = GodparentFormSet()
            context['schedule_item_formset'] = ScheduleItemFormSet()
            context['gallery_image_formset'] = GalleryImageFormSet()

        return context

    def form_valid(self, form):
        # --- DEBUGGING START ---
        print(f"DEBUG UPLOAD: User {self.request.user} attempting to save an event.", file=sys.stderr)
        if self.request.FILES:
            print(f"DEBUG UPLOAD: Files received! List: {self.request.FILES.keys()}", file=sys.stderr)
        else:
            print("DEBUG UPLOAD: ATTENTION! No files received.", file=sys.stderr)
        # --- DEBUGGING END ---

        context = self.get_context_data()
        godparent_formset = context['godparent_formset']
        schedule_item_formset = context['schedule_item_formset']
        gallery_image_formset = context['gallery_image_formset']

        # Complete validation (including gallery)
        if form.is_valid():
            self.object = form.save(commit=False)
            self.object.owner = self.request.user
            self.object.save()

            if godparent_formset.is_valid():
                godparent_formset.instance = self.object
                godparent_formset.save()

            if schedule_item_formset.is_valid():
                schedule_item_formset.instance = self.object
                schedule_item_formset.save()

            if gallery_image_formset.is_valid():
                gallery_image_formset.instance = self.object
                gallery_image_formset.save()

            # Check for missing relevant info (Attention Message)
            missing_info = []
            if not self.object.couple_photo: missing_info.append(_("Couple Photo"))
            if not self.object.ceremony_location or not self.object.ceremony_time: missing_info.append(_("Ceremony Logistics"))
            if not self.object.venue_name or not self.object.party_time: missing_info.append(_("Reception Logistics"))
            
            if missing_info:
                # Convert lazy objects to strings before joining to prevent TypeError
                fields_str = ", ".join([str(f) for f in missing_info])
                messages.warning(self.request, _("Event published, but some details are missing: %(fields)s. You can add them later.") % {'fields': fields_str})
            else:
                messages.success(self.request, _("Event '%(title)s' created!") % {'title': self.object.title})
            
            return redirect('invapp:dashboard')
        else:
            print("--- VALIDATION FAILED ---", file=sys.stderr)
            print(f"Form Errors: {form.errors}", file=sys.stderr)
            # We only show formset errors if they were actually interacted with
            return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse_lazy('invapp:dashboard')


class EventUpdateView(LoginRequiredMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'invapp/event_form_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Locked Plan Logic
        is_locked = False
        if hasattr(user, 'userprofile') and user.userprofile.plan and user.userprofile.plan.lock_event_on_creation:
            is_locked = True
            form = context.get('form')
            if form:
                for f in ['event_type', 'event_date', 'selected_design']:
                    if f in form.fields:
                        form.fields[f].disabled = True
        context['is_locked_plan'] = is_locked

        # Design Logic
        available_designs = CardDesign.objects.none()
        if hasattr(user, 'userprofile') and user.userprofile.plan:
            available_designs = user.userprofile.plan.card_designs.all()
        else:
            try:
                free_plan = Plan.objects.get(price=0)
                available_designs = free_plan.card_designs.all()
            except:
                pass

        design_fields = {}
        for design in available_designs.prefetch_related('special_fields'):
            names = [f.name for f in design.special_fields.all()]
            if names:
                design_fields[slugify(design.name)] = names

        current = self.object.selected_design
        if current:
            slug = slugify(current.name)
            if slug not in design_fields:
                names = [f.name for f in current.special_fields.all()]
                if names: design_fields[slug] = names

        context['design_specific_fields_json'] = json.dumps(design_fields)
        context['available_designs'] = available_designs

        # Formsets Update
        if self.request.POST:
            context['godparent_formset'] = GodparentFormSet(self.request.POST, self.request.FILES, instance=self.object)
            context['schedule_item_formset'] = ScheduleItemFormSet(self.request.POST, self.request.FILES,
                                                                   instance=self.object)
            context['gallery_image_formset'] = GalleryImageFormSet(self.request.POST, self.request.FILES,
                                                                   instance=self.object)
        else:
            context['godparent_formset'] = GodparentFormSet(instance=self.object)
            context['schedule_item_formset'] = ScheduleItemFormSet(instance=self.object)
            context['gallery_image_formset'] = GalleryImageFormSet(instance=self.object)

        return context

    def form_valid(self, form):
        print(f"DEBUG UPDATE: User {self.request.user} updating event {self.object.pk}.", file=sys.stderr)
        print(f"DEBUG FIELDS: Ceremony={form.cleaned_data.get('ceremony_location')}, Venue={form.cleaned_data.get('venue_name')}", file=sys.stderr)
        print(f"DEBUG MAPS: CeremonyMap={form.cleaned_data.get('ceremony_maps_url')}, PartyMap={form.cleaned_data.get('party_maps_url')}", file=sys.stderr)

        context = self.get_context_data()
        godparent_formset = context['godparent_formset']
        schedule_item_formset = context['schedule_item_formset']
        gallery_image_formset = context['gallery_image_formset']

        # Complete validation
        if form.is_valid():
            self.object = form.save()

            if godparent_formset.is_valid():
                godparent_formset.instance = self.object
                godparent_formset.save()

            if schedule_item_formset.is_valid():
                schedule_item_formset.instance = self.object
                schedule_item_formset.save()

            # Save gallery (add/delete)
            if gallery_image_formset.is_valid():
                gallery_image_formset.instance = self.object
                gallery_image_formset.save()

            # Check for missing relevant info (Attention Message)
            missing_info = []
            if not self.object.couple_photo: missing_info.append(_("Couple Photo"))
            if not self.object.ceremony_location or not self.object.ceremony_time: missing_info.append(_("Ceremony Logistics"))
            if not self.object.venue_name or not self.object.party_time: missing_info.append(_("Reception Logistics"))
            
            if missing_info:
                # Convert lazy objects to strings before joining to prevent TypeError
                fields_str = ", ".join([str(f) for f in missing_info])
                messages.warning(self.request, _("Event updated, but some details are missing: %(fields)s. You can add them later.") % {'fields': fields_str})
            else:
                messages.success(self.request, _("Event updated."))
            
            return redirect('invapp:dashboard')
        else:
            print("--- UPDATE VALIDATION FAILED ---", file=sys.stderr)
            print(f"Form Errors: {form.errors}", file=sys.stderr)
            return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse_lazy('invapp:dashboard')


class EventDeleteView(LoginRequiredMixin, DeleteView):
    model = Event
    success_url = reverse_lazy('invapp:dashboard')
    template_name = 'invapp/event_confirm_delete.html'

    def get_queryset(self):
        return Event.objects.filter(owner=self.request.user)

    def dispatch(self, request, *args, **kwargs):
        if request.user.userprofile.plan and request.user.userprofile.plan.lock_event_on_creation:
            messages.warning(request, _("Deleting events is locked on your plan."))
            return redirect('invapp:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Event deleted."))
        return super().delete(request, *args, **kwargs)


@login_required
@csrf_exempt
def event_autosave_view(request, pk):
    """
    Background save for event form data and related formsets.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    
    event = get_object_or_404(Event, pk=pk, owner=request.user)
    
    form = EventForm(request.POST, request.FILES, instance=event)
    godparent_formset = GodparentFormSet(request.POST, request.FILES, instance=event)
    schedule_item_formset = ScheduleItemFormSet(request.POST, request.FILES, instance=event)
    gallery_image_formset = GalleryImageFormSet(request.POST, request.FILES, instance=event)
    
    if form.is_valid():
        form.save()
        
        # Save related formsets if valid
        if godparent_formset.is_valid():
            godparent_formset.save()
        if schedule_item_formset.is_valid():
            schedule_item_formset.save()
        if gallery_image_formset.is_valid():
            gallery_image_formset.save()
            
        return JsonResponse({'status': 'success', 'last_saved': datetime.now().strftime('%H:%M:%S')})
    else:
        return JsonResponse({'status': 'invalid', 'errors': form.errors}, status=400)


# --- Preview View ---
@csrf_exempt
@xframe_options_exempt
def event_preview_view(request):
    if request.method != 'POST': return HttpResponse("Invalid", status=400)
    try:
        data = json.loads(request.body)

        # --- 1. Manage date and time ---
        date_str = data.get('event_date')
        if date_str:
            try:
                data['event_date'] = datetime.strptime(date_str, "%Y-%m-%d").date()
                data['date_time'] = data['event_date'] # Alias for older templates
            except:
                data['event_date'] = None
                data['date_time'] = None

        time_str = data.get('party_time')
        if time_str:
            try:
                data['party_time'] = datetime.strptime(time_str, "%H:%M").time()
            except:
                data['party_time'] = None

        ceremony_time_str = data.get('ceremony_time')
        if ceremony_time_str:
            try:
                data['ceremony_time'] = datetime.strptime(ceremony_time_str, "%H:%M").time()
            except:
                data['ceremony_time'] = None

        # --- 1.5. Manage Formsets (Godparents & Timeline) ---
        # Extract data from flat format (godparents-0-name) into structured lists
        godparents_list = []
        schedule_list = []
        
        for key, value in data.items():
            if key.startswith('godparents-') and key.endswith('-name') and value.strip():
                if not data.get(key.replace('-name', '-DELETE')) == 'on': # Skip deleted
                    godparents_list.append(SimpleNamespace(name=value))
            
            if key.startswith('schedule_items-') and key.endswith('-activity_type') and value.strip():
                if not data.get(key.replace('-activity_type', '-DELETE')) == 'on':
                    prefix = key.rsplit('-', 1)[0]
                    time_val = data.get(f"{prefix}-time")
                    try:
                        parsed_time = datetime.strptime(time_val, "%H:%M").time() if time_val else None
                    except:
                        parsed_time = None
                    schedule_list.append(SimpleNamespace(activity_type=value, time=parsed_time))

        mock_event = SimpleNamespace(**data)
        
        # Attach "Mock Managers" to support .exists() and .all() in templates
        mock_event.godparents = SimpleNamespace(
            exists=lambda: len(godparents_list) > 0,
            all=lambda: godparents_list
        )
        mock_event.schedule_items = SimpleNamespace(
            exists=lambda: len(schedule_list) > 0,
            all=lambda: sorted(schedule_list, key=lambda x: x.time if x.time else time.min)
        )

        # --- 2. Manage Images ---
        for field in ['couple_photo', 'landscape_photo', 'main_invitation_image', 'audio_greeting']:
            img = data.get(field)

            if not img:
                setattr(mock_event, field, None)
                continue

            img = img.strip()

            # Case A: New Upload (Base64) or Absolute URL (Cloudinary/HTTPS)
            if img.startswith('data:') or img.startswith('http://') or img.startswith('https://'):
                setattr(mock_event, field, SimpleNamespace(url=img))

            # Case B: Local URL (Development)
            else:
                clean_path = img.lstrip('/')
                if clean_path.startswith('media/'):
                    final_url = f"/{clean_path}"
                else:
                    final_url = f"{settings.MEDIA_URL}{clean_path}"

                setattr(mock_event, field, SimpleNamespace(url=final_url))

        # --- 3. Manage Design ---
        design_id = data.get('selected_design')
        if not design_id: return HttpResponse("No design", status=400)
        design = CardDesign.objects.get(id=design_id)

        # --- 4. Mock Guest (Using unique_id) ---
        mock_guest = SimpleNamespace(
            unique_id='00000000-0000-0000-0000-000000000000',
            name=_('Guest Name'),
            honorific='family',
            max_attendees=5,
            manual_is_attending=None,
            rsvp_details=SimpleNamespace(attending=None)
        )

        # --- 5. Mock Form (Critical for RSVP display) ---
        from .forms import RSVPForm
        mock_form = RSVPForm(guest=mock_guest)

        context = {
            'event': mock_event,
            'guest': mock_guest,
            'form': mock_form,
            'is_preview': True
        }

        # --- 6. Render with Request (Critical for CSRF Token) ---
        html = render_to_string(design.template_name, context, request=request)
        return HttpResponse(html)

    except Exception as e:
        print(f"Preview Error: {e}")
        return HttpResponse(f"Error: {e}", status=500)


# --- Guest Management Views ---
@login_required
def guest_list(request, event_id):
    event = get_object_or_404(Event, pk=event_id, owner=request.user)

    # 1. Fetch data
    guests_queryset = Guest.objects.filter(event=event).select_related('rsvp_details')
    guests_list = list(guests_queryset)

    # 2. Sort by URL parameter
    sort_param = request.GET.get('sort', 'name')

    def status_priority(guest):
        if guest.is_attending is True: return 0
        if guest.is_attending is None: return 1
        return 2

    if sort_param == 'name':
        guests_list.sort(key=lambda g: g.name.lower())
    elif sort_param == '-name':
        guests_list.sort(key=lambda g: g.name.lower(), reverse=True)
    elif sort_param == 'status':
        guests_list.sort(key=lambda g: (status_priority(g), g.name.lower()))
    elif sort_param == '-status':
        guests_list.sort(key=lambda g: (status_priority(g), g.name.lower()), reverse=True)

    total_attending = sum(g.attending_count for g in guests_list)

    context = {
        'event': event,
        'guests': guests_list,
        'total_attending': total_attending,
        'current_sort': sort_param,
    }
    return render(request, 'invapp/guest_list_tailwind.html', context)


class GuestCreateView(LoginRequiredMixin, CreateView):
    model = Guest
    form_class = GuestCreateForm
    template_name = 'invapp/guest_form_tailwind.html'

    def dispatch(self, request, *args, **kwargs):
        self.event = get_object_or_404(Event, pk=self.kwargs['event_id'])
        if self.event.owner != self.request.user:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Check guest limit
        limit = self.request.user.userprofile.plan.max_guests
        current = self.event.guests.count()
        if current >= limit:
            messages.error(self.request, _("Guest limit reached."))
            return redirect('invapp:guest_list', event_id=self.event.id)

        guest = form.save(commit=False)
        guest.owner = self.request.user
        guest.event = self.event
        guest.save()
        messages.success(self.request, _("Guest added."))
        return redirect('invapp:guest_list', event_id=self.event.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event'] = self.event
        context['form_title'] = _('Add New Guest')
        return context


class GuestUpdateView(LoginRequiredMixin, UpdateView):
    model = Guest
    form_class = GuestForm
    template_name = 'invapp/guest_form_tailwind.html'
    context_object_name = 'guest'

    def get_queryset(self):
        return super().get_queryset().filter(event__owner=self.request.user)

    def get_success_url(self):
        return reverse('invapp:guest_list', kwargs={'event_id': self.object.event.id})

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, _("Guest details updated."))
        return redirect('invapp:guest_list', event_id=self.object.event.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event'] = self.object.event
        context['form_title'] = _('Edit Guest: %(name)s') % {'name': self.object.name}
        return context


class GuestDeleteView(LoginRequiredMixin, DeleteView):
    model = Guest
    template_name = 'invapp/guest_confirm_delete.html'
    context_object_name = 'guest'

    def get_queryset(self):
        return super().get_queryset().filter(event__owner=self.request.user)

    def get_success_url(self):
        return reverse_lazy('invapp:guest_list', kwargs={'event_id': self.object.event.id})

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(self.request, _("Guest deleted."))
        return redirect(success_url)


@login_required
@csrf_exempt
def update_attendance_view(request, guest_id):
    if request.method != 'POST': return JsonResponse({'status': 'error'}, status=400)
    try:
        guest = get_object_or_404(Guest, id=guest_id, owner=request.user)
        data = json.loads(request.body)
        
        # 1. Handle attendance count update
        if 'number_attending' in data:
            new_count = int(data.get('number_attending', 0))
            guest.manual_attending_count = new_count
            guest.manual_is_attending = True if new_count > 0 else False
            guest.rsvp_source = Guest.RSVPSourceChoices.MANUAL
        
        # 2. Handle preferred language update
        if 'preferred_language' in data:
            guest.preferred_language = data.get('preferred_language')

        guest.save()

        total = sum(g.attending_count for g in Guest.objects.filter(event=guest.event))
        return JsonResponse({'status': 'success', 'new_total_attending': total})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@csrf_exempt
def mark_invitation_sent_view(request, guest_id):
    if request.method != 'POST': return JsonResponse({'status': 'error'}, status=400)
    try:
        guest = get_object_or_404(Guest, id=guest_id, owner=request.user)
        if guest.invitation_method != 'digital':
            guest.invitation_method = 'digital'
            guest.save()
        return JsonResponse({'status': 'success'})
    except:
        return JsonResponse({'status': 'error'}, status=500)


# --- Stripe Views ---
@login_required
def create_checkout_session_view(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    stripe.api_key = settings.STRIPE_SECRET_KEY

    if getattr(plan, 'is_recurring', False):
        checkout_mode = 'subscription'
    else:
        checkout_mode = 'payment'

    try:
        session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            metadata={
                'user_id': request.user.id,
                'plan_id': plan.id
            },
            success_url=request.build_absolute_uri(reverse('invapp:payment_success')),
            cancel_url=request.build_absolute_uri(reverse('invapp:payment_cancel')),
            mode=checkout_mode,
            line_items=[{
                'price': plan.stripe_price_id,
                'quantity': 1
            }]
        )
        return redirect(session.url, code=303)

    except Exception as e:
        messages.error(request, _("Stripe Error: %(error)s") % {'error': e})
        return redirect(reverse('invapp:landing_page') + '#pricing')


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    print("\n=== STRIPE WEBHOOK RECEIVED ===")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        print(f"❌ Error: Invalid payload")
        return HttpResponse(status=400)
    except stripe.SignatureVerificationError:
        print(f"❌ Error: Signature verification failed.")
        return HttpResponse(status=400)

    # --- 1. PAYMENT COMPLETED ---
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        print(f"💰 Payment Succeeded for Session ID: {session.get('id')}")

        user_id = session.get('metadata', {}).get('user_id')
        plan_id = session.get('metadata', {}).get('plan_id')
        subscription_id = session.get('subscription')

        print(f"👤 Metadata Found -> User ID: {user_id}, Plan ID: {plan_id}, Sub ID: {subscription_id}")

        if user_id and plan_id:
            try:
                user = User.objects.get(id=user_id)
                new_plan = Plan.objects.get(id=plan_id)

                if not hasattr(user, 'userprofile'):
                    UserProfile.objects.create(user=user)

                profile = user.userprofile
                profile.plan = new_plan
                profile.save()

                print(f"✅ SUCCESS: Upgraded {user.username} to plan '{new_plan.name}'")
            except Exception as e:
                print(f"❌ ERROR updating DB: {str(e)}")
                return HttpResponse(status=200)

    # --- 2. NEW SUBSCRIPTION CREATED ---
    elif event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        subscription_id = subscription.get('id')
        customer_id = subscription.get('customer')
        print(f"🆕 Subscription CREATED: {subscription_id} for Customer: {customer_id}")

    # --- 3. SUBSCRIPTION CANCELLED ---
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')

        print(f"⚠️ Subscription Cancelled for Customer ID: {customer_id}")

        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            customer = stripe.Customer.retrieve(customer_id)
            email = customer.get('email')

            if email:
                try:
                    user = User.objects.get(email=email)
                    user.userprofile.plan = None
                    user.userprofile.save()
                    print(f"✅ SUCCESS: Downgraded user {email} (Subscription Ended)")
                except User.DoesNotExist:
                    print(f"❌ User with email {email} not found.")
            else:
                print("❌ Could not find email in Stripe Customer object.")

        except Exception as e:
            print(f"❌ Error handling cancellation: {e}")
            return HttpResponse(status=200)

    return HttpResponse(status=200)


@login_required
def payment_success_view(request):
    messages.success(request, _("Payment successful! Your plan has been upgraded."))
    return redirect('invapp:dashboard')


@login_required
def payment_cancel_view(request):
    messages.warning(request, _("Payment cancelled."))
    return redirect(reverse('invapp:landing_page') + '#pricing')


@csrf_exempt
def api_verify_voucher(request):
    """
    JSON endpoint to verify if a voucher is valid.
    """
    code = request.GET.get('code') or request.POST.get('code')
    requested_plan_id = request.GET.get('plan_id') or request.POST.get('plan_id')
    
    print(f"DEBUG VOUCHER: Verifying code='{code}' for plan_id='{requested_plan_id}'")

    if not code:
        return JsonResponse({'valid': False, 'message': _('Please enter a voucher code.')})

    try:
        voucher = Voucher.objects.prefetch_related('applicable_plans').get(code__iexact=code)
    except Voucher.DoesNotExist:
        return JsonResponse({'valid': False, 'message': _('Invalid voucher code.')})

    if not voucher.active:
        return JsonResponse({'valid': False, 'message': _('This voucher is no longer active.')})

    if voucher.is_used:
        return JsonResponse({'valid': False, 'message': _('This voucher has already been used.')})

    if voucher.valid_until and voucher.valid_until < timezone.now():
        return JsonResponse({'valid': False, 'message': _('This voucher has expired.')})

    if voucher.valid_from and voucher.valid_from > timezone.now():
        return JsonResponse({'valid': False, 'message': _('This voucher is not yet active.')})

    if voucher.current_uses >= voucher.max_uses:
        return JsonResponse({'valid': False, 'message': _('This voucher has reached its maximum uses.')})

    # Plan Restriction Check
    if requested_plan_id and voucher.applicable_plans.exists():
        try:
            plan_id_int = int(requested_plan_id)
            if not voucher.applicable_plans.filter(id=plan_id_int).exists():
                print(f"DEBUG VOUCHER: Plan {plan_id_int} not in {list(voucher.applicable_plans.values_list('id', flat=True))}")
                return JsonResponse({'valid': False, 'message': _('This voucher is not valid for the selected plan.')})
        except ValueError:
            pass

    print(f"DEBUG VOUCHER: SUCCESS for code='{code}'")
    return JsonResponse({
        'valid': True,
        'discount_percentage': voucher.discount_percentage,
        'message': _('Voucher applied successfully!')
    })


@login_required
def api_apply_free_voucher(request):
    """
    Special endpoint for 100% discount vouchers to upgrade users instantly.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        code = data.get('code')
        plan_id = data.get('plan_id')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    if not code or not plan_id:
        return JsonResponse({'status': 'error', 'message': 'Missing code or plan_id'}, status=400)

    plan = get_object_or_404(Plan, id=plan_id)

    try:
        voucher = Voucher.objects.get(code__iexact=code, active=True)
    except Voucher.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': _('Invalid voucher.')}, status=400)

    if voucher.is_used:
        return JsonResponse({'status': 'error', 'message': _('Voucher already used.')}, status=400)

    if voucher.valid_until and voucher.valid_until < timezone.now():
        return JsonResponse({'status': 'error', 'message': _('Voucher expired.')}, status=400)

    if voucher.valid_from and voucher.valid_from > timezone.now():
        return JsonResponse({'status': 'error', 'message': _('Voucher not yet active.')}, status=400)

    if voucher.discount_percentage != 100:
        return JsonResponse({'status': 'error', 'message': _('This voucher is not for a free upgrade.')}, status=400)

    if voucher.current_uses >= voucher.max_uses:
        return JsonResponse({'status': 'error', 'message': _('Voucher reached usage limit.')}, status=400)

    # Plan Restriction Check
    if voucher.applicable_plans.exists():
        if not voucher.applicable_plans.filter(id=plan.id).exists():
            return JsonResponse({'status': 'error', 'message': _('This voucher is not valid for the selected plan.')}, status=400)

    # Perform Upgrade
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    profile.plan = plan
    profile.save()

    # Increment uses and mark as used
    voucher.current_uses += 1
    voucher.is_used = True
    voucher.used_by = request.user.email
    voucher.used_at = timezone.now()
    voucher.save()

    messages.success(request,
                     _("Congratulations! Your plan has been upgraded to %(plan)s for free!") % {'plan': plan.name})
    return JsonResponse({'status': 'success', 'redirect_url': reverse('invapp:dashboard')})


@login_required
def manual_upgrade_page_view(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    return render(request, 'invapp/upgrade_page.html', {'plan': plan})


# --- Guest Import/Export ---
@login_required
def download_guest_template_view(request, event_id):
    # Added Invitation Method to template
    df = pd.DataFrame(columns=[
        _('Honorific'), 
        _('Name'), 
        _('Email'), 
        _('Phone Number'), 
        _('Max Attendees'),
        _('Invitation Method') # digital or physical
    ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="guest_list_template.xlsx"'
    df.to_excel(response, index=False)
    return response


@login_required
def guest_import_view(request, event_id):
    event = get_object_or_404(Event, id=event_id, owner=request.user)
    if request.method == 'POST' and request.FILES.get('guest_file'):
        try:
            df = pd.read_excel(request.FILES['guest_file'])
            if 'Name' not in df.columns: raise ValueError(_("Missing 'Name' column"))

            current_count = event.guests.count()
            limit = request.user.userprofile.plan.max_guests
            to_add = df['Name'].dropna().count()

            if current_count + to_add > limit:
                messages.error(request, _("Import exceeds guest limit."))
                return redirect('invapp:guest_list', event_id=event.id)

            objs = []
            for _, row in df.iterrows():
                if pd.isna(row['Name']): continue
                
                # Logic for invitation method mapping
                raw_method = str(row.get('Invitation Method', '')).lower()
                method = 'physical'
                if 'digit' in raw_method:
                    method = 'digital'

                objs.append(Guest(
                    event=event, 
                    owner=request.user, 
                    name=str(row['Name']).strip(),
                    email=row.get('Email') if pd.notna(row.get('Email')) else None,
                    max_attendees=int(row.get('Max Attendees', 1)),
                    invitation_method=method,
                    preferred_language='ro' # Default to Romanian
                ))
            Guest.objects.bulk_create(objs)
            messages.success(request, _("Imported %(count)d guests.") % {'count': len(objs)})
        except Exception as e:
            messages.error(request, _("Import error: %(error)s") % {'error': str(e)})
    return redirect('invapp:guest_list', event_id=event.id)


class terms_of_service_view(TemplateView): template_name = "invapp/terms_and_conditions.html"


class privacy_policy_view(TemplateView): template_name = "invapp/privacy_policy.html"


# --- TEMPORARY FIX VIEW ---
def fix_site_domain(request):
    """
    Updates the Site object in the database to match the current hostname.
    """
    try:
        current_domain = request.get_host()
        site, created = Site.objects.get_or_create(id=1)
        old_domain = site.domain
        site.domain = current_domain
        site.name = "InvApp Romania"
        site.save()

        return HttpResponse(
            f"<h1>Success!</h1><p>Updated Site ID=1 from <strong>{old_domain}</strong> to <strong>{current_domain}</strong>.</p><p>You can now <a href='/'>Go Home</a> and Sign Up/Login.</p>")
    except Exception as e:
        return HttpResponse(f"Error updating site: {e}")


def faq_page(request):
    """
    Displays the FAQ page.
    """
    faqs = FAQ.objects.filter(is_visible=True).order_by('order')
    return render(request, 'invapp/faq.html', {'faqs': faqs})


@login_required
def submit_feedback(request):
    existing_review = Testimonial.objects.filter(user=request.user).first()
    social_avatar_url = None
    provider_name = 'email'

    try:
        social_accounts = SocialAccount.objects.filter(user=request.user)
        target_account = None

        if social_accounts.exists():
            for account in social_accounts:
                provider_str = str(account.provider).lower()
                if 'facebook' in provider_str or 'google' in provider_str:
                    target_account = account
                    break
                elif provider_str.isdigit() and len(provider_str) > 5:
                    target_account = account

            if not target_account:
                target_account = social_accounts.first()

        if target_account:
            raw_provider = str(target_account.provider).lower()
            uid = target_account.uid
            extra_data = target_account.extra_data or {}

            if 'google' in raw_provider:
                provider_name = 'google'
            elif 'facebook' in raw_provider or raw_provider.isdigit():
                provider_name = 'facebook'
            else:
                provider_name = 'email'

            try:
                social_avatar_url = target_account.get_avatar_url()
            except Exception:
                pass

            if not social_avatar_url and provider_name == 'google':
                social_avatar_url = extra_data.get('picture')

            if not social_avatar_url and provider_name == 'facebook':
                picture_data = extra_data.get('picture', {})
                if isinstance(picture_data, dict):
                    social_avatar_url = picture_data.get('data', {}).get('url')
                elif isinstance(picture_data, str):
                    social_avatar_url = picture_data

                if not social_avatar_url and uid:
                    social_avatar_url = f"https://graph.facebook.com/{uid}/picture?type=large"

            print(f"DEBUG FINAL: User={request.user}, SavedProvider={provider_name}, Avatar={social_avatar_url}",
                  file=sys.stderr)

    except Exception as e:
        print(f"DEBUG ERROR FEEDBACK: {e}", file=sys.stderr)
        pass

    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=existing_review)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user

            # Name
            full_name = request.user.get_full_name()
            if not full_name:
                full_name = request.user.username.split('@')[0]
            review.client_name = full_name

            # Avatar
            if social_avatar_url:
                review.avatar_url = social_avatar_url

            # Provider
            review.social_provider = provider_name

            review.save()
            messages.success(request, _("Thank you for your feedback!"))
            return redirect('invapp:dashboard')
    else:
        form = ReviewForm(instance=existing_review)

    return render(request, 'invapp/feedback_form.html', {
        'form': form,
        'social_avatar_url': social_avatar_url,
        'social_provider': provider_name
    })


@login_required
@xframe_options_exempt
def event_preview_demo(request, event_id):
    """
    Special dashboard view when no real guests exist.
    """
    event = get_object_or_404(Event, pk=event_id)

    if event.owner != request.user:
        return HttpResponseForbidden(_("You do not have permission to view this event."))

    if not event.selected_design:
        messages.warning(request, _("Select a design to see the preview."))
        return redirect('invapp:event_update', pk=event.id)

    # 1. Create a dummy guest (in-memory only)
    dummy_guest = SimpleNamespace(
        unique_id='00000000-0000-0000-0000-000000000000',
        name=_('Sample Guest Name'),
        honorific='family',
        max_attendees=2,
        manual_is_attending=None,
        rsvp_details=SimpleNamespace(attending=None),
        event=event
    )

    # 2. Create an empty form linked to dummy guest
    form = RSVPForm(guest=dummy_guest)

    # 3. Context
    context = {
        'event': event,
        'guest': dummy_guest,
        'form': form,
        'is_preview': True,
        'google_calendar_link': None
    }

    return render(request, event.selected_design.template_name, context)

def upgrade_plan(request):
    """Page where users can view plans and upgrade."""
    return render(request, 'invapp/upgrade_page.html')


class EventLivePreviewView(LoginRequiredMixin, View):
    """
    Renders a live preview using form data without touching the database.
    Bypasses model restrictions to allow real-time updates of unsaved relations.
    """

    def get(self, request, *args, **kwargs):
        return HttpResponse(_("Preview data expired. Please interact with the form to refresh."))

    def post(self, request, *args, **kwargs):
        # 1. Get Design (Required for rendering)
        design_id = request.POST.get('selected_design')
        design = None
        if design_id:
            try:
                design = CardDesign.objects.get(pk=design_id)
            except: pass
        
        if not design:
            return HttpResponse(_("Please select a template to see the preview."))

        # 2. Find existing event if any
        event_id = request.POST.get('event_id')
        existing_event = None
        if event_id:
            try:
                existing_event = Event.objects.get(pk=event_id, owner=request.user)
            except: pass

        # 3. Build a Mock Event object (SimpleNamespace)
        event_data = {}
        for key in request.POST:
            if not key.startswith('godparents-') and not key.startswith('schedule_items-'):
                event_data[key] = request.POST.get(key)

        # Parse critical fields for template filters
        if event_data.get('event_date'):
            try:
                event_data['event_date'] = datetime.strptime(event_data['event_date'], "%d/%m/%Y")
            except:
                try:
                    event_data['event_date'] = datetime.strptime(event_data['event_date'], "%Y-%m-%d")
                except:
                    event_data['event_date'] = None

        for time_field in ['party_time', 'ceremony_time']:
            if event_data.get(time_field):
                try:
                    event_data[time_field] = datetime.strptime(event_data[time_field], "%H:%M").time()
                except:
                    event_data[time_field] = None

        mock_event = SimpleNamespace(**event_data)
        mock_event.selected_design = design
        mock_event.owner = request.user

        # 4. Mock Related Managers for godparents/schedule
        class MockRelatedManager:
            def __init__(self, objects): self.objects = objects
            def all(self): return self.objects
            def count(self): return len(self.objects)
            def exists(self): return len(self.objects) > 0

        # Godparents
        godparents = []
        try:
            total_gp = int(request.POST.get('godparents-TOTAL_FORMS', 0))
            for i in range(total_gp):
                name = request.POST.get(f'godparents-{i}-name')
                delete = request.POST.get(f'godparents-{i}-DELETE') == 'on'
                if name and not delete:
                    godparents.append(SimpleNamespace(name=name))
        except: pass
        mock_event.godparents = MockRelatedManager(godparents)

        # Schedule
        schedule = []
        try:
            total_sch = int(request.POST.get('schedule_items-TOTAL_FORMS', 0))
            for i in range(total_sch):
                activity = request.POST.get(f'schedule_items-{i}-activity_type')
                time_val = request.POST.get(f'schedule_items-{i}-time')
                delete = request.POST.get(f'schedule_items-{i}-DELETE') == 'on'
                if activity and not delete:
                    try:
                        parsed_time = datetime.strptime(time_val, "%H:%M").time() if time_val else None
                    except: parsed_time = None
                    schedule.append(SimpleNamespace(activity_type=activity, time=parsed_time))
        except: pass
        mock_event.schedule_items = MockRelatedManager(schedule)

        # 5. Handle Photos (Live + Fallback)
        mock_event.preview_couple_photo_b64 = None
        if 'couple_photo' in request.FILES:
            f = request.FILES['couple_photo']
            try:
                img_data = base64.b64encode(f.read()).decode('utf-8')
                mock_event.preview_couple_photo_b64 = f"data:{f.content_type};base64,{img_data}"
            except: pass

        mock_event.preview_main_image_b64 = None
        if 'main_invitation_image' in request.FILES:
            f = request.FILES['main_invitation_image']
            try:
                img_data = base64.b64encode(f.read()).decode('utf-8')
                mock_event.preview_main_image_b64 = f"data:{f.content_type};base64,{img_data}"
            except: pass
        
        # Smart Helper Logic for mock (Template compatibility)
        if mock_event.preview_couple_photo_b64:
            mock_event.couple_photo = SimpleNamespace(url=mock_event.preview_couple_photo_b64)
            mock_event.get_couple_photo_url = mock_event.preview_couple_photo_b64
        elif existing_event and existing_event.couple_photo:
            mock_event.couple_photo = existing_event.couple_photo
            mock_event.get_couple_photo_url = existing_event.couple_photo.url
        else:
            mock_event.couple_photo = None
            mock_event.get_couple_photo_url = None

        if mock_event.preview_main_image_b64:
            mock_event.main_invitation_image = SimpleNamespace(url=mock_event.preview_main_image_b64)
        elif existing_event and existing_event.main_invitation_image:
            mock_event.main_invitation_image = existing_event.main_invitation_image
        else:
            mock_event.main_invitation_image = None

        # 6. DUMMY DATA (As in Dashboard Preview)
        # Prevents "NoneType" errors in templates that expect a guest/form
        dummy_guest = SimpleNamespace(
            unique_id='00000000-0000-0000-0000-000000000000',
            name=_('Sample Guest Name'),
            honorific='family',
            max_attendees=2,
            manual_is_attending=None,
            rsvp_details=SimpleNamespace(attending=None),
            event=mock_event
        )
        dummy_form = RSVPForm(guest=dummy_guest)

        context = {
            'event': mock_event,
            'guest': dummy_guest,
            'form': dummy_form,
            'is_preview': True,
            'google_calendar_link': None
        }

        try:
            return render(request, design.template_name, context)
        except Exception as e:
            return HttpResponse(f"Preview Error: {str(e)}")
