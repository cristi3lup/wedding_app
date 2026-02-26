# Standard Operating Procedure (SOP): Digital Marketing & Design Services Promotion

## 1. Overview
This strategy focuses on cross-promoting InvApp digital invitations alongside premium wedding decor and floral design services to provide couples with a cohesive, "digitally harmonized" wedding experience.

## 2. Value Proposition
*   **Unified Aesthetic:** The digital invitation design matches the physical floral and decor themes.
*   **All-in-One Luxury:** The couple receives a premium technical solution (InvApp) as an added-value gift for high-tier decor contracts.
*   **Zero-Stress Organization:** Positioning the platform as the "Digital Assistant" that handles the boring logistics while the couple focuses on design.

## 3. Promotion Channels & Execution
### A. Social Media (Instagram/TikTok/Facebook)
1.  **"Behind the Scenes" Content:** Post videos of a floral setup being built alongside a phone screen showing the matching digital invitation.
2.  **Reels/Stories:** Use the "Limited Offer" urgency. Highlight that the Premium InvApp gift is only available for contracts signed during specific windows (e.g., Fair Weekends).
3.  **Link in Bio:** Always include the direct landing page link: `https://invapp-romania.ro/ro/`.

### B. Direct Sales & Consultation
1.  **The "Wow" Factor:** During decor consultations, show the client their potential invitation design on a tablet. 
2.  **The Closer:** If a client is hesitant on a decor package price, use the InvApp Premium voucher as the final "free gift" to close the deal.

### C. Physical QR Codes
1.  Print high-quality business cards or mini-flyers with a QR code pointing to `https://invapp-romania.ro/ro/`.
2.  Place these QR codes inside floral centerpieces at display booths during fairs.

## 4. Brand Integration
*   Ensure all promotional graphics use the **Indigo/Gold/White** palette to maintain the "InvApp Premium" feel.
*   Mention "Powered by Culori" in the website footer to leverage the authority of the established design brand.

---

# Standard Operating Procedure (SOP): Wedding Fair Campaign

## 1. Overview
This campaign is designed to convert leads at physical wedding fairs into premium digital invitation users. The workflow automates the process of generating 100% discount vouchers and applying them instantly via WhatsApp links.

## 2. Preparation (Admin Panel)
1.  **Log in** to the Django Admin.
2.  Navigate to **InvApp > Vouchers**.
3.  Click the **"➕ Generează Vouchere Bulk"** button (top right).
4.  Fill in the parameters:
    *   **Count:** e.g., 100
    *   **Campaign Name:** e.g., `Targ_Bucuresti_Martie_2026`
    *   **Days Valid:** e.g., 7 (determines when the link stops working).
    *   **Discount %:** 100
5.  Click **"Generează și Descarcă CSV"**.
6.  **Save the CSV file** securely. It contains the unique activation links.

## 3. Sales Execution (At the Fair)
1.  When a customer signs a floral/decor contract, identify their unique voucher link from the CSV.
2.  **Send the link via WhatsApp** to the client.
    *   *Message Template:* "Felicitări pentru contract! Iată cadoul promis - accesul tău gratuit la InvApp Premium: https://invapp-romania.ro/ro/accounts/signup/?v=TARG-XXXX"
3.  The client clicks the link, signs up, and is **automatically upgraded** to Premium without any payment step.

## 4. Automation & UI Cleanup
*   **Countdown:** The landing page displays a live countdown to the end of the fair (Sunday 20:00).
*   **Auto-Hide:** The urgency banner is active from **Friday to Monday**. 
*   **Expiration:** 24 hours after the Sunday 20:00 deadline (i.e., Monday 20:00), the top black banner will automatically disappear from the website to maintain brand integrity.

## 5. Performance Tracking
1.  In the Admin panel, filter Vouchers by **Campaign Name**.
2.  Check the **Is Used** and **Used At** columns to see how many clients activated their gift in real-time.
3.  Review the **Used By** column to cross-reference with your contract list.

---

# Standard Operating Procedure (SOP): Invitation Design Development

## 1. Overview
This procedure outlines how to create, test, and deploy new invitation templates. Following this workflow ensures that designs remain responsive, multi-language compatible, and under full administrative control.

## 2. Design Workflow
### A. Creative (External)
1.  **Figma/Canva:** Create the visual concept. Identify "Dynamic Zones" (e.g., where names, dates, and locations will go).
2.  **Asset Export:** Export static backgrounds, ornaments, or icons. Upload large images to **Cloudinary** via the Django Admin (Site Assets) to keep the app fast.

### B. Technical Implementation (The Template)
1.  **Create File:** Create a new HTML file in `invapp/templates/invapp/invites/` (e.g., `design_vintage_luxury.html`).
2.  **Inheritance:** Always extend `invapp/base_invite.html` to inherit core CSS, JS, and font logic.
3.  **Dynamic Tags:** Use standard Django tags for all event data:
    *   Couple: `{{ event.bride_name }} & {{ event.groom_name }}`
    *   Date: `{{ event.event_date|date:"d F Y" }}`
    *   Logic: Use `{% if event.godparents.all %}` blocks to handle optional fields gracefully.
4.  **Localization:** Wrap ALL static text in `{% translate "..." %}`.

### C. Registration (Admin Panel)
To have **maximum control** over the design without writing code, register it in the database:
1.  Navigate to **Admin > Card Designs > Add Card Design**.
2.  **Name:** Give it a premium name (e.g., "Boho Eucalyptus").
3.  **Template Name:** Enter the exact path created in Step B (e.g., `invapp/invites/design_boho.html`).
4.  **Preview Image:** Upload a high-quality mockup thumbnail.
5.  **Priority:** Set a number (higher = appears first in the carousel).
6.  **Public Toggle:** Use this to "Soft Launch" designs before making them live.

## 3. Controlling Access & Pricing
*   **Plan Restrictions:** In the `Card Design` admin page, select which **Plans** can use this design. This allows you to lock "Luxury" designs to only the most expensive pachet.
*   **Special Fields:** Use the `Special Fields` ManyToMany to tell the event form which inputs are needed (e.g., if a design *must* have a Couple Photo, select `couple_photo`).

## 4. Testing & Validation
1.  **Demo View:** Before going public, use the `event_preview_demo` URL to see how the design renders with real user data.
2.  **Mobile Check:** Use Chrome DevTools (F12) to test the design on "iPhone SE" and "Samsung Galaxy" widths.
3.  **Language Toggle:** Switch between RO/EN to ensure text doesn't overflow or break the layout.

---

# Appendix: Event Data Mapping (Used Fields)

When creating a new design, use this list to map out which data points will be displayed. These fields are accessible via the `{{ event }}` object in Django templates.

### 1. Core Event Info
*   `{{ event.title }}`: The internal title or main heading (e.g., "Our Wedding").
*   `{{ event.event_type }}`: Choice field: `wedding`, `baptism`, or `image_upload`.
*   `{{ event.event_date }}`: Full date and time. Use filters: `{{ event.event_date|date:"d F Y" }}`.

### 2. People & Roles
*   **Wedding Specific:**
    *   `{{ event.bride_name }}`: Name of the bride.
    *   `{{ event.groom_name }}`: Name of the groom.
    *   `{{ event.bride_parents }}`: Names of the bride's parents.
    *   `{{ event.groom_parents }}`: Names of the groom's parents.
*   **Baptism Specific:**
    *   `{{ event.child_name }}`: Name of the child being baptized.
    *   `{{ event.parents_names }}`: Names of the parents.
*   **Common:**
    *   `{{ event.godparents.all }}`: QuerySet of godparents. Loop using `{% for gp in event.godparents.all %}{{ gp.name }}{% endfor %}`.

### 3. Locations & Logistics
*   **Ceremony (Church/City Hall):**
    *   `{{ event.ceremony_time }}`: Time of the ceremony.
    *   `{{ event.ceremony_location }}`: Name of the church or venue.
    *   `{{ event.ceremony_address }}`: Full physical address.
    *   `{{ event.ceremony_maps_url }}`: Google Maps link for navigation.
*   **Reception/Party:**
    *   `{{ event.party_time }}`: Start time of the celebration.
    *   `{{ event.venue_name }}`: Name of the restaurant/ballroom.
    *   `{{ event.venue_address }}`: Full physical address.
    *   `{{ event.party_maps_url }}`: Google Maps link for navigation.

### 4. Custom Content
*   `{{ event.invitation_wording }}`: The main body text/story of the invitation.
*   `{{ event.calendar_description }}`: Text for "Add to Calendar" events.
*   `{{ event.other_info }}`: Additional logistics or notes (e.g., "No flowers please").

### 5. Media & Visuals
*   `{{ event.couple_photo.url }}`: Primary photo of the couple/child.
*   `{{ event.landscape_photo.url }}`: Wide-format photo for banners.
*   `{{ event.main_invitation_image.url }}`: Full static invitation (for Image Upload designs).
*   `{{ event.audio_greeting.url }}`: Path to the background music/voice message.
*   `{{ event.gallery_images.all }}`: Up to 6 photos. Loop: `{% for img in event.gallery_images.all %}{{ img.image.url }}{% endfor %}`.

### 6. Schedule (Timeline)
*   `{{ event.schedule_items.all }}`: Detailed itinerary.
    *   Fields per item: `.time`, `.activity_type`, `.location`, `.description`.

---

# Appendix: RSVP Integration Mapping (Used Fields)

To integrate RSVP functionality into a new design, use these fields to build the confirmation form. RSVP data is linked to a specific `Guest` via their `unique_id`.

### 1. Guest Context (Pre-filled or Logic)
*   `{{ guest.name }}`: The name(s) of the people invited (e.g., "The Smith Family").
*   `{{ guest.max_attendees }}`: The maximum number of people allowed for this specific invitation.
*   `{{ guest.unique_id }}`: Used in the URL to identify the guest (e.g., `invapp-romania.ro/rsvp/UUID/`).

### 2. RSVP Form Fields (Data to Collect)
*   `attending`: (Boolean) `True` for Yes, `False` for No.
*   `number_attending`: (Integer) How many people from the group are actually coming (must be `<= guest.max_attendees`).
*   `meal_preference`: (Text) Space for dietary restrictions, allergies, or menu choices (e.g., "1 Vegetarian, 1 Child").
*   `message`: (Text) Optional personal note from the guest to the hosts.

### 3. Displaying RSVP Status (For the Host/Admin)
*   `{{ guest.is_attending }}`: Returns the current status (Yes/No/None).
*   `{{ guest.attending_count }}`: Returns the confirmed number of participants.
*   `{{ guest.rsvp_details.submitted_at }}`: Timestamp of when the guest last responded.
*   `{{ guest.rsvp_source }}`: Indicates if the RSVP was `automatic` (via the site) or `manual` (updated by the host).


