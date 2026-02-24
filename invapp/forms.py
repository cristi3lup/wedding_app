# invapp/forms.py
import re
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import RSVP, Guest, TableAssignment, Table, Event, Godparent, ScheduleItem, GalleryImage
from .models import CardDesign
from django import forms
from django.db.models import Q
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from django.conf import settings

from allauth.account.forms import SignupForm
from django.urls import reverse_lazy
from .models import Guest, Testimonial

INPUT_CLASSES = "block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 bg-white dark:bg-slate-900 dark:text-white dark:ring-slate-700"
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
        self.guest = kwargs.pop('guest', None)
        super().__init__(*args, **kwargs)

    def clean_number_attending(self):
        number = self.cleaned_data.get('number_attending')
        if number and self.guest and number > self.guest.max_attendees:
            raise forms.ValidationError(
                _("Value must be less than or equal to %(max)s, please contact event host.") % {'max': self.guest.max_attendees}
            )
        return number

class TableAssignmentAdminForm(forms.ModelForm):
    class Meta:
        model = TableAssignment
        fields = '__all__'

    def clean_guest(self):
        guest = self.cleaned_data.get('guest')
        if guest:
            try:
                if not guest.rsvp_details.attending:
                    raise forms.ValidationError(_("Invalid choice: This guest has not RSVP'd Yes."))
            except RSVP.DoesNotExist:
                raise forms.ValidationError(_("Invalid choice: This guest has not RSVP'd."))
        return guest

class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ['name', 'capacity']
        labels = {
            'name': _('Table Name or Number'),
            'capacity': _('Capacity (Number of Seats)'),
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'capacity': forms.NumberInput(attrs={'class': INPUT_CLASSES}),
        }

class AssignGuestForm(forms.Form):
    guest = forms.ModelChoiceField(queryset=Guest.objects.none(), label=_("Assign Guest"))
    table = forms.ModelChoiceField(queryset=Table.objects.none(), label=_("To Table"))

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

        if event:
            assigned_guest_ids = TableAssignment.objects.filter(table__event=event).values_list('guest_id', flat=True)
            self.fields['guest'].queryset = Guest.objects.filter(
                event=event,
                rsvp_details__attending=True
            ).exclude(
                id__in=assigned_guest_ids
            )
            self.fields['table'].queryset = Table.objects.filter(event=event)

            def clean(self):
                cleaned_data = super().clean()
                guest = cleaned_data.get('Assign Guest')
                table = cleaned_data.get('To Table')

                if guest and table:
                    guest_actual_attendees = guest.attending_count
                    if table.remaining_capacity < guest_actual_attendees:
                        error_message = ngettext_lazy(
                            "Not enough capacity at {table_name}. "
                            "Needs {needed_seats} seat for {guest_name}, "
                            "but only {available_seats} seat(s) are available.",
                            "Not enough capacity at {table_name}. "
                            "Needs {needed_seats} seats for {guest_name}, "
                            "but only {available_seats} seat(s) are available.",
                            guest_actual_attendees
                        )
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
    event_date = forms.DateTimeField(
        input_formats=['%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'],
        widget=forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'DD/MM/YYYY'})
    )

    class Meta:
        model = Event
        fields = [
            'event_type', 'title', 'event_date', 'party_time', 'venue_name', 'venue_address',
            'bride_name', 'groom_name', 'bride_parents', 'groom_parents',
            'child_name', 'parents_names',
            'ceremony_maps_url', 'party_maps_url', 'calendar_description',
            'ceremony_time', 'ceremony_location', 'ceremony_address',
            'invitation_wording', 'schedule_details', 'other_info',
            'couple_photo',
            'landscape_photo',
            'selected_design',
            'main_invitation_image', 'audio_greeting',
        ]

        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'party_time': forms.TimeInput(
                format='%H:%M',
                attrs={'type': 'time', 'class': INPUT_CLASSES}
            ),
            'venue_name': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'venue_address': forms.TextInput(attrs={'class': INPUT_CLASSES}),
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
            'ceremony_location': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. St. Nicholas Church'}),
            'ceremony_address': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Physical Address'}),
            'invitation_wording': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 5}),
            'schedule_details': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 4}),
            'other_info': forms.Textarea(attrs={'class': INPUT_CLASSES, 'rows': 4}),
            'selected_design': forms.RadioSelect(),
        }

    def clean_map_url(self, field_name):
        data = self.cleaned_data.get(field_name)
        if not data:
            return data

        # Only extract src if it's a full iframe tag
        if data.strip().startswith('<iframe') and 'src="' in data:
            match = re.search(r'src="([^"]+)"', data)
            if match:
                return match.group(1)
        
        # Otherwise, assume it's already a direct URL or a short link
        return data.strip()

    def clean_ceremony_maps_url(self):
        return self.clean_map_url('ceremony_maps_url')

    def clean_party_maps_url(self):
        return self.clean_map_url('party_maps_url')


class GuestForm(forms.ModelForm):
    class Meta:
        model = Guest
        fields = [
            'honorific',
            'name',
            'preferred_language',
            'phone_number',
            'email',
            'max_attendees',
            'invitation_method',
        ]
        labels = {
            'honorific': _("Courtesy Title"),
            'name': _("Guest/Group Name (e.g., 'The Smith Family', 'John Doe')"),
            'preferred_language': _("Invitation Language"),
            'phone_number': _('Phone Number (Optional)'),
            'email': _('Email Address (Optional)'),
            'max_attendees': _('Max Number of People Invited (including guest)'),
            'invitation_method': _('Invitation Method (Digital or Paper)'),
        }
        help_texts = {
            'max_attendees': _('Enter the total number of people this invitation covers (e.g., 2 for a couple).'),
            'name': _('Full name of the primary guest or couple/family name.'),
            'email': _('Primary email for the invitation.'),
        }
        widgets = {
            'honorific': forms.Select(attrs={'class': INPUT_CLASSES}),
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES_WITH_ICON, 'placeholder': 'John Doe'}),
            'preferred_language': forms.Select(attrs={'class': INPUT_CLASSES}),
            'phone_number': forms.TextInput(attrs={'class': INPUT_CLASSES_WITH_ICON, 'placeholder': '+40...'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASSES_WITH_ICON, 'placeholder': 'john@example.com'}),
            'max_attendees': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'min': '1', 'value': '1'}),
            'invitation_method': forms.Select(attrs={'class': INPUT_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial['preferred_language'] = 'ro'
            self.initial['invitation_method'] = 'digital'

class GuestCreateForm(GuestForm):
    class Meta(GuestForm.Meta):
        fields = [
            'honorific',
            'name',
            'preferred_language',
            'phone_number',
            'email',
            'max_attendees',
            'invitation_method',
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
            assigned_guest_ids = TableAssignment.objects.filter(
                table__event=event
            ).values_list('guest_id', flat=True)

            attending_guests = Guest.objects.filter(
                Q(event=event) & (
                        Q(manual_is_attending=True) |
                        (Q(manual_is_attending__isnull=True) & Q(rsvp_details__attending=True))
                )
            )

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
                               _("Not enough capacity at %(table)s. Assigning these guests requires %(needed)d seat(s), but only %(available)d seat(s) are available.") % {
                                   'table': table.name,
                                   'needed': total_new_attendees,
                                   'available': table.remaining_capacity
                               })
        return cleaned_data

class GuestContactForm(forms.ModelForm):
    """
    Form for guests to provide contact info after RSVP.
    """
    class Meta:
        model = Guest
        fields = ['email', 'phone_number']
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': 'your.email@example.com',
                'class': INPUT_CLASSES_WITH_ICON
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': '+40712345678',
                'class': INPUT_CLASSES_WITH_ICON
            }),
        }

class CustomSignupForm(SignupForm):
    terms_agreement = forms.BooleanField(required=True)

    def __init__(self, *args, **kwargs):
        super(CustomSignupForm, self).__init__(*args, **kwargs)
        self.fields['terms_agreement'].label = format_html(
            _('I agree to the <a href="{}" target="_blank" class="text-indigo-600 hover:underline">Terms and Conditions</a> and <a href="{}" target="_blank" class="text-indigo-600 hover:underline">Privacy Policy</a>.'),
            reverse_lazy('invapp:terms_and_conditions'),
            reverse_lazy('invapp:privacy_policy')
        )

    def save(self, request):
        user = super(CustomSignupForm, self).save(request)
        try:
            free_plan = Plan.objects.get(price=0)
            UserProfile.objects.create(user=user, plan=free_plan)
        except Plan.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error creating profile: {e}")
        return user

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


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ['rating', 'text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': INPUT_CLASSES,
                'rows': 4,
                'placeholder': _('Tell us what you think (optional)...')
            }),
            'rating': forms.HiddenInput()
        }

class GalleryImageForm(forms.ModelForm):
    class Meta:
        model = GalleryImage
        fields = ['image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={
                'class': 'block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-rose-50 file:text-rose-700 hover:file:bg-rose-100'
            })
        }

GalleryImageFormSet = inlineformset_factory(
    Event,
    GalleryImage,
    form=GalleryImageForm,
    fields=['image'],
    extra=1,
    max_num=6,
    validate_max=True,
    can_delete=True
)