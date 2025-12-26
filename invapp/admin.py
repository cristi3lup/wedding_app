from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Event, Godparent, Guest, RSVP, Table, TableAssignment, CardDesign, Plan, UserProfile, SpecialField, ScheduleItem, FAQ, Testimonial
from .forms import TableAssignmentAdminForm
from import_export.admin import ImportExportModelAdmin
from import_export import resources

# --- ADD THIS INLINE CLASS ---
class GodparentInline(admin.TabularInline):
    model = Godparent
    extra = 1

# --- NEW: Schedule Item Inline ---
class ScheduleItemInline(admin.TabularInline):
    model = ScheduleItem
    extra = 1
    ordering = ('time',)

# --- Inlines for the Event Detail Page ---
class TableInline(admin.TabularInline):
    model = Table
    extra = 1

class TableAssignmentInline(admin.TabularInline):
    model = TableAssignment
    form = TableAssignmentAdminForm
    extra = 0
    autocomplete_fields = ['guest', 'table']

# --- Main Admin Classes ---
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'event_date', 'venue_name', 'view_guests_link')
    search_fields = ('title', 'venue_name', 'owner__username')
    list_filter = ('event_date',)
    # Added ScheduleItemInline here
    inlines = [TableInline, TableAssignmentInline, GodparentInline, ScheduleItemInline]

    @admin.display(description='Guests')
    def view_guests_link(self, obj):
        count = obj.guests.count()
        url = reverse('admin:invapp_guest_changelist') + f'?event__id__exact={obj.id}'
        return format_html('<a href="{}">{} Guests</a>', url, count)

# ... [Rest of the admin.py remains the same] ...
@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ('honorific', 'name', 'event', 'email', 'get_rsvp_status', 'get_assigned_table')
    search_fields = ('name', 'email', 'event__title')
    list_filter = ('event',)
    readonly_fields = ('unique_id',)

    @admin.display(description='RSVP Status')
    def get_rsvp_status(self, obj):
        try:
            rsvp = obj.rsvp_details
            if rsvp.attending is True: return f"Yes ({rsvp.number_attending or '?'})"
            elif rsvp.attending is False: return "No"
        except (RSVP.DoesNotExist, AttributeError): pass
        return "No Response"

    @admin.display(description='Assigned Table')
    def get_assigned_table(self, obj):
        try:
            return obj.tableassignment.table.name
        except (TableAssignment.DoesNotExist, AttributeError):
            return "Not Assigned"

@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'capacity')
    search_fields = ('name', 'event__title')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_user_email', 'plan', 'get_event_count')
    list_filter = ('plan',)
    search_fields = ('user__username', 'user__email')
    list_select_related = ('user', 'plan')
    list_editable = ('plan',)

    @admin.display(description='Email Address', ordering='user__email')
    def get_user_email(self, obj):
        return obj.user.email

    @admin.display(description='Events Created')
    def get_event_count(self, obj):
        return Event.objects.filter(owner=obj.user).count()

admin.site.register(RSVP)
@admin.register(TableAssignment)
class TableAssignmentAdmin(admin.ModelAdmin):
    form = TableAssignmentAdminForm
    list_display = ('guest', 'table', 'get_event_title')
    list_filter = ('event', 'table')
    autocomplete_fields = ['guest', 'table']
    search_fields = ('guest__name', 'table__name', 'event__title')

    @admin.display(description='Event', ordering='event__title')
    def get_event_title(self, obj):
        if obj.event: return obj.event.title
        return "—"

@admin.register(SpecialField)
class SpecialFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(CardDesign)
class CardDesignAdmin(admin.ModelAdmin):
    # UPDATED: Added 'display_plans' to the list
    list_display = ('name', 'event_type', 'priority', 'is_multilanguage', 'display_plans', 'display_special_fields')

    list_editable = ('priority', 'is_multilanguage',)
    list_filter = ('event_type', 'available_on_plans', 'is_multilanguage')
    search_fields = ('name', 'template_name')
    filter_horizontal = ('available_on_plans', 'special_fields')

    @admin.display(description='Special Fields')
    def display_special_fields(self, obj):
        return ", ".join([field.name for field in obj.special_fields.all()])

    # NEW METHOD: Shows which plans have access to this design
    @admin.display(description='Available Plans')
    def display_plans(self, obj):
        return ", ".join([plan.name for plan in obj.available_on_plans.all()])

    @admin.display(description='Special Fields')
    def display_special_fields(self, obj):
        return ", ".join([field.name for field in obj.special_fields.all()])

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'max_events', 'featured', 'is_public', 'stripe_price_id')
    list_editable = ('price', 'max_events', 'featured', 'is_public')


from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

# ... (restul importurilor și codului tău existent rămân neschimbate) ...

# 1. Dezînregistrăm Admin-ul standard pentru User
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


# 2. Creăm propria noastră versiune care afișează coloana 'is_active'
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # Definim ce coloane apar în listă
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_active',  # <--- Asta este coloana pe care o dorești (Activ/Inactiv)
        'is_staff',  # Stare de autorizare (Admin Access)
        'date_joined'
    )

    # Adăugăm filtre în dreapta pentru a găsi rapid userii inactivi
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')

    # Permitem căutarea după email și nume
    search_fields = ('username', 'first_name', 'last_name', 'email')

    # Ordonare implicită (cei mai noi sus)
    ordering = ('-date_joined',)


class FAQResource(resources.ModelResource):
    class Meta:
        model = FAQ
        # Definim ordinea coloanelor în Excel
        fields = ('id', 'question', 'answer', 'question_en', 'answer_en', 'order', 'is_visible')
        import_id_fields = ('id',)  # Folosim ID pentru a face update la întrebări existente


# 2. Actualizăm Admin-ul FAQ să folosească ImportExport
@admin.register(FAQ)
class FAQAdmin(ImportExportModelAdmin):
    resource_class = FAQResource  # <--- Conectăm resursa definită mai sus

    list_display = ('question', 'question_en', 'order', 'is_visible')
    list_editable = ('order', 'is_visible')
    list_filter = ('is_visible',)
    search_fields = ('question', 'question_en')
    ordering = ('order', )

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    # Coloanele pe care le vezi în tabel
    list_display = ('client_name', 'rating', 'created_at', 'is_active', 'is_featured')

    # CRITIC: Aici permiți selectarea pentru Landing Page direct din listă
    list_editable = ('is_active', 'is_featured')

    # Filtre în dreapta pentru a găsi rapid review-urile de 5 stele
    list_filter = ('rating', 'is_featured', 'is_active')

    search_fields = ('client_name', 'text')

    ordering = ('-created_at',)