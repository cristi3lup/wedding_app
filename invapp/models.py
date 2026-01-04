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


class SiteImage(models.Model):
    """
    Imagini statice gestionabile din Admin (Hero, Logo, Bannere).
    """
    KEY_CHOICES = [
        ('hero_bg', 'Hero Background (Landing)'),
        ('logo_main', 'Logo Principal'),
        ('feature_1', 'Imagine Feature 1'),
        ('feature_2', 'Imagine Feature 2'),
        ('feature_3', 'Imagine Feature 3'),
        ('cta_bg', 'Call to Action Background'),
    ]

    key = models.CharField(
        max_length=50,
        choices=KEY_CHOICES,
        unique=True,
        help_text="Locul unde va apărea această imagine."
    )
    image = models.ImageField(upload_to='site_assets/', help_text="Încarcă imaginea aici.")
    description = models.CharField(max_length=200, blank=True, help_text="Descriere pentru Alt Text (SEO)")

    def __str__(self):
        return self.get_key_display()


class Plan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True)

    # Feature Controls
    max_guests = models.PositiveIntegerField(
        default=0,
        help_text=_("Maximum number of guests allowed. Use a very large number for unlimited.")
    )
    max_events = models.PositiveIntegerField(
        default=1,
        help_text=_("Maximum number of events this plan allows.")
    )
    is_public = models.BooleanField(
        default=True,
        help_text=_("Uncheck this to hide the plan from the landing page (useful for Admin-only testing plans).")
    )
    has_table_assignment = models.BooleanField(
        default=False,
        help_text=_("Does this plan include the table assignment feature?")
    )
    can_upload_own_design = models.BooleanField(
        default=False,
        help_text=_("Does this plan allow uploading a custom design image?")
    )

    icon_svg_path = models.TextField(
        blank=True,
        help_text=_("Paste the SVG <path> data for an icon here. e.g., <path d='...'/>")
    )
    color_class = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Main Tailwind CSS accent color. e.g., 'text-indigo-500'")
    )
    featured = models.BooleanField(
        default=False,
        help_text=_("Check this to make the plan stand out visually.")
    )
    lock_event_on_creation = models.BooleanField(
        default=False,
        help_text=_("If True, events created under this plan cannot be edited or deleted.")
    )
    stripe_price_id = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("The Price ID from Stripe for this plan (e.g., price_1J...).")
    )

    def __str__(self):
        return self.name


class SpecialField(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("The exact field name from the Event model (e.g., 'couple_photo').")
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("A user-friendly description for the admin panel.")
    )

    def __str__(self):
        return self.name


class CardDesign(models.Model):
    class EventTypeChoices(models.TextChoices):
        WEDDING = 'wedding', _('Wedding')
        BAPTISM = 'baptism', _('Baptism')
        IMAGE_UPLOAD = 'image_upload', _('Image Upload Only')

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    # Legacy path (optional)
    preview_image_path = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Path to preview image in static files (Legacy)")
    )

    # --- FIX 1: Adăugat ImageField pentru Upload din Admin ---
    preview_image = models.ImageField(
        upload_to='design_previews/',
        blank=True,
        null=True,
        help_text=_("Upload a mockup image here (Cloudinary).")
    )

    template_name = models.CharField(
        max_length=255,
        help_text=_("e.g., 'invapp/invites/design_classic.html'")
    )

    event_type = models.CharField(
        max_length=20,
        choices=EventTypeChoices.choices,
        default=EventTypeChoices.WEDDING,
        help_text=_("The type of event this design is for.")
    )

    available_on_plans = models.ManyToManyField(
        'Plan',
        blank=True,
        related_name='card_designs',
        help_text=_("Select which subscription plans can use this design.")
    )

    priority = models.PositiveIntegerField(
        default=0,
        help_text=_("Higher numbers appear first in the carousel.")
    )

    is_multilanguage = models.BooleanField(
        default=False,
        help_text=_("Check if this design supports multiple languages (shows tick icon).")
    )

    is_public = models.BooleanField(
        default=False,
        help_text=_("If unchecked, this design is hidden from the public gallery.")
    )

    # --- FIX 2: Adăugat is_active pentru Admin ---
    is_active = models.BooleanField(
        default=True,
        help_text=_("Admin control: Uncheck to soft-delete/hide this design everywhere.")
    )

    special_fields = models.ManyToManyField(
        SpecialField,
        blank=True,
        related_name='card_designs',
        help_text=_("Select any special form fields this design requires.")
    )

    def __str__(self):
        return self.name


# Represents the main wedding event details
class Event(models.Model):
    class EventTypeChoices(models.TextChoices):
        WEDDING = 'wedding', _('Wedding')
        BAPTISM = 'baptism', _('Baptism')
        IMAGE_UPLOAD = 'image_upload', _('Image Upload Only')

    event_type = models.CharField(
        max_length=20,
        choices=EventTypeChoices.choices,
        default=EventTypeChoices.WEDDING,
        verbose_name=_("Event Type"),
        help_text=_("The type of event being planned.")
    )

    # --- BAPTISM-SPECIFIC FIELDS ---
    main_invitation_image = models.ImageField(
        upload_to='invitation_images/',
        null=True,
        blank=True,
        verbose_name=_("Main Invitation Image"),
        help_text=_("Upload your main invitation image designed in Canva (or another tool).")
    )
    audio_greeting = models.FileField(
        upload_to='audio_greetings/',
        blank=True,
        null=True,
        verbose_name=_("Audio Greeting"),
        help_text=_("Optional: Upload an audio greeting (e.g., MP3, M4A, WAV).")
    )
    child_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Child Name"),
        help_text=_("Name of the child (for baptism).")
    )
    parents_names = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Parents' Names"),
        help_text=_("Names of the parents (for baptism).")
    )

    # --- WEDDING-SPECIFIC FIELDS ---
    bride_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Bride Name"),
        help_text=_("Name of the bride.")
    )
    groom_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Groom Name"),
        help_text=_("Name of the groom.")
    )
    bride_parents = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Bride's Parents"),
        help_text=_("Names of the bride's parents (e.g., 'John & Jane Doe').")
    )
    groom_parents = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Groom's Parents"),
        help_text=_("Names of the groom's parents (e.g., 'George & Mary Smith').")
    )

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='events')
    selected_design = models.ForeignKey(CardDesign, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='events')

    title = models.CharField(
        max_length=200,
        default=_("Our Wedding"),
        verbose_name=_("Event Title")
    )
    event_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Date"),
        help_text=_("Date of the event")
    )
    party_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Party Time"),
        help_text=_("Time when party starts.")
    )
    venue_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Venue Name"),
        help_text=_("Name of the venue")
    )
    venue_address = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Venue Address"),
        help_text=_("Full address of the venue")
    )
    ceremony_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Ceremony Time"),
        help_text=_("Time of the religious ceremony (for baptism/wedding).")
    )
    ceremony_location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Ceremony Location"),
        help_text=_("Name and address of the church/ceremony location.")
    )

    ceremony_maps_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name=_("Ceremony Map Link"),
        help_text=_("Optional: Google Maps Embed SRC URL")
    )
    party_maps_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name=_("Party Map Link"),
        help_text=_("Optional: Google Maps Embed SRC URL")
    )
    calendar_description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Calendar Description"),
        help_text=_("Optional: Short description for calendar event")
    )

    invitation_wording = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Invitation Wording"),
        help_text=_("Main invitation text (e.g., 'Together with their families...')")
    )
    schedule_details = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Schedule Details"),
        help_text=_("Details about the schedule (e.g., Ceremony, Reception times)")
    )
    other_info = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Other Information"),
        help_text=_("Other information (e.g., Dress code, Gift registry)")
    )

    couple_photo = models.ImageField(
        upload_to='event_photos/',
        null=True,
        blank=True,
        verbose_name=_("Couple Photo"),
        help_text=_("A photo of the couple to be displayed on the invitation.")
    )
    landscape_photo = models.ImageField(
        upload_to='event_landscape_photos/',
        null=True,
        blank=True,
        verbose_name=_("Landscape Photo"),
        help_text=_(
            "Optional: A landscape-oriented photo to display after the greeting (e.g., a photo of the venue or couple).")
    )

    def __str__(self):
        return self.title


# Represents a guest or a couple/family invited
class Guest(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='guests')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='guests')

    name = models.CharField(
        max_length=200,
        help_text=_("Primary name for the invitation (e.g., 'The Smith Family', 'John Doe')")
    )
    email = models.EmailField(
        blank=True,
        null=True,
        help_text=_("Optional: Used for sending updates")
    )
    max_attendees = models.PositiveIntegerField(
        default=1,
        help_text=_("How many people are included in this invitation")
    )

    # --- Add new phone_number field ---
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text=_("Optional: Guest's phone number.")
    )

    # --- End new phone_number field ---

    # --- Define choices for the gender field ---
    class HonorificChoices(models.TextChoices):
        MR = 'mr', _('Mr.')
        MRS = 'mrs', _('Mrs.')
        MS = 'ms', _('Ms.')
        DR = 'dr', _('Dr.')
        FAMILY = 'family', _('Family')
        COUPLE = 'couple', _('Couple')
        NONE = 'none', _('None')

    honorific = models.CharField(
        max_length=10,
        choices=HonorificChoices.choices,
        default=HonorificChoices.NONE,
        help_text=_("The courtesy title for addressing the guest (e.g., Mr., Mrs., Family).")
    )

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

    # --- Fields for invitation method and manual RSVP ---
    class InvitationMethodChoices(models.TextChoices):
        DIGITAL = 'digital', _('Digital Invitation')
        PHYSICAL = 'physical', _('Physical Invitation')

    invitation_method = models.CharField(
        max_length=20,
        choices=InvitationMethodChoices.choices,
        default=InvitationMethodChoices.PHYSICAL,
        blank=True,
        null=True
    )

    # For guests not using the digital RSVP form, or for overriding digital RSVP
    attending_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Number of guests attending")
    )

    manual_is_attending = models.BooleanField(
        null=True,
        blank=True,
        help_text=_("Manually set attendance status (e.g., for physical RSVPs).")
    )
    manual_attending_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Manually set number of attendees if known (especially for physical RSVPs).")
    )
    # --- End new fields ---

    # --- Add the new UUID field ---
    unique_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text=_("Unique identifier for the guest's invitation link")
    )

    # Property to get definitive attending count
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


# Stores the response from a guest
class RSVP(models.Model):
    # Link directly to the Guest who is responding
    guest = models.OneToOneField(Guest, on_delete=models.CASCADE, related_name='rsvp_details')

    attending = models.BooleanField(
        null=True,
        blank=True,
        choices=[(True, _('Yes')), (False, _('No'))],
        help_text=_("Will they attend?")
    )
    number_attending = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("How many are actually coming?")
    )
    meal_preference = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text=_("e.g., Vegetarian, Allergies")
    )
    message = models.TextField(
        blank=True,
        null=True,
        help_text=_("Optional message from the guest")
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = _("Undecided")
        if self.attending is True:
            status = _("Attending")
        elif self.attending is False:
            status = _("Not Attending")
        return format_lazy(_("RSVP for {name} - {status}"), name=self.guest.name, status=status)


# Represents a physical table at the reception
class Table(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tables')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tables')
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField(default=8)

    @property
    def current_seated_count(self):
        """Calculate total number of confirmed attendees seated at this table."""
        return sum(assignment.guest.attending_count for assignment in self.assigned_guests.all())

    @property
    def remaining_capacity(self):
        """Calculate remaining seats at this table."""
        return max(0, self.capacity - self.current_seated_count)

    class Meta:
        unique_together = ('event', 'name')

    def __str__(self):
        return self.name


# Assigns a guest (who RSVP'd Yes) to a table
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
            return format_lazy(_("{guest} -> {table} for {event}"), guest=guest_name, table=table_name,
                               event=self.event.title)
        return format_lazy(_("{guest} -> {table} (No Event Assigned)"), guest=guest_name, table=table_name)


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # --- FIX: Auto-assign Free Plan (Price = 0) ---
        # This ensures new users (Social or Email) start with a plan visible in dashboard
        free_plan = Plan.objects.filter(price=0).first()
        UserProfile.objects.create(user=instance, plan=free_plan)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()


# === NEW: Godparent Model                   ===
# ==============================================
class Godparent(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='godparents')
    name = models.CharField(
        max_length=200,
        help_text=_("Full name of the godparent or godparent couple (e.g., 'John & Jane Smith').")
    )

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

    activity_type = models.CharField(
        max_length=50,
        choices=ActivityType.choices,
        default=ActivityType.CIVIL_CEREMONY,
        verbose_name=_("Activity Type")
    )

    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Location")
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Details"),
        help_text=_("Optional details about this part of the event.")
    )

    class Meta:
        ordering = ['time']
        verbose_name = _("Schedule Item")
        verbose_name_plural = _("Schedule Items")

    def __str__(self):
        return f"{self.get_activity_type_display()} at {self.time}"


class FAQ(models.Model):
    # --- Versiunea în Română (Default) ---
    question = models.CharField(max_length=255, verbose_name="Întrebare (RO)")
    answer = models.TextField(verbose_name="Răspuns (RO)")

    # --- Versiunea în Engleză (NOU) ---
    question_en = models.CharField(max_length=255, blank=True, verbose_name="Question (EN)")
    answer_en = models.TextField(blank=True, verbose_name="Answer (EN)")

    order = models.PositiveIntegerField(default=0, help_text="Ordinea de afișare")
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        verbose_name = "FAQ Item"

    def __str__(self):
        return self.question


class Testimonial(models.Model):
    # Legăm de user pentru a preveni spam-ul (un review per user)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='testimonial'
    )

    # Păstrăm client_name ca string pentru a-l putea edita manual dacă e nevoie
    # (sau dacă userul își șterge contul, review-ul rămâne cu nume)
    client_name = models.CharField(max_length=100, verbose_name="Nume Client")

    # Avatar opțional (dacă vrem să preluăm poza de profil în viitor)
    avatar_url = models.URLField(blank=True, null=True)

    text = models.TextField(blank=True, verbose_name="Mesaj (Opțional)")

    rating = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Număr stele (1-5)"
    )

    is_featured = models.BooleanField(default=False, help_text="Apare pe prima pagină?")
    is_active = models.BooleanField(default=True, help_text="Este vizibil public?")
    created_at = models.DateTimeField(auto_now_add=True)

    PROVIDER_CHOICES = [
        ('email', 'Email'),
        ('google', 'Google'),
        ('facebook', 'Facebook'),
    ]
    social_provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='email',
        verbose_name="Sursa Review"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Review Client"
        verbose_name_plural = "Reviews Clienți"

    def __str__(self):
        return f"{self.client_name} ({self.social_provider}) - {self.rating}★"