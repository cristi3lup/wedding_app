import csv
import random
import string
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from invapp.models import Voucher

class Command(BaseCommand):
    help = 'Generates a batch of unique campaign vouchers and exports them to CSV.'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=50, help='Number of vouchers to generate')
        parser.add_argument('--campaign', type=str, default='General', help='Name of the campaign')
        parser.add_argument('--days-valid', type=int, default=30, help='How many days the vouchers are valid')
        parser.add_argument('--discount', type=int, default=100, help='Discount percentage (1-100)')

    def handle(self, *args, **options):
        count = options['count']
        campaign = options['campaign']
        days_valid = options['days-valid']
        discount = options['discount']
        
        valid_until = timezone.now() + timedelta(days=days_valid)
        
        # Base URL for activation (signup with voucher param)
        # Using a default or settings if available, otherwise a placeholder
        base_url = "https://invapp-romania.ro/ro/accounts/signup/"
        
        vouchers_created = []
        
        self.stdout.write(f"Generating {count} vouchers for campaign '{campaign}'...")
        
        for _ in range(count):
            # Generate a unique code: TARG-XXXX
            code = f"TARG-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
            
            # Ensure uniqueness
            while Voucher.objects.filter(code=code).exists():
                code = f"TARG-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
            
            voucher = Voucher.objects.create(
                code=code,
                discount_percentage=discount,
                campaign_name=campaign,
                valid_until=valid_until,
                active=True,
                max_uses=1 # Single use for these campaigns
            )
            vouchers_created.append(voucher)
            
        # Export to CSV
        filename = f"vouchers_{campaign}_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Cod Voucher', 'Link Activare', 'Campanie', 'Valabil Pana La'])
            for v in vouchers_created:
                activation_link = f"{base_url}?v={v.code}"
                writer.writerow([v.code, activation_link, v.campaign_name, v.valid_until.strftime('%Y-%m-%d %H:%M')])
                
        self.stdout.write(self.style.SUCCESS(f"Successfully generated {len(vouchers_created)} vouchers."))
        self.stdout.write(self.style.SUCCESS(f"CSV file exported to: {filename}"))
