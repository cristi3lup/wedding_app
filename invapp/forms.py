# invapp/forms.py

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
# Make sure all relevant models are imported
from .models import RSVP, Guest, TableAssignment, Table, Event, Godparent, ScheduleItem
from .models import CardDesign
from django import forms
from django.db.models import Q
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy

from allauth.account.forms import SignupForm
from django.urls import reverse_lazy
from .models import Guest # Make sure Guest is imported
INPUT_CLASSES = "block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-600 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 bg-gray-50 dark:bg-gray-700 dark:text-white dark:ring-gray-500"
INPUT_CLASSES_WITH_ICON = f"{INPUT_CLASSES} pl-10"


class RSVPForm(forms.ModelForm):
    class Meta:
        model = RSVP
        fields = ['attending', 'number_attending', 'meal_preference', 'message']
        widgets = {
            'attending': forms.RadioSelect,
            'number_attending': forms.NumberInput(attrs={'class': INPUT_CLASSES}),
            'meal_preference': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 3}),
            'message': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        # We pop the 'guest' argument before initializing the form
        self.guest = kwargs.pop('guest', None)
        super().__init__(*args, **kwargs)

    def clean_number_attending(self):
        number = self.cleaned_data.get('number_attending')
        # Check if the number exceeds the guest's limit
        if number and self.guest and number > self.guest.max_attendees:
            raise forms.ValidationError(
                _(f"Value must be less than or equal to {self.guest.max_attendees}, please contact event host.")
            )
        return number

# --- Add this new form ---
class TableAssignmentAdminForm(forms.ModelForm):
    class Meta:
        model = TableAssignment
        fields = '__all__' # Use all fields from the TableAssignment model

    # Add custom validation for the 'guest' field
    def clean_guest(self):
        guest = self.cleaned_data.get('guest') # Get the selected Guest object
        if guest:
            try:
                # Check if the related RSVP exists and attending is True
                if not guest.rsvp_details.attending: # Access related RSVP via related_name
                    raise forms.ValidationError_("Invalid choice: This guest has not RSVP'd Yes.")
            except RSVP.DoesNotExist:
                # Handle case where the guest has no RSVP record at all
                raise forms.ValidationError_("Invalid choice: This guest has not RSVP'd.")
        # Important: Always return the cleaned field data
        return guest

class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ['name', 'capacity'] # Fields the customer will fill
        labels = {
            'name': _('Table Name or Number'),
            'capacity': _('Capacity (Number of Seats)'),
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'capacity': forms.NumberInput(attrs={'class': INPUT_CLASSES}),
        }

class AssignGuestForm(forms.Form):
    # We'll set the querysets dynamically in the view
    guest = forms.ModelChoiceField(queryset=Guest.objects.none(), label=_("Assign Guest"))
    table = forms.ModelChoiceField(queryset=Table.objects.none(), label=_("To Table"))

    # Initialize form with querysets filtered for the specific event and unassigned guests
    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None) # Get event passed from view
        super().__init__(*args, **kwargs)

        if event:
            # Get IDs of guests already assigned to any table for this event
            assigned_guest_ids = TableAssignment.objects.filter(table__event=event).values_list('guest_id', flat=True)

            # Filter guests: must belong to the event, have RSVP'd Yes, and NOT be in the assigned list
            self.fields['guest'].queryset = Guest.objects.filter(
                event=event,
                rsvp_details__attending=True
            ).exclude(
                id__in=assigned_guest_ids
            )

            # Filter tables: must belong to the event
            self.fields['table'].queryset = Table.objects.filter(event=event)

            def clean(self):
                cleaned_data = super().clean()
                guest = cleaned_data.get('Assign Guest')
                table = cleaned_data.get('To Table')

                if guest and table:
                    # ... (check if guest already assigned) ...

                    # Capacity Check using guest's attending_count property
                    guest_actual_attendees = guest.attending_count  # Uses the property from Guest model

                    # table.remaining_capacity already uses the sum of attending_counts of currently seated guests
                    # Your original f-string
                    # f"Not enough capacity at {table.name}. "
                    # f"Needs {guest_actual_attendees} seat(s) for {guest.name}, "
                    # f"but only {table.remaining_capacity} seat(s) are available."

                    if table.remaining_capacity < guest_actual_attendees:
                        # 1. Define the translatable singular and plural error messages
                        #    The number to check for plurals is guest_actual_attendees.
                        error_message = ngettext_lazy(
                            # Singular string (when guest_actual_attendees is 1)
                            "Not enough capacity at {table_name}. "
                            "Needs {needed_seats} seat for {guest_name}, "
                            "but only {available_seats} seat(s) are available.",

                            # Plural string (for 0 or 2+ seats)
                            "Not enough capacity at {table_name}. "
                            "Needs {needed_seats} seats for {guest_name}, "
                            "but only {available_seats} seat(s) are available.",

                            # The number that decides singular/plural
                            guest_actual_attendees
                        )

                        # 2. Add the error, formatting the string with your variables
                        self.add_error(
                            'table',
                            error_message.format(
                                table_name=table.name,
                                needed_seats=guest_actual_attendees,
                                guest_name=guest.name,
                                available_seats=table.remaining_capacity
                            )
                        )

                    return cleaned_data

class EventForm(forms.ModelForm):
     class Meta:
        model = Event
        # Specify fields the customer CAN edit
        fields = [
            'event_type', 'title', 'event_date','party_time', 'venue_name', 'venue_address',
            'bride_name', 'groom_name', 'bride_parents', 'groom_parents', # Wedding fields
            'child_name', 'parents_names',
            #'godparents',
             # Baptism fields
            'Maps_embed_url','ceremony_maps_url','party_maps_url', 'calendar_description',
            'ceremony_time', 'ceremony_location',
            'invitation_wording', 'schedule_details', 'other_info',
            'couple_photo',
            'landscape_photo',
            'selected_design',
            'main_invitation_image', 'audio_greeting',

        ]


        # Optional: Add widgets for better user experience
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASSES}),
             'event_date': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': INPUT_CLASSES}
            ),
            'party_time': forms.TimeInput(
                format='%H:%M',
                attrs={'type': 'time', 'class': INPUT_CLASSES}
            ),
            'venue_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'venue_address': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 3}),
            'bride_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'groom_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'bride_parents': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'groom_parents': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'child_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'parents_names': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'ceremony_maps_url': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'party_maps_url': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'calendar_description': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 3}),
            'ceremony_time': forms.TimeInput(
                format='%H:%M',
                attrs={'type': 'time', 'class': INPUT_CLASSES}
            ),
            'ceremony_location': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'invitation_wording': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 5}),
            'schedule_details': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 4}),
            'other_info': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 4}),
            'selected_design': forms.RadioSelect(),
        }
        help_texts = {
            'Maps_embed_url': _('Find venue on Google Maps, click Share > Embed > Copy SRC URL.'),
        }

# invapp/forms.py
# ... (other imports and forms) ...

# --- Add form for creating/editing Guests by customer ---
class GuestForm(forms.ModelForm):
    class Meta:
        model = Guest
        # --- THE FIX: 'honorific' is now the first field in the list ---
        fields = [
            'honorific',
            'name',
            'phone_number',
            'email',
            'max_attendees',
            'invitation_method',
            'manual_is_attending',
            'manual_attending_count',
        ]
        labels = {
            'honorific': _("Courtesy Title"),
            'name': _("Guest/Group Name (e.g., 'The Smith Family', 'John Doe')"),
            'phone_number': _('Phone Number (Optional)'),
            'email': _('Email Address (Optional)'),
            'max_attendees': _('Max Number of People Invited (including guest)'),
            'invitation_method': _('Invitation Method'),
            'manual_is_attending': _('Manually Confirmed Attending?'),
            'manual_attending_count': _('Number Confirmed Attending (Manual)'),
        }
        help_texts = {
            'max_attendees': _('Enter the total number of people this invitation covers (e.g., 2 for a couple).'),
            'name': _('Full name of the primary guest or couple/family name.'),
            'email': _('Primary email for the invitation.'),
            'manual_is_attending': _('Set this if guest confirmed verbally or via physical RSVP card.'),
            'manual_attending_count': _('If attending, how many? Overrides digital RSVP if set.'),
        }
        widgets = {
            'honorific': forms.Select(attrs={'class': INPUT_CLASSES}),
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES_WITH_ICON, 'placeholder': 'John Doe'}),
            'phone_number': forms.TextInput(attrs={'class': INPUT_CLASSES_WITH_ICON, 'placeholder': '+40...'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASSES_WITH_ICON, 'placeholder': 'john@example.com'}),
            'max_attendees': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'min': '1', 'value': '1'}),
            'invitation_method': forms.Select(attrs={'class': INPUT_CLASSES}),
            'manual_is_attending': forms.Select(choices=[(None, _('Unknown')), (True, _('Yes')), (False, _('No'))],
                                                attrs={'class': INPUT_CLASSES}),
            'manual_attending_count': forms.NumberInput(attrs={'class': INPUT_CLASSES}),
        }

class GuestCreateForm(GuestForm):
    class Meta(GuestForm.Meta):
        # We inherit everything from GuestForm but limit the fields
        fields = [
            'honorific',
            'name',
            'phone_number',
            'email',
            'max_attendees',
        ]

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text=_('A valid email address is required for account confirmation.'),
        widget = forms.EmailInput(attrs={'class': INPUT_CLASSES})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("An account with this email address already exists."))
        return email

class GuestChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        meal_prefs = obj.rsvp_details.meal_preference if hasattr(obj, 'rsvp_details') and obj.rsvp_details else _("Not specified")
        # We use the new smart property for the label too, to be consistent
        count = obj.attending_count
        return format_html(
            """
            <span class="font-bold text-gray-900">{}</span>
            <span class="text-gray-600"> ({} pers.)</span>
            <p class="text-xs text-gray-500 mt-1">Meal: {}</p>
            """,
            obj.name,
            count,
            meal_prefs
        )


# This is our new form with debugging statements added.
class TableAssignmentForm(forms.Form):
    guests = GuestChoiceField(
        queryset=Guest.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label=_("Select guests to assign")
    )
    table = forms.ModelChoiceField(
        queryset=Table.objects.none(),
        required=True,
        label=_("Assign selected guests to"),
        widget = forms.Select(attrs={'class': INPUT_CLASSES})
    )

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

        if event:
            print("\n--- DEBUG: Populating Table Assignment Form ---")

            # Step 1: Get IDs of guests who are already assigned to a table.
            assigned_guest_ids = TableAssignment.objects.filter(
                table__event=event
            ).values_list('guest_id', flat=True)

            # Step 2: Filter guests who are "Attending"
            # Logic: (Manual=True) OR (Manual=None AND RSVP=True)
            # This EXCLUDES (Manual=False) which solves your bug.
            attending_guests = Guest.objects.filter(
                Q(event=event) & (
                        Q(manual_is_attending=True) |
                        (Q(manual_is_attending__isnull=True) & Q(rsvp_details__attending=True))
                )
            )

            # Step 3: Exclude already assigned guests
            final_queryset = attending_guests.exclude(id__in=assigned_guest_ids).distinct()

            self.fields['guests'].queryset = final_queryset
            self.fields['table'].queryset = Table.objects.filter(event=event)

    def clean(self):
        cleaned_data = super().clean()
        guests = cleaned_data.get('guests')
        table = cleaned_data.get('table')

        if guests and table:
            total_new_attendees = sum(guest.attending_count for guest in guests)
            if table.remaining_capacity < total_new_attendees:
                self.add_error(None,
                               _(f"Not enough capacity at {table.name}. "
                                 f"Assigning these guests requires {total_new_attendees} seat(s), "
                                 f"but only {table.remaining_capacity} seat(s) are available.")
                               )
        return cleaned_data

class GuestContactForm(forms.ModelForm):
    """
    A form for guests to optionally provide their contact info after RSVPing.
    """
    class Meta:
        model = Guest
        # These are the only fields the guest can update on the thank you page.
        fields = ['email', 'phone_number']
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': 'your.email@example.com',
                'class': 'INPUT_CLASSES_WITH_ICON'
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': '+40712345678',
                'class': 'INPUT_CLASSES_WITH_ICON'
            }),
        }

# --- ADD THIS NEW FORM AT THE BOTTOM ---
class CustomSignupForm(SignupForm):
    # We define the field here without the label first.
    terms_agreement = forms.BooleanField(required=True)

    def __init__(self, *args, **kwargs):
        super(CustomSignupForm, self).__init__(*args, **kwargs)
        # THE FIX: We set the label dynamically here, after all modules have loaded.
        # This breaks the circular import loop.
        self.fields['terms_agreement'].label = format_html(
            _('I agree to the <a href="{}" target="_blank" class="text-indigo-600 hover:underline">Terms and Conditions</a> and <a href="{}" target="_blank" class="text-indigo-600 hover:underline">Privacy Policy</a>.'),
            reverse_lazy('invapp:terms_and_conditions'),
            reverse_lazy('invapp:privacy_policy')
        )

    def save(self, request):
        # Save the user account using the parent class's save method
        user = super(CustomSignupForm, self).save(request)

        # --- NEW: Automatically assign the Free Plan ---
        try:
            # Find the free plan (assuming it has a price of 0)
            free_plan = Plan.objects.get(price=0)

            # Create a UserProfile for the new user and assign the free plan
            UserProfile.objects.create(user=user, plan=free_plan)

        except Plan.DoesNotExist:
            # This is a fallback in case you haven't created a free plan
            # in the admin yet. You can decide to create a profile
            # with no plan, or just log a warning.
            print(f"WARNING: No free plan (price=0) found. User {user.email} was created without a plan.")
            # Optionally, create a profile with no plan:
            # UserProfile.objects.create(user=user, plan=None)
            pass
        except Exception as e:
            # Handle other potential errors
            print(f"An error occurred while creating a user profile for {user.email}: {e}")

        return user

# --- This is the new formset for managing Godparents ---
class GodparentForm(forms.ModelForm):
    class Meta:
        model = Godparent
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': _("Godparent's name")})
        }

GodparentFormSet = inlineformset_factory(
    Event,
    Godparent,
    form=GodparentForm,
    extra=1,
    can_delete=True,
    can_delete_extra=True
)

class ScheduleItemForm(forms.ModelForm):
    class Meta:
        model = ScheduleItem
        fields = ['time', 'activity_type', 'location', 'description']
        widgets = {
            'time': forms.TimeInput(attrs={'type': 'time', 'class': INPUT_CLASSES}),
            'activity_type': forms.Select(attrs={'class': INPUT_CLASSES}),
            'location': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': _('e.g. Town Hall, Main Church')}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 2, 'placeholder': _('Optional details...')}),
        }

ScheduleItemFormSet = inlineformset_factory(
    Event, ScheduleItem,
    form=ScheduleItemForm,
    extra=1,
    can_delete=True
)