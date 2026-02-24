# Ghid de Lucru pentru Crearea și Înregistrarea Template-urilor (SOP)

Acest ghid detaliază procesul de adăugare a noilor design-uri premium în platforma InvApp, asigurând control creativ deplin fără a afecta logica de backend.

---

### **Pasul 1: Scheletul UI (Crearea Fișierului HTML)**
Pentru a începe un design nou, creați un fișier HTML în directorul `invapp/templates/invapp/invites/`. Folosiți Tailwind CSS pentru styling rapid și responsiv.

*   **Locație recomandată:** `invapp/templates/invapp/invites/nume_design.html`
*   **Structura de bază:**
    ```html
    {% load static %}
    {% load i18n %}
    <!DOCTYPE html>
    <html lang="{{ guest.preferred_language|default:'ro' }}">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <title>{{ event.title }}</title>
        <!-- Adăugați fonturi Google aici -->
    </head>
    <body class="bg-gray-100 font-sans">
        <!-- Design-ul tău aici -->
    </body>
    </html>
    ```

---

### **Pasul 2: Injecția de Date (Variabile Django)**

#### **2.1. Date Generale Eveniment**
*   **Titlu Eveniment:** `{{ event.title }}`
*   **Dată:** `{{ event.event_date|date:"d F Y" }}`
*   **Locație Petrecere:** `{{ event.venue_name }}`, `{{ event.venue_address }}`
*   **Ora Petrecere:** `{{ event.party_time|time:"H:i" }}`
*   **Locație Ceremonie:** `{{ event.ceremony_location }}`, `{{ event.ceremony_address }}`
*   **Ora Ceremonie:** `{{ event.ceremony_time|time:"H:i" }}`
*   **Hărți (Links):** `{{ event.ceremony_maps_url }}` și `{{ event.party_maps_url }}`

#### **2.2. Protagoniști (Nuntă & Botez)**
*   **Nume Mirilor:** `{{ event.bride_name }}` și `{{ event.groom_name }}`
*   **Părinți Miri:** `{{ event.bride_parents }}` și `{{ event.groom_parents }}`
*   **Nume Copil (Botez):** `{{ event.child_name }}`
*   **Părinți Copil (Botez):** `{{ event.parents_names }}`
*   **Nași (Listă):**
    ```html
    {% for godparent in event.godparents.all %}
        <p>{{ godparent.name }}</p>
    {% endfor %}
    ```

#### **2.3. Program (Timeline/Schedule)**
Pentru a afișa evenimentele în ordine cronologică:
```html
{% for item in event.schedule_items.all %}
    <div class="flex gap-4">
        <span>{{ item.time|time:"H:i" }}</span>
        <span>{{ item.get_activity_type_display }}</span>
        <span>{{ item.location }}</span>
        <p>{{ item.description }}</p>
    </div>
{% endfor %}
```

#### **2.4. Texte Personalizate**
*   **Text Invitație:** `{{ event.invitation_wording|linebreaks }}`
*   **Detalii Program:** `{{ event.schedule_details|linebreaks }}`
*   **Alte Informații (Dresscode etc):** `{{ event.other_info|linebreaks }}`

---

### **Pasul 3: Media & Managementul Asset-urilor**

#### **3.1. Fotografii Utilizator**
*   **Imagine Principală (Canva/Design):** `{{ event.main_invitation_image.url }}`
*   **Poză Cuplu:** `{{ event.couple_photo.url }}`
*   **Poză Landscape:** `{{ event.landscape_photo.url }}`
*   **Galerie Foto (Până la 6 poze):**
    ```html
    <div class="grid grid-cols-2 gap-2">
        {% for photo in event.gallery_images.all %}
            <img src="{{ photo.image.url }}" class="rounded-lg shadow">
        {% endfor %}
    </div>
    ```
    *Atenție: Folosiți întotdeauna un `if` pentru a verifica dacă imaginea există:*
    `{% if event.couple_photo %}<img src="{{ event.couple_photo.url }}">{% endif %}`

#### **3.2. Audio (Melodie de Fundal)**
Pentru a adăuga mesajul audio sau melodia încărcată de utilizator:
```html
{% if event.audio_greeting %}
    <audio id="bgMusic" src="{{ event.audio_greeting.url }}" preload="auto"></audio>
    <button onclick="document.getElementById('bgMusic').play()">Play Music</button>
{% endif %}
```

#### **3.3. Asset-uri Statice (Design-ul tău)**
Asset-urile care fac parte din tema grafică (nu sunt încărcate de utilizator):
`{% static 'invapp/images/nume_fisier.png' %}`

---

### **Pasul 4: Awareness Live Preview (Modul Editare)**
Sistemul InvApp permite utilizatorului să vadă modificările în timp real (Live Preview) în timp ce completează formularul de editare. Template-ul tău trebuie să știe dacă este în mod "Preview" sau în mod "Invitatie Reală".

Folosește variabila booleană `is_preview` pentru a dezactiva elementele care nu au sens în timpul editării:

*   **Dezactivare Formular RSVP:**
    ```html
    <button type="submit" 
            {% if is_preview %}disabled onclick="alert('RSVP dezactivat în preview');"{% endif %}
            class="{% if is_preview %}opacity-50 cursor-not-allowed{% endif %}">
        Confirmă Prezența
    </button>
    ```

*   **Ascundere Script-uri (Analytics, Facebook Pixel):**
    Nu vrei să numeri vizitele proprietarului care își editează invitația ca fiind vizite de la invitați.
    ```html
    {% if not is_preview %}
        <!-- Cod Google Analytics / Facebook Pixel -->
    {% endif %}
    ```

---

### **Pasul 5: Înregistrarea în Sistem (Activarea Design-ului)**
După ce fișierul HTML este gata, trebuie să îl faceți vizibil utilizatorilor prin Interfața de Administrare Django.

1.  Accesați **Panoul de Administrare** (`/admin/`).
2.  Navigați la secțiunea **Card Designs** -> **Add Card Design**.
3.  Completați câmpurile:
    *   **Name:** Numele comercial (ex: "Royal Velvet").
    *   **Template Name:** Calea exactă către fișier, de ex: `invapp/invites/nume_design.html`.
    *   **Event Type:** Wedding, Baptism sau Image Upload Only.
    *   **Preview Image:** Încărcați un mockup (copertă) pentru selectorul de teme.
    *   **Priority:** Număr mare (ex: 50) pentru a apărea printre primele.
    *   **Is Public:** Bifați pentru activare.
4.  **Salvați.** Design-ul va apărea acum în selectorul de teme al utilizatorilor.

---

**Sfat de Tech Lead:** Întotdeauna folosiți filtrul `|linebreaks` pentru câmpurile de text lungi pentru a păstra paragrafele create de utilizator în formulare.
