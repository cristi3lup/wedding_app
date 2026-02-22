from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from import_export import resources


from .models import (
    Event,
    Godparent,
    Guest,
    RSVP,
    Table,
    TableAssignment,
    CardDesign,
    Plan,
    UserProfile,
    SpecialField,
    ScheduleItem,
    FAQ,
    Testimonial,
    SiteImage,
    AboutSection,
    FutureFeature,
    PlanFeature,
    GalleryImage,
)
from .forms import TableAssignmentAdminForm


# ==========================================
# === 0. RESOURCES (Import/Export)       ===
# ==========================================

class GuestResource(resources.ModelResource):
    class Meta:
        model = Guest
        fields = ('id', 'name', 'email', 'phone_number', 'honorific', 'max_attendees', 'event__title', 'invitation_method', 'preferred_language')
        export_order = ('id', 'name', 'email', 'phone_number', 'honorific', 'max_attendees', 'event__title', 'invitation_method', 'preferred_language')

class EventResource(resources.ModelResource):
    class Meta:
        model = Event
        fields = ('id', 'title', 'owner__username', 'event_type', 'event_date', 'venue_name', 'venue_address')
        export_order = ('id', 'title', 'owner__username', 'event_type', 'event_date', 'venue_name', 'venue_address')

class PlanResource(resources.ModelResource):
    class Meta:
        model = Plan
        fields = ('id', 'name', 'price', 'max_guests', 'max_events', 'stripe_price_id', 'is_public')

class CardDesignResource(resources.ModelResource):
    class Meta:
        model = CardDesign
        fields = ('id', 'name', 'event_type', 'template_name', 'priority', 'is_active', 'is_public')

# ==========================================
# === 1. INLINES (Secondary Tables)      ===
# ==========================================

class GodparentInline(admin.TabularInline):
    model = Godparent
    extra = 1


class ScheduleItemInline(admin.TabularInline):
    model = ScheduleItem
    extra = 1
    ordering = ('time',)


class TableInline(admin.TabularInline):
    model = Table
    extra = 1


class TableAssignmentInline(admin.TabularInline):
    model = TableAssignment
    form = TableAssignmentAdminForm
    extra = 0
    autocomplete_fields = ['guest', 'table']


# ==========================================
# === 2. EVENT MANAGEMENT                ===
# ==========================================
class GalleryImageInline(admin.TabularInline):
    model = GalleryImage
    extra = 1
    max_num = 6
    verbose_name = "Gallery Image"
    verbose_name_plural = "Photo Gallery (Max 6 images)"

@admin.register(Event)
class EventAdmin(ImportExportModelAdmin):
    resource_class = EventResource
    list_display = ('title', 'owner', 'event_date', 'venue_name', 'view_guests_link')
    search_fields = ('title', 'venue_name', 'owner__username', 'owner__email')
    list_filter = ('event_type', 'event_date')
    inlines = [TableInline, TableAssignmentInline, GodparentInline, ScheduleItemInline, GalleryImageInline]

    @admin.display(description='Guests')
    def view_guests_link(self, obj):
        count = obj.guests.count()
        url = reverse('admin:invapp_guest_changelist') + f'?event__id__exact={obj.id}'
        return format_html('<a href="{}">{} Guests</a>', url, count)



@admin.register(Guest)
class GuestAdmin(ImportExportModelAdmin):
    resource_class = GuestResource
    list_display = ('honorific', 'name', 'event', 'preferred_language', 'get_rsvp_status', 'get_assigned_table')
    search_fields = ('name', 'email', 'event__title')
    list_filter = ('event', 'preferred_language')
    readonly_fields = ('unique_id',)

    @admin.display(description='RSVP Status')
    def get_rsvp_status(self, obj):
        try:
            rsvp = obj.rsvp_details
            if rsvp.attending is True:
                return f"Yes ({rsvp.number_attending or '?'})"
            elif rsvp.attending is False:
                return "No"
        except (RSVP.DoesNotExist, AttributeError):
            pass
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


admin.site.register(RSVP)

# ==========================================
# === 3. USER MANAGEMENT                 ===
# ==========================================

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'is_active',
        'is_staff',
        'date_joined'
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)


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


# ==========================================
# === 4. DESIGN SYSTEM & PLANS           ===
# ==========================================

@admin.register(SpecialField)
class SpecialFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(CardDesign)
class CardDesignAdmin(ImportExportModelAdmin):
    resource_class = CardDesignResource
    list_display = ('name', 'event_type', 'show_preview_icon', 'is_active', 'is_public', 'priority', 'display_plans')
    list_editable = ('priority', 'is_active', 'is_public')
    list_filter = ('event_type', 'is_active', 'is_public', 'available_on_plans')
    search_fields = ('name', 'template_name')
    filter_horizontal = ('available_on_plans', 'special_fields')

    fields = (
        'name',
        'description',
        'event_type',
        'preview_image',
        'show_large_preview',
        'preview_image_path',
        'template_name',
        'special_fields',
        'available_on_plans',
        'is_multilanguage',
        'is_active',
        'is_public',
        'priority'
    )

    readonly_fields = ('show_large_preview',)

    def show_preview_icon(self, obj):
        if obj.preview_image:
            return format_html(
                '<img src="{}" style="height: 50px; width: auto; border-radius: 4px; box-shadow: 0 0 2px #ccc;" />',
                obj.preview_image.url
            )
        return "-"
    show_preview_icon.short_description = "Preview"

    def show_large_preview(self, obj):
        if obj.preview_image:
            return format_html(
                '<img src="{}" style="max-height: 300px; max-width: 100%; border-radius: 8px;" />',
                obj.preview_image.url
            )
        return "No image uploaded"
    show_large_preview.short_description = "Current Image Preview"

    @admin.display(description='Available Plans')
    def display_plans(self, obj):
        return ", ".join([plan.name for plan in obj.available_on_plans.all()])

    @admin.display(description='Special Fields')
    def display_special_fields(self, obj):
        return ", ".join([field.name for field in obj.special_fields.all()])


class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 0
    fields = ('order', 'text_ro', 'text_en', 'is_included')
    ordering = ('order',)


@admin.register(Plan)
class PlanAdmin(ImportExportModelAdmin):
    resource_class = PlanResource
    list_display = ('name', 'price','show_watermark', 'max_guests', 'max_events', 'stripe_price_id', 'is_public')
    list_editable = ('price', 'max_guests', 'max_events', 'is_public','show_watermark')
    search_fields = ('name',)
    inlines = [PlanFeatureInline]

    fieldsets = (
        ('General Information', {
            'fields': ('name', 'price', 'description', 'stripe_price_id')
        }),
        ('Limitations', {
            'fields': ('max_guests', 'max_events', 'lock_event_on_creation'),
            'description': "Set technical limits for this plan."
        }),
        ('Visual & Public', {
            'fields': ('featured', 'is_public', 'icon_svg_path', 'color_class')
        }),
        ('Legacy Settings', {
            'classes': ('collapse',),
            'fields': ('has_table_assignment', 'can_upload_own_design', 'show_watermark'),
        }),
    )


@admin.register(SiteImage)
class SiteImageAdmin(admin.ModelAdmin):
    list_display = ('key', 'description', 'image')
    search_fields = ('key', 'description')


# ==========================================
# === 5. MARKETING (FAQ & Reviews)       ===
# ==========================================

class FAQResource(resources.ModelResource):
    class Meta:
        model = FAQ
        fields = ('id', 'question', 'answer', 'question_ro', 'answer_ro', 'order', 'is_visible')
        import_id_fields = ('id',)


@admin.register(FAQ)
class FAQAdmin(ImportExportModelAdmin):
    resource_class = FAQResource
    list_display = ('question', 'question_ro', 'order', 'is_visible')
    list_editable = ('order', 'is_visible')
    list_filter = ('is_visible',)
    search_fields = ('question', 'question_ro')
    ordering = ('order',)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'social_provider', 'social_provider_badge', 'rating', 'created_at', 'is_active')
    list_filter = ('social_provider', 'is_active', 'rating')
    search_fields = ('client_name', 'content')
    list_editable = ('is_active', 'social_provider')

    def social_provider_badge(self, obj):
        if obj.social_provider == 'facebook':
            return "🔵 Facebook"
        elif obj.social_provider == 'google':
            return "🔴 Google"
        return "✉️ Email"

    social_provider_badge.short_description = 'Badge'


@admin.register(AboutSection)
class AboutSectionAdmin(admin.ModelAdmin):
    list_display = ('title_en', 'title_ro', 'is_active')


class FutureFeatureResource(resources.ModelResource):
    class Meta:
        model = FutureFeature
        fields = ('id', 'title_en', 'description_en', 'title_ro', 'description_ro', 'target_date', 'priority', 'is_public', 'icon_svg_path', 'color_class')
        export_order = ('id', 'title_en', 'description_en', 'title_ro', 'description_ro', 'target_date', 'priority', 'is_public', 'icon_svg_path', 'color_class')

@admin.register(FutureFeature)
class FutureFeatureAdmin(ImportExportModelAdmin):
    resource_class = FutureFeatureResource
    list_display = ('title_en', 'target_date', 'priority', 'is_public')
    list_editable = ('priority', 'is_public')
