from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.urls import reverse, path
from django.utils.html import format_html
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _, gettext as __
from import_export.admin import ImportExportModelAdmin
from import_export import resources
import csv
import uuid
import urllib.parse
from datetime import timedelta

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
    Voucher,
    MarketingCampaign,
    PlatformPartner,
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


class GalleryImageInline(admin.TabularInline):
    model = GalleryImage
    extra = 1
    max_num = 6
    verbose_name = _("Gallery Image")
    verbose_name_plural = _("Photo Gallery (Max 6 images)")


# ==========================================
# === 2. EVENT MANAGEMENT                ===
# ==========================================

@admin.register(Event)
class EventAdmin(ImportExportModelAdmin):
    resource_class = EventResource
    list_display = ('title', 'owner', 'event_date', 'venue_name', 'host_whatsapp', 'view_guests_link')
    search_fields = ('title', 'venue_name', 'owner__username', 'owner__email', 'host_whatsapp')
    list_filter = ('event_type', 'event_date')
    inlines = [TableInline, TableAssignmentInline, GodparentInline, ScheduleItemInline, GalleryImageInline]

    @admin.display(description=_('Guests'))
    def view_guests_link(self, obj):
        count = obj.guests.count()
        url = reverse('admin:invapp_guest_changelist') + f'?event__id__exact={obj.id}'
        return format_html('<a href="{}">{} {}</a>', url, count, _('Guests'))



@admin.register(Guest)
class GuestAdmin(ImportExportModelAdmin):
    resource_class = GuestResource
    list_display = ('honorific', 'name', 'event', 'preferred_language', 'get_rsvp_status', 'get_assigned_table')
    search_fields = ('name', 'email', 'event__title')
    list_filter = ('event', 'preferred_language')
    readonly_fields = ('unique_id',)

    @admin.display(description=_('RSVP Status'))
    def get_rsvp_status(self, obj):
        try:
            rsvp = obj.rsvp_details
            if rsvp.attending is True:
                return f"{_('Yes')} ({rsvp.number_attending or '?'})"
            elif rsvp.attending is False:
                return _("No")
        except (RSVP.DoesNotExist, AttributeError):
            pass
        return _("No Response")

    @admin.display(description=_('Assigned Table'))
    def get_assigned_table(self, obj):
        try:
            return obj.tableassignment.table.name
        except (TableAssignment.DoesNotExist, AttributeError):
            return _("Not Assigned")


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

    @admin.display(description=_('Event'), ordering='event__title')
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

    @admin.display(description=_('Email Address'), ordering='user__email')
    def get_user_email(self, obj):
        return obj.user.email

    @admin.display(description=_('Events Created'))
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
    show_preview_icon.short_description = _("Preview")

    def show_large_preview(self, obj):
        if obj.preview_image:
            return format_html(
                '<img src="{}" style="max-height: 300px; max-width: 100%; border-radius: 8px;" />',
                obj.preview_image.url
            )
        return _("No image uploaded")
    show_large_preview.short_description = _("Current Image Preview")

    @admin.display(description=_('Available Plans'))
    def display_plans(self, obj):
        return ", ".join([plan.name for plan in obj.available_on_plans.all()])

    @admin.display(description=_('Special Fields'))
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
        (_('General Information'), {
            'fields': ('name', 'price', 'description', 'stripe_price_id')
        }),
        (_('Limitations'), {
            'fields': ('max_guests', 'max_events', 'lock_event_on_creation'),
            'description': _("Set technical limits for this plan.")
        }),
        (_('Visual & Public'), {
            'fields': ('featured', 'is_public', 'icon_svg_path', 'color_class')
        }),
        (_('Legacy Settings'), {
            'classes': ('collapse',),
            'fields': ('has_table_assignment', 'can_upload_own_design', 'show_watermark'),
        }),
    )


@admin.register(SiteImage)
class SiteImageAdmin(admin.ModelAdmin):
    list_display = ('key', 'description', 'image')
    search_fields = ('key', 'description')


# ==========================================
# === 5. MARKETING & VOUCHERS            ===
# ==========================================

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ('code', 'campaign_name', 'discount_percentage', 'is_used', 'valid_from', 'valid_until')
    list_editable = ('campaign_name',)
    search_fields = ('code', 'used_by', 'campaign_name')
    list_filter = ('is_used', 'campaign_name', 'valid_from', 'valid_until', 'discount_percentage')
    readonly_fields = ('created_at', 'used_at')
    fields = ('code', 'campaign_name', 'discount_percentage', 'active', 'max_uses', 'current_uses', 'is_used', 'used_by', 'used_at', 'valid_from', 'valid_until', 'applicable_plans', 'custom_message')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('generate-bulk/', self.admin_site.admin_view(self.generate_bulk_view), name='invapp_voucher_generate_bulk'),
        ]
        return custom_urls + urls

    def generate_bulk_view(self, request):
        if request.method == 'POST':
            try:
                count = int(request.POST.get('count', 50))
                campaign = request.POST.get('campaign', 'General Admin')
                days_valid = int(request.POST.get('days_valid', 30))
                discount = int(request.POST.get('discount', 100))
                selected_plan_ids = request.POST.getlist('applicable_plans')
                custom_message = request.POST.get('custom_message', '')
                
                # Handle optional start date
                start_date_str = request.POST.get('valid_from')
                if start_date_str:
                    valid_from = timezone.datetime.fromisoformat(start_date_str)
                    if not timezone.is_aware(valid_from):
                        valid_from = timezone.make_aware(valid_from)
                else:
                    valid_from = timezone.now()

                valid_until = valid_from + timedelta(days=days_valid)
                vouchers_to_create = []
                codes = []

                for i in range(count):
                    code = f"TARG-{uuid.uuid4().hex[:4].upper()}"
                    while code in codes:
                        code = f"TARG-{uuid.uuid4().hex[:4].upper()}"
                    codes.append(code)
                    
                    vouchers_to_create.append(Voucher(
                        code=code,
                        discount_percentage=discount,
                        campaign_name=campaign,
                        valid_from=valid_from,
                        valid_until=valid_until,
                        active=True,
                        max_uses=1,
                        custom_message=custom_message
                    ))

                from django.db import transaction
                with transaction.atomic():
                    Voucher.objects.bulk_create(vouchers_to_create)
                    created_vouchers = Voucher.objects.filter(code__in=codes)
                    if selected_plan_ids:
                        for v in created_vouchers:
                            v.applicable_plans.set(selected_plan_ids)

                safe_campaign = slugify(campaign) if campaign else "direct_sale"
                base_domain = "https://invapp-romania.ro/ro/accounts/signup/"
                
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="vouchers_{safe_campaign}.csv"'
                response.write(u'\ufeff'.encode('utf8'))
                
                writer = csv.writer(response)
                writer.writerow([
                    __('Code'), __('Campaign'), __ ('Discount %'), 
                    __('Valid From'), __('Valid Until'), __('Plans'), 
                    __('Activation Link (Client)'), __('Send via WhatsApp')
                ])
                
                plan_names = __("All")
                if selected_plan_ids:
                    plan_names = ", ".join(Plan.objects.filter(id__in=selected_plan_ids).values_list('name', flat=True))

                for v in created_vouchers:
                    activation_url = f"{base_domain}?v={v.code}&utm_source=whatsapp&utm_medium=direct_message&utm_campaign={safe_campaign}"
                    open_link_text = __("Open Link")
                    activation_formula = f'=HYPERLINK("{activation_url}", "{open_link_text}")'
                    
                    # Use custom message if provided, otherwise fallback to default
                    if v.custom_message:
                        wa_text = f"{v.custom_message}\n\n{activation_url}"
                    else:
                        wa_text = __("Hi! 🥂 We're happy we reached an agreement for your event decor! As promised, here is your link to activate the InvApp platform (Free). Click here to create your account: %(url)s") % {'url': activation_url}
                    
                    encoded_wa_text = urllib.parse.quote(wa_text)
                    wa_link = f"https://wa.me/?text={encoded_wa_text}"
                    send_wa_text = __("SEND VIA WHATSAPP ➔")
                    wa_formula = f'=HYPERLINK("{wa_link}", "{send_wa_text}")'
                    
                    writer.writerow([
                        v.code, v.campaign_name, v.discount_percentage, 
                        v.valid_from.strftime('%Y-%m-%d %H:%M'),
                        v.valid_until.strftime('%Y-%m-%d %H:%M'), 
                        plan_names, activation_formula, wa_formula
                    ])
                return response

            except Exception as e:
                error_msg = __("Error: %(error)s") % {'error': str(e)}
                self.message_user(request, error_msg, level=messages.ERROR)
                return redirect("..")

        context = dict(
            self.admin_site.each_context(request),
            title=__("Generate Bulk Vouchers"),
            opts=self.model._meta,
            available_plans=Plan.objects.all().order_by('price'),
        )
        return render(request, "admin/invapp/voucher/generate_bulk.html", context)


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'partner', 'is_active', 'show_urgency_bar', 'countdown_end_date')
    list_editable = ('is_active',)
    search_fields = ('name',)


@admin.register(PlatformPartner)
class PlatformPartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'whatsapp_number', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name', 'whatsapp_number')


# ==========================================
# === 6. FAQ & REVIEWS                   ===
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
    list_display = ('client_name', 'social_provider', 'rating', 'created_at', 'is_active')
    list_filter = ('social_provider', 'is_active', 'rating')
    search_fields = ('client_name',)
    list_editable = ('is_active',)


@admin.register(AboutSection)
class AboutSectionAdmin(admin.ModelAdmin):
    list_display = ('title_en', 'title_ro', 'is_active')


@admin.register(FutureFeature)
class FutureFeatureAdmin(ImportExportModelAdmin):
    list_display = ('title_en', 'target_date', 'priority', 'is_public')
    list_editable = ('priority', 'is_public')
