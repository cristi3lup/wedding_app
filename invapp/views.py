from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.contrib.auth.models import User
from .models import UserProfile, Event, Guest, RSVP, Table, TableAssignment, CardDesign, Plan
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
import stripe
from datetime import datetime, timedelta
from types import SimpleNamespace
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .forms import (
    GuestForm, EventForm, GuestContactForm, AssignGuestForm,
    RSVPForm, TableForm, CustomUserCreationForm, TableAssignmentForm,
    GuestCreateForm, GodparentFormSet, ScheduleItemFormSet
)


# --- CSV Export View ---
@login_required
def export_assignments_csv(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if event.owner != request.user:
        return HttpResponseForbidden(_("You do not have permission to export data for this event."))

    response = HttpResponse(content_type='text/csv')
    response[
        'Content-Disposition'] = f'attachment; filename="event_{event.title.replace(" ", "_")}_table_assignments.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Guest Name', 'Phone Number', 'Email', 'Assigned Table',
        'Number Attending', 'Invitation Method', 'Type', 'Meal Preferences'
    ])

    assignments = TableAssignment.objects.filter(table__event=event) \
        .select_related('guest', 'table', 'guest__rsvp_details') \
        .order_by('table__name', 'guest__name')

    for assignment in assignments:
        guest = assignment.guest
        writer.writerow([
            guest.name,
            guest.phone_number if guest.phone_number else '',
            guest.email if guest.email else '',
            assignment.table.name,
            guest.attending_count,
            guest.get_invitation_method_display(),
            guest.get_honorific_display(),  # Assuming gender/honorific logic
            guest.rsvp_details.meal_preference if hasattr(guest, 'rsvp_details') else '',
        ])
    return response


# --- Invitation & RSVP View ---
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

    return render(request, 'invapp/landing_page_tailwind.html', {'designs': designs, 'plans': plans})


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
    # UPDATED: Order by event_date
    events = Event.objects.filter(
        owner=request.user
    ).select_related(
        'selected_design'
    ).prefetch_related(
        'guests'
    ).order_by('-event_date')  # Fixed sorting

    user_guests = Guest.objects.filter(event__owner=request.user)
    guest_count = user_guests.count()

    context = {
        'events': events,
        'guests': user_guests,
        'guest_count': guest_count,
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
            else:
                messages.error(self.request, _("Profile error."))
                return redirect('invapp:dashboard')
        except ObjectDoesNotExist:
            return redirect('invapp:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        available_designs = CardDesign.objects.none()
        if hasattr(user, 'userprofile') and user.userprofile.plan:
            available_designs = user.userprofile.plan.card_designs.all()
        else:
            try:
                free_plan = Plan.objects.get(price=0)
                available_designs = free_plan.card_designs.all()
            except Plan.DoesNotExist:
                pass

        design_fields = {}
        for design in available_designs.prefetch_related('special_fields'):
            names = [f.name for f in design.special_fields.all()]
            if names: design_fields[slugify(design.name)] = names

        context['design_specific_fields_json'] = json.dumps(design_fields)
        context['available_designs'] = available_designs

        if self.request.POST:
            context['godparent_formset'] = GodparentFormSet(self.request.POST, self.request.FILES)
            context['schedule_item_formset'] = ScheduleItemFormSet(self.request.POST, self.request.FILES)
        else:
            context['godparent_formset'] = GodparentFormSet()
            context['schedule_item_formset'] = ScheduleItemFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        godparent_formset = context['godparent_formset']
        schedule_item_formset = context['schedule_item_formset']

        if form.is_valid() and godparent_formset.is_valid() and schedule_item_formset.is_valid():
            self.object = form.save(commit=False)
            self.object.owner = self.request.user
            self.object.save()

            godparent_formset.instance = self.object
            godparent_formset.save()

            schedule_item_formset.instance = self.object
            schedule_item_formset.save()

            messages.success(self.request, _(f"Event '{self.object.title}' created!"))
            return redirect(self.get_success_url())
        else:
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
        is_locked = False
        if hasattr(user, 'userprofile') and user.userprofile.plan and user.userprofile.plan.lock_event_on_creation:
            is_locked = True
            form = context.get('form')
            if form:
                # UPDATED: Locked fields include event_date and party_time
                for f in ['event_type', 'event_date', 'selected_design']:
                    if f in form.fields: form.fields[f].disabled = True

        context['is_locked_plan'] = is_locked

        # Available designs logic (same as create)
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
            if names: design_fields[slugify(design.name)] = names

        # Ensure current design is visible even if not available
        current = self.object.selected_design
        if current:
            slug = slugify(current.name)
            if slug not in design_fields:
                names = [f.name for f in current.special_fields.all()]
                if names: design_fields[slug] = names

        context['design_specific_fields_json'] = json.dumps(design_fields)
        context['available_designs'] = available_designs

        if self.request.POST:
            context['godparent_formset'] = GodparentFormSet(self.request.POST, self.request.FILES, instance=self.object)
            context['schedule_item_formset'] = ScheduleItemFormSet(self.request.POST, self.request.FILES,
                                                                   instance=self.object)
        else:
            context['godparent_formset'] = GodparentFormSet(instance=self.object)
            context['schedule_item_formset'] = ScheduleItemFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        godparent_formset = context['godparent_formset']
        schedule_item_formset = context['schedule_item_formset']

        if form.is_valid() and godparent_formset.is_valid() and schedule_item_formset.is_valid():
            self.object = form.save()
            godparent_formset.instance = self.object
            godparent_formset.save()

            schedule_item_formset.instance = self.object
            schedule_item_formset.save()

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
def event_preview_view(request):
    if request.method != 'POST': return HttpResponse("Invalid", status=400)
    try:
        data = json.loads(request.body)

        # --- UPDATED: Handle event_date and party_time ---
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

        # Handle Images
        for field in ['couple_photo', 'landscape_photo', 'main_invitation_image']:
            img = data.get(field)
            if img and img.startswith('data:image'):
                setattr(mock_event, field, SimpleNamespace(url=img))
            elif isinstance(img, str):
                setattr(mock_event, field, SimpleNamespace(url=f"{settings.MEDIA_URL}{img}"))
            else:
                setattr(mock_event, field, None)

        design_id = data.get('selected_design')
        if not design_id: return HttpResponse("No design", status=400)
        design = CardDesign.objects.get(id=design_id)

        mock_guest = SimpleNamespace(uuid='preview', name='Guest Name', honorific='mr')  # Dummy guest

        context = {'event': mock_event, 'guest': mock_guest, 'is_preview': True}
        html = render_to_string(design.template_name, context)
        return HttpResponse(html)
    except Exception as e:
        print(f"Preview Error: {e}")
        return HttpResponse(f"Error: {e}", status=500)


# --- Guest Management Views ---
@login_required
def guest_list(request, event_id):
    event = get_object_or_404(Event, pk=event_id, owner=request.user)
    guests = Guest.objects.filter(event=event).select_related('rsvp_details').order_by('name')
    total = sum(g.attending_count for g in guests)
    return render(request, 'invapp/guest_list_tailwind.html',
                  {'event': event, 'guests': guests, 'total_attending': total})


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
    try:
        session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            metadata={'user_id': request.user.id, 'plan_id': plan.id},
            success_url=request.build_absolute_uri(reverse('invapp:payment_success')),
            cancel_url=request.build_absolute_uri(reverse('invapp:payment_cancel')),
            mode='payment',
            line_items=[{'price': plan.stripe_price_id, 'quantity': 1}]
        )
        return redirect(session.url, code=303)
    except Exception as e:
        messages.error(request, f"Stripe Error: {e}")
        return redirect(reverse('invapp:landing_page') + '#pricing')


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        uid = session.get('metadata', {}).get('user_id')
        pid = session.get('metadata', {}).get('plan_id')
        if uid and pid:
            try:
                user = User.objects.get(id=uid)
                plan = Plan.objects.get(id=pid)
                if not hasattr(user, 'userprofile'): UserProfile.objects.create(user=user)
                user.userprofile.plan = plan
                user.userprofile.save()
            except:
                pass
    return HttpResponse(status=200)


@login_required
def payment_success_view(request):
    messages.success(request, "Payment successful! Plan upgraded.")
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