from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import Event, Guest, RSVP, Plan, UserProfile, CardDesign
from django.urls import reverse

class DashboardPerformanceTest(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', password='password123')
        
        # Create a basic plan
        self.plan = Plan.objects.create(name='Free', price=0, max_events=5, max_guests=100)
        
        # Ensure profile exists (signal handles this usually, but let's be explicit)
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.plan = self.plan
        self.profile.save()

        # Create a design
        self.design = CardDesign.objects.create(name='Classic', template_name='invapp/invites/default_invite.html')

        # Create an event
        self.event = Event.objects.create(
            owner=self.user,
            title="Test Wedding",
            selected_design=self.design
        )

        # Create guests
        self.guest1 = Guest.objects.create(owner=self.user, event=self.event, name="Guest 1")
        self.guest2 = Guest.objects.create(owner=self.user, event=self.event, name="Guest 2")
        
        # RSVP for Guest 1 (Attending)
        RSVP.objects.create(guest=self.guest1, attending=True, number_attending=2)
        
        # RSVP for Guest 2 (Not Attending)
        RSVP.objects.create(guest=self.guest2, attending=False)

        self.client = Client()
        self.client.login(username='testuser', password='password123')

    def test_dashboard_guest_counts(self):
        """
        Verify that the dashboard correctly calculates guest counts using the annotated queryset.
        """
        url = reverse('invapp:dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check if the event in context has correct annotations
        events_in_context = response.context['events']
        self.assertEqual(len(events_in_context), 1)
        
        event = events_in_context[0]
        
        # Guest 1 is attending, Guest 2 is not.
        # confirmed_count counts GUESTS (rows) that are attending.
        self.assertEqual(event.confirmed_count, 1)
        self.assertEqual(event.total_guests_count, 2)
