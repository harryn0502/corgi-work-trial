import os
import pandas as pd
from django.core.management.base import BaseCommand
from api.models import Claim


# Helper function to clean currency "$1,200.00" -> 1200.00
def clean_currency(val):
    if pd.isna(val):
        return None
    s = str(val).replace("$", "").replace(",", "").strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return float(s)
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Load claims from csv"

    def handle(self, *args, **options):
        csv_path = "/app/data/claims.csv"

        # Check csv exists
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"File not found: {csv_path}"))
            return

        # Read the csv
        self.stdout.write(f"Reading {csv_path}...")
        df = pd.read_csv(csv_path)

        # Add it to the database
        count = 0
        for index, row in df.iterrows():
            try:
                # ID (Tracking Number)
                tracking_number = str(row["Tracking Number"]).strip()
                if not tracking_number or tracking_number.lower() == "nan":
                    continue

                # Parse Financials
                amount_of_claim = clean_currency(row.get("Amount of Claim"))
                max_benefit = clean_currency(row.get("Max Benefit"))
                ground_truth_amount = clean_currency(row.get("Approved Benefit Amount"))

                # Parse Strings
                claim_status = row.get("Status")
                if pd.isna(claim_status):
                    claim_status = "Unknown"

                desc = row.get("PM Explanation")
                description = desc if pd.notna(desc) else "No explanation provided."

                # Update Database
                Claim.objects.update_or_create(
                    id=tracking_number,
                    defaults={
                        "amount_of_claim": amount_of_claim,
                        "max_benefit": max_benefit,
                        "claim_status": claim_status,
                        "ground_truth_amount": ground_truth_amount,
                        "description": description,
                    },
                )
                count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Skipped row {index}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully loaded {count} claims."))
