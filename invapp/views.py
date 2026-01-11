from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialAccount
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.contrib.auth.models import User
from .models import UserProfile, Event, Guest, RSVP, Table, TableAssignment, CardDesign, Plan, FAQ, AboutSection, FutureFeature
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
from datetime import datetime, timedelta
from types import SimpleNamespace
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from .models import Testimonial # Asigură-te că imporți modelul
from .forms import (
    GuestForm, EventForm, GuestContactForm, AssignGuestForm,
    RSVPForm, TableForm, CustomUserCreationForm, TableAssignmentForm,
    GuestCreateForm, GodparentFormSet, ScheduleItemFormSet, ReviewForm, GalleryImageFormSet
)


@csrf_exempt
@xframe_options_exempt
def event_preview(request):
    """
    Preview logic with Cloudinary Fix.
    """
    if request.method == 'POST':
        try:
            # 1. Extragere date
            if request.content_type == 'application/json':
                try:
                    data = json.loads(request.body)
                except json.JSONDecodeError:
                    return HttpResponse("Invalid JSON", status=400)
            else:
                data = request.POST.dict()

            # 2. Construire instanță Event
            event_instance = Event()

            # Populare câmpuri
            for field in Event._meta.fields:
                if field.name in data:
                    val = data[field.name]
                    if val == "": val = None
                    setattr(event_instance, field.name, val)

            # 3. FIX IMAGINI (Aici e rezolvarea pentru eroarea din loguri)
            image_fields = ['couple_photo', 'landscape_photo', 'main_invitation_image']

            for field_name in image_fields:
                raw_val = data.get(field_name)

                if raw_val and isinstance(raw_val, str):
                    # Dacă e URL Cloudinary (începe cu http), îl transformăm în obiect
                    if raw_val.startswith('http://') or raw_val.startswith('https://'):
                        mock_img = SimpleNamespace(url=raw_val)  # <--- ASTA REZOLVĂ EROAREA
                        setattr(event_instance, field_name, mock_img)

                    # Dacă e Base64 (upload nou)
                    elif raw_val.startswith('data:image'):
                        mock_img = SimpleNamespace(url=raw_val)
                        setattr(event_instance, field_name, mock_img)

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
            print(f"Preview Error: {e}")
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

            # Clear manual overrides if guest responds digitally
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
            'details': event.calendar_description or f"Join us for {event.title}!",
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
            'details': event.calendar_description or f"Join us for {event.title}!",
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
    plans = Plan.objects.filter(is_public=True).prefetch_related('card_designs').order_by('price')

    # UPDATED: Order by priority (descending), then by name
    designs = CardDesign.objects.filter(
        is_public=True
    ).distinct().order_by('-priority', 'name')

    recent_reviews = Testimonial.objects.filter(is_active=True).order_by('-created_at')[:10]

    # === NEW DATA FETCHING ===
    # 1. About Section (Luăm prima activă)
    about_section = AboutSection.objects.filter(is_active=True).first()

    # 2. Future Features (Doar cele publice)
    future_features = FutureFeature.objects.filter(is_public=True).order_by('-priority', 'target_date')

    context = {
        'reviews': recent_reviews,
        'designs': designs,
        'plans': plans,
        'about_section': about_section,  # Adăugat în context
        'future_features': future_features,  # Adăugat în context
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
                f'Hello {user.username},\n\nThank you for creating an account on our platform. You have the possibility to login to create invitations.\n\nWith respect,\nInvApp Team')
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            try:
                send_mail(subject, message, from_email, recipient_list)
                messages.success(request, _("Registration successful! A confirmation email has been sent."))
            except Exception as e:
                messages.warning(request, _("Registration successful, but we could not send a confirmation email."))

            login(request, user)
            return redirect('invapp:dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup_tailwind.html', {'form': form})


# --- Dashboard ---
@login_required
def dashboard_view(request):
    # Preluăm evenimentele
    events = Event.objects.filter(owner=request.user).select_related('selected_design').prefetch_related(
        'guests').order_by('-event_date')

    for event in events:
        # Folosim hasattr/attribut access pentru a evita query-uri extra în buclă dacă e posibil,
        # sau un simplu filter. Varianta sigură:
        event.confirmed_count = event.guests.filter(rsvp_details__attending=True).count()
        event.total_guests_count = event.guests.count()  # Optimizare pentru template

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
        messages.success(self.request, _(f"Table '{table_name}' deleted successfully."))
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
                messages.error(request, _(f"Error: {e}"))
            return redirect('invapp:table_assignment', event_id=event.id)
        else:
            form = AssignGuestForm(request.POST, event=event)
            if form.is_valid():
                guest = form.cleaned_data['guest']
                table = form.cleaned_data['table']
                if TableAssignment.objects.filter(guest=guest).exists():
                    messages.error(request, _(f"{guest.name} is already assigned."))
                else:
                    TableAssignment.objects.create(guest=guest, table=table)
                    messages.success(request, _(f"Assigned {guest.name} to {table.name}."))
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
            messages.success(request, _(f"{len(selected_guests)} guest(s) assigned to {target_table.name}."))
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

        # 1. Logică Design-uri
        available_designs = CardDesign.objects.none()
        if hasattr(user, 'userprofile') and user.userprofile.plan:
            available_designs = user.userprofile.plan.card_designs.all()
        else:
            try:
                free_plan = Plan.objects.get(price=0)
                available_designs = free_plan.card_designs.all()
            except Plan.DoesNotExist:
                pass

        # 2. Logică Câmpuri Speciale
        design_fields = {}
        for design in available_designs.prefetch_related('special_fields'):
            names = [f.name for f in design.special_fields.all()]
            if names:
                design_fields[slugify(design.name)] = names

        context['design_specific_fields_json'] = json.dumps(design_fields)
        context['available_designs'] = available_designs

        # 3. Formsets (Includem si Galeria)
        if self.request.POST:
            context['godparent_formset'] = GodparentFormSet(self.request.POST, self.request.FILES)
            context['schedule_item_formset'] = ScheduleItemFormSet(self.request.POST, self.request.FILES)
            # <--- LINIE NOUĂ: Instanțiem FormSet-ul Galeriei cu POST și FILES
            context['gallery_image_formset'] = GalleryImageFormSet(self.request.POST, self.request.FILES)
        else:
            context['godparent_formset'] = GodparentFormSet()
            context['schedule_item_formset'] = ScheduleItemFormSet()
            # <--- LINIE NOUĂ: FormSet gol pentru GET
            context['gallery_image_formset'] = GalleryImageFormSet()

        return context

    def form_valid(self, form):
        # --- DEBUGGING START ---
        print(f"DEBUG UPLOAD: Userul {self.request.user} incearca sa salveze un eveniment.", file=sys.stderr)
        if self.request.FILES:
            print(f"DEBUG UPLOAD: Am primit fisiere! Lista: {self.request.FILES.keys()}", file=sys.stderr)
        else:
            print("DEBUG UPLOAD: ATENTIE! Nu s-au primit fisiere.", file=sys.stderr)
        # --- DEBUGGING END ---

        context = self.get_context_data()
        godparent_formset = context['godparent_formset']
        schedule_item_formset = context['schedule_item_formset']
        # <--- LINIE NOUĂ: Extragem formset-ul din context
        gallery_image_formset = context['gallery_image_formset']

        # Validare completă (inclusiv galeria)
        if form.is_valid() and godparent_formset.is_valid() and schedule_item_formset.is_valid() and gallery_image_formset.is_valid():
            self.object = form.save(commit=False)
            self.object.owner = self.request.user
            self.object.save()

            godparent_formset.instance = self.object
            godparent_formset.save()

            schedule_item_formset.instance = self.object
            schedule_item_formset.save()

            # <--- LINIE NOUĂ: Salvăm galeria
            gallery_image_formset.instance = self.object
            gallery_image_formset.save()

            messages.success(self.request, _(f"Event '{self.object.title}' created!"))
            return redirect(self.get_success_url())
        else:
            print(f"DEBUG UPLOAD: Formular invalid. Errors: {form.errors}", file=sys.stderr)
            # Verificăm și erorile din galerie pentru debug
            if not gallery_image_formset.is_valid():
                print(f"DEBUG GALERIE: Erori galerie: {gallery_image_formset.errors}", file=sys.stderr)

            return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse_lazy('invapp:guest_list', kwargs={'event_id': self.object.id})


class EventUpdateView(LoginRequiredMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'invapp/event_form_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Logică Plan Blocat
        is_locked = False
        if hasattr(user, 'userprofile') and user.userprofile.plan and user.userprofile.plan.lock_event_on_creation:
            is_locked = True
            form = context.get('form')
            if form:
                for f in ['event_type', 'event_date', 'selected_design']:
                    if f in form.fields:
                        form.fields[f].disabled = True
        context['is_locked_plan'] = is_locked

        # Logică Design-uri
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
            # <--- LINIE NOUĂ: Formset Galerie cu instance=self.object
            context['gallery_image_formset'] = GalleryImageFormSet(self.request.POST, self.request.FILES,
                                                                   instance=self.object)
        else:
            context['godparent_formset'] = GodparentFormSet(instance=self.object)
            context['schedule_item_formset'] = ScheduleItemFormSet(instance=self.object)
            # <--- LINIE NOUĂ: Formset Galerie populat cu imaginile existente
            context['gallery_image_formset'] = GalleryImageFormSet(instance=self.object)

        return context

    def form_valid(self, form):
        print(f"DEBUG UPDATE: Userul {self.request.user} actualizeaza evenimentul.", file=sys.stderr)

        context = self.get_context_data()
        godparent_formset = context['godparent_formset']
        schedule_item_formset = context['schedule_item_formset']
        # <--- LINIE NOUĂ
        gallery_image_formset = context['gallery_image_formset']

        # Validare completă
        if form.is_valid() and godparent_formset.is_valid() and schedule_item_formset.is_valid() and gallery_image_formset.is_valid():
            self.object = form.save()

            godparent_formset.instance = self.object
            godparent_formset.save()

            schedule_item_formset.instance = self.object
            schedule_item_formset.save()

            # <--- LINIE NOUĂ: Salvare galerie (adăugare/ștergere)
            gallery_image_formset.instance = self.object
            gallery_image_formset.save()

            messages.success(self.request, _("Event updated."))
            return redirect(self.get_success_url())
        else:
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


# --- Preview View ---
@csrf_exempt
@xframe_options_exempt
def event_preview_view(request):
    if request.method != 'POST': return HttpResponse("Invalid", status=400)
    try:
        data = json.loads(request.body)

        # --- 1. Gestionare dată și oră (Date & Time) ---
        date_str = data.get('event_date')
        if date_str:
            try:
                data['event_date'] = datetime.strptime(date_str, "%Y-%m-%d").date()
            except:
                data['event_date'] = None

        time_str = data.get('party_time')
        if time_str:
            try:
                data['party_time'] = datetime.strptime(time_str, "%H:%M").time()
            except:
                data['party_time'] = None

        mock_event = SimpleNamespace(**data)

        # --- 2. Gestionare Imagini (Images) ---
        for field in ['couple_photo', 'landscape_photo', 'main_invitation_image']:
            img = data.get(field)
            if img and img.startswith('data:image'):
                setattr(mock_event, field, SimpleNamespace(url=img))
            elif isinstance(img, str):
                setattr(mock_event, field, SimpleNamespace(url=f"{settings.MEDIA_URL}{img}"))
            else:
                setattr(mock_event, field, None)

        # --- 3. Gestionare Design ---
        design_id = data.get('selected_design')
        if not design_id: return HttpResponse("No design", status=400)
        design = CardDesign.objects.get(id=design_id)

        # --- 4. Mock Guest (Folosind unique_id) ---
        # Folosim un UUID valid (0000...) pentru a nu crăpa validarea URL-urilor din template
        mock_guest = SimpleNamespace(
            unique_id='00000000-0000-0000-0000-000000000000',
            name='Nume Invitat',
            honorific='family',
            max_attendees=5,
            manual_is_attending=None, # Necesar pentru logica din image_based_invite
            rsvp_details=SimpleNamespace(attending=None) # Simulam lipsa unui raspuns anterior
        )

        # --- 5. Mock Form (Critic pentru afișarea RSVP) ---
        # Instantiem formularul gol pentru a putea randa campurile in preview
        from .forms import RSVPForm
        mock_form = RSVPForm(guest=mock_guest)

        context = {
            'event': mock_event,
            'guest': mock_guest,
            'form': mock_form,
            'is_preview': True
        }

        # --- 6. Randare cu Request (Critic pentru CSRF Token) ---
        html = render_to_string(design.template_name, context, request=request)
        return HttpResponse(html)

    except Exception as e:
        print(f"Preview Error: {e}")
        # Returnam eroarea ca text pentru a o vedea in consola browserului daca ceva nu merge
        return HttpResponse(f"Error: {e}", status=500)


# --- Guest Management Views ---
@login_required
def guest_list(request, event_id):
    event = get_object_or_404(Event, pk=event_id, owner=request.user)

    # 1. Preluăm datele
    guests_queryset = Guest.objects.filter(event=event).select_related('rsvp_details')
    guests_list = list(guests_queryset)  # Convertim în listă pentru sortare Python

    # 2. Preluăm parametrul din URL (asta trimite HTML-ul tău)
    sort_param = request.GET.get('sort', 'name')

    # Funcție ajutătoare pentru status
    def status_priority(guest):
        if guest.is_attending is True: return 0  # Primii
        if guest.is_attending is None: return 1  # Mijloc
        return 2  # Ultimii

    # 3. Aplicăm sortarea pe baza parametrului primit
    if sort_param == 'name':
        guests_list.sort(key=lambda g: g.name.lower())
    elif sort_param == '-name':
        guests_list.sort(key=lambda g: g.name.lower(), reverse=True)
    elif sort_param == 'status':
        guests_list.sort(key=lambda g: (status_priority(g), g.name.lower()))
    elif sort_param == '-status':
        guests_list.sort(key=lambda g: (status_priority(g), g.name.lower()), reverse=True)

    # Recalculăm totalul
    total_attending = sum(g.attending_count for g in guests_list)

    # 4. Trimitem 'current_sort' înapoi la HTML
    # Fără asta, HTML-ul nu știe să pună săgeata corectă!
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event'] = self.object.event
        context['form_title'] = _(f'Edit Guest: {self.object.name}')
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
        new_count = int(data.get('number_attending', 0))

        guest.manual_attending_count = new_count
        guest.manual_is_attending = True if new_count > 0 else False
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

    # --- LOGIC FOR SUBSCRIPTIONS ---
    # We check if the plan is marked as recurring in the database.
    # If you haven't added the 'is_recurring' field to models.py yet,
    # this defaults to False (standard one-time payment).
    if getattr(plan, 'is_recurring', False):
        checkout_mode = 'subscription'
    else:
        checkout_mode = 'payment'

    try:
        session = stripe.checkout.Session.create(
            customer_email=request.user.email,

            # Metadata is critical for the Webhook to identify the user later
            metadata={
                'user_id': request.user.id,
                'plan_id': plan.id
            },

            success_url=request.build_absolute_uri(reverse('invapp:payment_success')),
            cancel_url=request.build_absolute_uri(reverse('invapp:payment_cancel')),

            # Dynamic Mode: Switches between 'payment' and 'subscription' automatically
            mode=checkout_mode,

            line_items=[{
                'price': plan.stripe_price_id,
                'quantity': 1
            }]
        )
        return redirect(session.url, code=303)

    except Exception as e:
        messages.error(request, f"Stripe Error: {e}")
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
    except ValueError as e:
        print(f"❌ Error: Invalid payload")
        return HttpResponse(status=400)
    except stripe.SignatureVerificationError as e:
        print(f"❌ Error: Signature verification failed.")
        return HttpResponse(status=400)

    # --- 1. PLATA FINALIZATĂ (One-Time sau Prima lună de Subscripție) ---
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        print(f"💰 Payment Succeeded for Session ID: {session.get('id')}")

        user_id = session.get('metadata', {}).get('user_id')
        plan_id = session.get('metadata', {}).get('plan_id')

        # Verificăm dacă există subscription ID (pentru planuri recurente)
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

                # OPTIONAL: Dacă vrei să salvezi ID-ul subscripției pentru a o gestiona mai târziu
                # Trebuie să adaugi câmpul 'stripe_subscription_id' în modelul UserProfile mai întâi
                # if subscription_id:
                #     profile.stripe_subscription_id = subscription_id

                profile.save()

                print(f"✅ SUCCESS: Upgraded {user.username} to plan '{new_plan.name}'")
            except Exception as e:
                print(f"❌ ERROR updating DB: {str(e)}")
                return HttpResponse(status=200)

    # --- 2. SUBSCRIERE NOUĂ CREATĂ (Specific pentru Event Planners) ---
    elif event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        subscription_id = subscription.get('id')
        customer_id = subscription.get('customer')
        print(f"🆕 Subscription CREATED: {subscription_id} for Customer: {customer_id}")

        # NOTĂ: De obicei, logica de activare a planului este deja tratată în
        # checkout.session.completed mai sus. Aici poți adăuga logică suplimentară
        # doar dacă ai nevoie să reacționezi strict la crearea obiectului de subscripție.
        # Pentru moment, doar logăm evenimentul pentru a confirma că funcționează.

    # --- 3. ANULARE SUBSCRIERE ---
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
                    # Downgrade la planul Free sau NULL
                    # Asumăm că planul Free are un ID specific sau logică de fallback
                    # Aici îl setăm pe None momentan
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
    messages.success(request, "Payment successful! Your plan has been upgraded.")
    return redirect('invapp:dashboard')


@login_required
def payment_cancel_view(request):
    messages.warning(request, "Payment cancelled.")
    return redirect(reverse('invapp:landing_page') + '#pricing')


@login_required
def manual_upgrade_page_view(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    return render(request, 'invapp/upgrade_page.html', {'plan': plan})


# --- Guest Import/Export ---
@login_required
def download_guest_template_view(request, event_id):
    df = pd.DataFrame(columns=['Honorific', 'Name', 'Email', 'Phone Number', 'Max Attendees'])
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
            # Basic validation
            if 'Name' not in df.columns: raise ValueError("Missing 'Name' column")

            current_count = event.guests.count()
            limit = request.user.userprofile.plan.max_guests
            to_add = df['Name'].dropna().count()

            if current_count + to_add > limit:
                messages.error(request, _("Import exceeds guest limit."))
                return redirect('invapp:guest_list', event_id=event.id)

            objs = []
            for _, row in df.iterrows():
                if pd.isna(row['Name']): continue
                objs.append(Guest(
                    event=event, owner=request.user, name=str(row['Name']).strip(),
                    email=row.get('Email') if pd.notna(row.get('Email')) else None,
                    max_attendees=int(row.get('Max Attendees', 1))
                ))
            Guest.objects.bulk_create(objs)
            messages.success(request, f"Imported {len(objs)} guests.")
        except Exception as e:
            messages.error(request, f"Import error: {e}")
    return redirect('invapp:guest_list', event_id=event.id)


class terms_of_service_view(TemplateView): template_name = "invapp/terms_and_conditions.html"


class privacy_policy_view(TemplateView): template_name = "invapp/privacy_policy.html"


# --- TEMPORARY FIX VIEW (Add this at the bottom) ---
def fix_site_domain(request):
    """
    Updates the Site object in the database to match the current hostname (invapp-romania.ro).
    Useful for fixing 'Site matching query does not exist' errors after domain change.
    """
    try:
        current_domain = request.get_host()  # Should capture 'invapp-romania.ro'

        # Get the default Site (ID=1) - create if missing
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
    Afișează pagina de Întrebări Frecvente.
    """
    faqs = FAQ.objects.filter(is_visible=True).order_by('order')
    return render(request, 'invapp/faq.html', {'faqs': faqs})


from django.contrib.auth.decorators import login_required


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
                if 'facebook' in provider_str:
                    target_account = account
                    break
                elif 'google' in provider_str:
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
                provider_name = 'google'  # Asta va salva 'google' in DB -> Badge Rosu in Admin
            elif 'facebook' in raw_provider or raw_provider.isdigit():
                provider_name = 'facebook'  # Asta va salva 'facebook' in DB -> Badge Albastru
            else:
                provider_name = 'email'

            try:
                social_avatar_url = target_account.get_avatar_url()
            except Exception:
                pass

            # B. Încercare Manuală Google
            if not social_avatar_url and provider_name == 'google':
                social_avatar_url = extra_data.get('picture')

            # C. Încercare Manuală Facebook
            if not social_avatar_url and provider_name == 'facebook':
                picture_data = extra_data.get('picture', {})
                if isinstance(picture_data, dict):
                    social_avatar_url = picture_data.get('data', {}).get('url')
                elif isinstance(picture_data, str):
                    social_avatar_url = picture_data

                # D. Fallback Suprem Facebook
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

            # Nume
            full_name = request.user.get_full_name()
            if not full_name:
                full_name = request.user.username.split('@')[0]
            review.client_name = full_name

            # Avatar
            if social_avatar_url:
                review.avatar_url = social_avatar_url

            # Provider - AICI SE SALVEAZA IN BAZA DE DATE
            # Daca provider_name este 'google', in Admin va aparea 'Google'
            review.social_provider = provider_name

            review.save()
            messages.success(request, "Îți mulțumim pentru feedback!")
            return redirect('invapp:dashboard')  # Sau unde doresti sa redirectionezi
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
    View special pentru dashboard când nu există niciun invitat real.
    Generează un invitat fictiv în memorie.
    """
    event = get_object_or_404(Event, pk=event_id)

    # Securitate: Doar proprietarul poate vedea demo-ul
    if event.owner != request.user:
        return HttpResponseForbidden("Nu ai permisiunea să vizualizezi acest eveniment.")

    # Dacă evenimentul nu are design selectat
    if not event.selected_design:
        messages.warning(request, "Selectează un design pentru a vedea previzualizarea.")
        return redirect('invapp:event_update', pk=event.id)

    # 1. Creăm un Guest Fictiv (Nu se salvează în DB)
    dummy_guest = SimpleNamespace(
        unique_id='00000000-0000-0000-0000-000000000000',  # UUID Valid ca format
        name='Nume Invitat Exemplu',  # Dummy Name cerut
        honorific='family',
        max_attendees=2,
        manual_is_attending=None,
        rsvp_details=SimpleNamespace(attending=None),  # Simulăm lipsa RSVP
        event=event
    )

    # 2. Creăm un Formular gol legat de acest guest fictiv
    form = RSVPForm(guest=dummy_guest)

    # 3. Context
    context = {
        'event': event,
        'guest': dummy_guest,
        'form': form,
        'is_preview': True,  # Activăm modul preview (ascunde butoanele de submit)
        'google_calendar_link': None
    }

    return render(request, event.selected_design.template_name, context)

def upgrade_plan(request):
    """Pagina unde utilizatorii pot vedea planurile si face upgrade."""
    return render(request, 'invapp/upgrade_page.html')


class EventLivePreviewView(LoginRequiredMixin, View):
    """
    View special pentru a randa preview-ul fără a salva datele în DB.
    Primește datele din formular via POST.
    """

    def post(self, request, *args, **kwargs):
        # 1. Extragem datele din request.POST fără a salva
        form = EventForm(request.POST, request.FILES)

        # Chiar dacă formularul nu e 100% valid (ex: lipsesc câmpuri opționale),
        # încercăm să randăm ce avem pentru preview.
        event_instance = form.save(commit=False)
        event_instance.owner = request.user

        # 2. Gestionare Design (Critic pentru randare)
        design_id = request.POST.get('selected_design')
        if design_id:
            try:
                design = CardDesign.objects.get(pk=design_id)
                event_instance.selected_design = design
            except CardDesign.DoesNotExist:
                return HttpResponse("Design invalid selectat.", status=400)
        else:
            return HttpResponse("Te rugăm să selectezi un design pentru preview.", status=400)

        # 3. Gestionare Imagini (Live Upload - Hack pentru Preview)
        # Citim imaginea direct din memorie și o convertim în Base64 pentru a o afișa
        # fără a o salva pe disk/Cloudinary.
        if 'couple_photo' in request.FILES:
            f = request.FILES['couple_photo']
            try:
                img_data = base64.b64encode(f.read()).decode('utf-8')
                # Aici "păcălim" template-ul să folosească string-ul base64 în loc de URL
                # Trebuie să modificăm template-ul invitației să accepte asta sau să suprascriem atributul.
                # O metodă robustă e să setăm un atribut temporar pe obiect.
                event_instance.preview_couple_photo_b64 = f"data:{f.content_type};base64,{img_data}"
            except Exception:
                pass  # Dacă eșuează conversia, nu afișăm poza nouă

        # 4. Context pentru Template
        context = {
            'event': event_instance,
            'guest': None,  # Preview-ul nu are un invitat specific
            'is_preview': True,  # Flag util în template pentru a ascunde butoane de RSVP etc.
        }

        # 5. Randare
        try:
            return render(request, design.template_name, context)
        except Exception as e:
            return HttpResponse(f"Eroare la generare preview: {str(e)}", status=500)