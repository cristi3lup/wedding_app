from django.dispatch import receiver
# --- THE REAL FIX: Import the dictionary, not the signal itself ---
from djstripe.signals import WEBHOOK_SIGNALS
from .models import UserProfile, Plan
# --- THE REAL FIX: Import 'Session', not 'CheckoutSession' ---
from djstripe.models import Customer, Session, Price
import sys


# --- THE REAL FIX: Connect to the signal using the dictionary key ---
# We will listen for "checkout.session.completed" as it's the most reliable
# signal for this job and will help avoid the "database is locked" error.
@receiver(WEBHOOK_SIGNALS["checkout.session.completed"])
def upgrade_plan_on_payment(sender, event, **kwargs):
    """
    This function is called when a Checkout Session is completed.
    """
    print("INFO: checkout.session.completed webhook received. Processing plan upgrade...")

    try:
        # 1. Get the session object from the event
        session_data = event.data["object"]

        # 2. Get the Customer object from the session
        customer_id = session_data.get("customer")
        if not customer_id:
            print(f"Webhook Error: No customer ID found in Checkout Session.")
            return

        customer = Customer.objects.get(id=customer_id)

        # 3. Find the User in our database
        user = customer.subscriber
        if not user:
            print(f"Webhook Error: No local user (subscriber) found for customer {customer_id}.")
            return

        # 4. Find the Checkout Session in our database to get the line items
        checkout_session = Session.objects.get(id=session_data.get("id"))

        # 5. Get the Price ID from the Checkout Session's line items
        line_items = checkout_session.line_items.all()
        if not line_items:
            print(f"Webhook Error: Checkout Session {checkout_session.id} has no line items.")
            return

        stripe_price_id = line_items[0].price.id

        # 6. Find the Plan they purchased in our database
        plan = Plan.objects.get(stripe_price_id=stripe_price_id)
        if not plan:
            print(f"Webhook Error: No plan found with stripe_price_id {stripe_price_id}.")
            return

        # 7. Upgrade the User's Profile
        user_profile, created = UserProfile.objects.get_or_create(user=user)
        user_profile.plan = plan
        user_profile.save()

        print(f"SUCCESS: Upgraded user {user.email} to {plan.name}!")

    except Customer.DoesNotExist:
        print(f"Webhook Error: Customer {customer_id} not found in database.", file=sys.stderr)
    except Session.DoesNotExist:
        print(f"Webhook Error: Session {session_data.get('id')} not found in database.", file=sys.stderr)
    except Plan.DoesNotExist:
        print(f"Webhook Error: Plan with price_id {stripe_price_id} not found.", file=sys.stderr)
    except Exception as e:
        print(f"Webhook Error: An unexpected error occurred: {e}", file=sys.stderr)