from django.db import models


# Create your models here.
class Claim(models.Model):
    # Processing State
    PROCESSING_STATUS = [
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
    ]

    # Tracking Number
    id = models.CharField(primary_key=True, max_length=50)

    # Amount of Claim
    amount_of_claim = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Max Benefit
    max_benefit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # --- Ground Truth ---
    # Status
    claim_status = models.CharField(max_length=100, blank=True, null=True)

    # Approved Benefit Amount
    ground_truth_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    # PM Explanation
    description = models.TextField(blank=True, null=True)

    # --- Estimation ---
    estimated_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    ai_explanation = models.TextField(blank=True, null=True)
    ai_reasoning = models.JSONField(default=list, blank=True)

    # --- Status ---
    status = models.CharField(max_length=20, choices=PROCESSING_STATUS, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id} | Claim: ${self.amount_of_claim} | Truth: ${self.ground_truth_amount}"
