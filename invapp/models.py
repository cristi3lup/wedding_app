import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.utils.text import format_lazy
from django.utils.translation import get_language
from django.core.exceptions import ValidationError
from cloudinary.models import CloudinaryField
from cloudinary_storage.storage import RawMediaCloudinaryStorage


class SiteImage(models.Model):
    KEY_CHOICES = [
        ('hero_bg', _('Hero Background (Landing)')),
        ('global_bg', _('Global Site Background')),
        ('logo_main', _('Primary Logo')),
        ('feature_1', _('Feature Image 1')),
        ('feature_2', _('Feature Image 2')),
        ('feature_3', _('Feature Image 3')),
        ('cta_bg', _('Call to Action Background')),
        ('partner_promo', _('Partner Promotion (Culori)')),
    ]
    key = models.CharField(max_length=50, choices=KEY_CHOICES, unique=True)
    image = models.ImageField(upload_to='site_assets/')
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.get_key_display()


class Plan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True)
    max_guests = models.PositiveIntegerField(default=0)
    max_events = models.PositiveIntegerField(default=1)
    is_public = models.BooleanField(default=True)
    has_table_assignment = models.BooleanField(default=False)
    can_upload_own_design = models.BooleanField(default=False)
    show_watermark = models.BooleanField(default=True, verbose_name=_("Show Watermark"))
    icon_svg_path = models.TextField(blank=True)
    color_class = models.CharField(max_length=50, blank=True)
    featured = models.BooleanField(default=False)
    lock_event_on_creation = models.BooleanField(default=False)
    stripe_price_id = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name


class PlanFeature(models.Model):
    plan = models.ForeignKey(Plan, related_name='features', on_delete=models.CASCADE)
    text_ro = models.CharField(max_length=255, verbose_name=_("Feature Text (RO)"))
    text_en = models.CharField(max_length=255, verbose_name=_("Feature Text (EN)"), blank=True)
    is_included = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = _("Plan Feature")
        verbose_name_plural = _("Plan Features")

    @property
    def text(self):
        if get_language() == 'ro':
            return self.text_ro
        return self.text_en or self.text_ro

    def __str__(self):
        return self.text_ro


class PlatformPartner(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Partner Name"))
    whatsapp_number = models.CharField(max_length=20, verbose_name=_("WhatsApp Number"))
    facebook_url = models.URLField(blank=True, verbose_name=_("Facebook URL"))
    instagram_url = models.URLField(blank=True, verbose_name=_("Instagram URL"))
    website_url = models.URLField(blank=True, verbose_name=_("Website URL"))
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Platform Partner")
        verbose_name_plural = _("Platform Partners")


class MarketingCampaign(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=False)
    partner = models.ForeignKey(PlatformPartner, on_delete=models.SET_NULL, null=True, blank=True)
    show_urgency_bar = models.BooleanField(default=False)
    urgency_text = models.CharField(max_length=255, blank=True)
    countdown_end_date = models.DateTimeField(null=True, blank=True)
    hero_headline = models.CharField(max_length=200)
    hero_subheadline = models.TextField(blank=True)
    primary_button_text = models.CharField(max_length=50, default=_("Start Now"))
    primary_button_link = models.CharField(max_length=200, default="/ro/accounts/signup/")
    theme_color_hex = models.CharField(max_length=7, default="#4f46e5")

    def save(self, *args, **kwargs):
        if self.is_active:
            MarketingCampaign.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Marketing Campaign")
        verbose_name_plural = _("Marketing Campaigns")


class Voucher(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount_percentage = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(default=100)
    current_uses = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    used_by = models.CharField(max_length=255, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    campaign_name = models.CharField(max_length=100, blank=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    applicable_plans = models.ManyToManyField(Plan, blank=True)
    custom_message = models.TextField(blank=True, help_text=_("Optional custom message for WhatsApp sharing."))

    def __str__(self):
        return f"{self.code} ({self.discount_percentage}%)"


class SpecialField(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class CardDesign(models.Model):
    class EventTypeChoices(models.TextChoices):
        WEDDING = 'wedding', _('Wedding')
        BAPTISM = 'baptism', _('Baptism')
        IMAGE_UPLOAD = 'image_upload', _('Image Upload Only')

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    preview_image_path = models.CharField(max_length=255, blank=True, null=True)
    preview_image = models.ImageField(upload_to='design_previews/', blank=True, null=True)
    template_name = models.CharField(max_length=255)
    event_type = models.CharField(max_length=20, choices=EventTypeChoices.choices, default=EventTypeChoices.WEDDING)
    available_on_plans = models.ManyToManyField(Plan, blank=True, related_name='card_designs')
    priority = models.PositiveIntegerField(default=0)
    is_multilanguage = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    special_fields = models.ManyToManyField(SpecialField, blank=True, related_name='card_designs')

    def __str__(self):
        return self.name


class Event(models.Model):
    class EventTypeChoices(models.TextChoices):
        WEDDING = 'wedding', _('Wedding')
        BAPTISM = 'baptism', _('Baptism')
        IMAGE_UPLOAD = 'image_upload', _('Image Upload Only')

    event_type = models.CharField(max_length=20, choices=EventTypeChoices.choices, default=EventTypeChoices.WEDDING)
    child_name = models.CharField(max_length=200, blank=True)
    host_whatsapp = models.CharField(max_length=20, blank=True, null=True, help_text=_("Format: 407XXXXXXXX (no '+' or '0' in front)"))
    whatsapp_custom_message = models.CharField(max_length=255, blank=True, null=True, help_text=_("Default pre-filled message for the guest to send to the host."))
    parents_names = models.CharField(max_length=200, blank=True)
    bride_name = models.CharField(max_length=100, blank=True)
    groom_name = models.CharField(max_length=100, blank=True)
    bride_parents = models.CharField(max_length=200, blank=True)
    groom_parents = models.CharField(max_length=200, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='events')
    selected_design = models.ForeignKey(CardDesign, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    title = models.CharField(max_length=200, default=_("Our Wedding"))
    event_date = models.DateTimeField(default=timezone.now)
    party_time = models.TimeField(null=True, blank=True)
    venue_name = models.CharField(max_length=200, blank=True, null=True)
    venue_address = models.TextField(blank=True, null=True)
    ceremony_time = models.TimeField(null=True, blank=True)
    ceremony_location = models.CharField(max_length=255, blank=True)
    ceremony_address = models.TextField(blank=True, null=True)
    ceremony_maps_url = models.URLField(max_length=1000, blank=True, null=True)
    party_maps_url = models.URLField(max_length=1000, blank=True, null=True)
    calendar_description = models.TextField(blank=True, null=True)
    invitation_wording = models.TextField(blank=True, null=True)
    schedule_details = models.TextField(blank=True, null=True)
    other_info = models.TextField(blank=True, null=True)
    main_invitation_image = models.ImageField(upload_to='invitation_images/', null=True, blank=True)
    audio_greeting = models.FileField(upload_to='audio_greetings/', storage=RawMediaCloudinaryStorage(), blank=True, null=True)
    couple_photo = models.ImageField(upload_to='event_photos/', null=True, blank=True)
    landscape_photo = models.ImageField(upload_to='event_landscape_photos/', null=True, blank=True)

    def __str__(self):
        return self.title

    @property
    def get_couple_photo_url(self):
        if hasattr(self, 'preview_couple_photo_b64') and self.preview_couple_photo_b64:
            return self.preview_couple_photo_b64
        if self.couple_photo:
            return self.couple_photo.url
        return None


class GalleryImage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='gallery_images')
    image = CloudinaryField('image', folder='invapp_gallery')

    def save(self, *args, **kwargs):
        if not self.pk and self.event.gallery_images.count() >= 6:
            raise ValidationError(_("The limit of 6 photos for this package has been reached."))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.event}"


class Guest(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='guests')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='guests')
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    max_attendees = models.PositiveIntegerField(default=1)
    phone_number = models.CharField(max_length=30, blank=True, null=True)

    class HonorificChoices(models.TextChoices):
        MR = 'mr', _('Mr.')
        MRS = 'mrs', _('Mrs.')
        MS = 'ms', _('Ms.')
        DR = 'dr', _('Dr.')
        FAMILY = 'family', _('Family')
        COUPLE = 'couple', _('Couple')
        NONE = 'none', _('None')

    honorific = models.CharField(max_length=10, choices=HonorificChoices.choices, default=HonorificChoices.NONE)

    @property
    def get_full_display_name(self):
        if self.honorific == 'family':
            return format_lazy(_('The {name} Family'), name=self.name)
        elif self.honorific == 'couple':
            return format_lazy(_('The {name} Couple'), name=self.name)
        elif self.honorific != 'none':
            return f"{self.get_honorific_display()} {self.name}"
        else:
            return self.name

    class InvitationMethodChoices(models.TextChoices):
        DIGITAL = 'digital', _('Digital')
        PHYSICAL = 'physical', _('On Paper')

    invitation_method = models.CharField(max_length=20, choices=InvitationMethodChoices.choices, default=InvitationMethodChoices.PHYSICAL, blank=True, null=True)

    class RSVPSourceChoices(models.TextChoices):
        AUTOMATIC = 'automatic', _('Automatic (Guest)')
        MANUAL = 'manual', _('Manual (Host)')

    rsvp_source = models.CharField(max_length=20, choices=RSVPSourceChoices.choices, default=RSVPSourceChoices.MANUAL, blank=True, null=True)
    manual_is_attending = models.BooleanField(null=True, blank=True)
    manual_attending_count = models.PositiveIntegerField(null=True, blank=True)
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    preferred_language = models.CharField(max_length=5, choices=settings.LANGUAGES, default='ro')

    @property
    def is_attending(self):
        if self.manual_is_attending is not None:
            return self.manual_is_attending
        try:
            if hasattr(self, 'rsvp_details') and self.rsvp_details.attending is not None:
                return self.rsvp_details.attending
        except Exception:
            pass
        return None

    @property
    def attending_count(self):
        if self.manual_is_attending is not None:
            return self.manual_attending_count if self.manual_is_attending else 0
        try:
            if hasattr(self, 'rsvp_details') and self.rsvp_details.attending:
                return self.rsvp_details.number_attending or 1
        except Exception:
            pass
        return 0

    def __str__(self):
        return self.name


class RSVP(models.Model):
    guest = models.OneToOneField(Guest, on_delete=models.CASCADE, related_name='rsvp_details')
    attending = models.BooleanField(null=True, blank=True, choices=[(True, _('Yes')), (False, _('No'))])
    number_attending = models.PositiveIntegerField(null=True, blank=True)
    meal_preference = models.CharField(max_length=200, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = _("Undecided")
        if self.attending is True:
            status = _("Attending")
        elif self.attending is False:
            status = _("Not Attending")
        return str(format_lazy(_("RSVP for {name} - {status}"), name=self.guest.name, status=status))


class Table(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tables')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tables')
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField(default=8)

    @property
    def current_seated_count(self):
        return sum(assignment.guest.attending_count for assignment in self.assigned_guests.all())

    @property
    def remaining_capacity(self):
        return max(0, self.capacity - self.current_seated_count)

    class Meta:
        unique_together = ('event', 'name')

    def __str__(self):
        return self.name


class TableAssignment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True)
    guest = models.OneToOneField(Guest, on_delete=models.CASCADE)
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='assigned_guests')

    class Meta:
        unique_together = ('guest', 'table')

    def __str__(self):
        guest_name = self.guest.name if self.guest else _("Unknown Guest")
        table_name = self.table.name if self.table else _("Unknown Table")
        if self.event:
            return format_lazy(_("{guest} -> {table} for {event}"), guest=guest_name, table=table_name, event=self.event.title)
        return str(format_lazy(_("{guest} -> {table} (No Event Assigned)"), guest=guest_name, table=table_name))


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile_exists(sender, instance, created, **kwargs):
    profile, newly_created = UserProfile.objects.get_or_create(user=instance)
    if newly_created or profile.plan is None:
        default_plan = Plan.objects.filter(price=0).first() or Plan.objects.first()
        if default_plan:
            profile.plan = default_plan
            profile.save()


class Godparent(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='godparents')
    name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.name} (for event: {self.event.title})"


class ScheduleItem(models.Model):
    class ActivityType(models.TextChoices):
        CIVIL_CEREMONY = 'civil_ceremony', _('Civil Ceremony')
        RELIGIOUS_CEREMONY = 'religious_ceremony', _('Religious Ceremony')
        RECEPTION = 'reception', _('Reception')
        PARTY = 'party', _('Party')
        PHOTOSHOOT = 'photoshoot', _('Photoshoot')
        OTHER = 'other', _('Other')

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='schedule_items')
    time = models.TimeField(verbose_name=_("Time"))
    activity_type = models.CharField(max_length=50, choices=ActivityType.choices, default=ActivityType.CIVIL_CEREMONY)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['time']
        verbose_name = _("Schedule Item")
        verbose_name_plural = _("Schedule Items")

    def __str__(self):
        return f"{self.get_activity_type_display()} at {self.time}"


class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    question_ro = models.CharField(max_length=255, blank=True)
    answer_ro = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        verbose_name = _("FAQ Item")

    def __str__(self):
        return self.question


class Testimonial(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='testimonial')
    client_name = models.CharField(max_length=100)
    avatar_url = models.URLField(blank=True, null=True)
    text = models.TextField(blank=True)
    rating = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    PROVIDER_CHOICES = [('email', _('Email')), ('google', _('Google')), ('facebook', _('Facebook'))]
    social_provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='email')

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Customer Review")
        verbose_name_plural = _("Customer Reviews")

    def __str__(self):
        return f"{self.client_name} - {self.rating}★"


class AboutSection(models.Model):
    title_en = models.CharField(max_length=200, default=_("Crafted with Love"))
    description_en = models.TextField()
    title_ro = models.CharField(max_length=200, default=_("Created with Love"), blank=True)
    description_ro = models.TextField(blank=True)
    icon_svg_path = models.TextField(blank=True)
    color_class = models.CharField(max_length=50, default="text-indigo-600")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("About Section Configuration")
        verbose_name_plural = _("About Section Configurations")

    @property
    def title(self):
        return self.title_ro if get_language() == 'ro' else self.title_en

    @property
    def description(self):
        return self.description_ro if get_language() == 'ro' else self.description_en

    def __str__(self):
        return f"About Section: {self.title_en}"


class FutureFeature(models.Model):
    title_en = models.CharField(max_length=200)
    description_en = models.TextField(blank=True)
    title_ro = models.CharField(max_length=200, blank=True)
    description_ro = models.TextField(blank=True)
    icon_svg_path = models.TextField(blank=True)
    color_class = models.CharField(max_length=50, default="text-indigo-600")
    target_date = models.DateField(null=True, blank=True)
    is_public = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=0)

    @property
    def title(self):
        return self.title_ro if get_language() == 'ro' else self.title_en

    @property
    def description(self):
        return self.description_ro if get_language() == 'ro' else self.description_en

    def __str__(self):
        return self.title_en
