import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from django.http import StreamingHttpResponse

from api.models import Claim
from api.utils.file_loader import EvidenceLoader
from api.ai_service import query_claim_assessment, ClaimAssessment


class HealthView(APIView):
    def get(self, request):
        return Response({"message": "Django is talking to React!"}, status=status.HTTP_200_OK)


class AnalyzeView(APIView):
    def post(self, request):
        # Parse tracking numbers
        raw_ids = request.data.get("tracking_numbers", "")
        tracking_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]

        if not tracking_ids:
            return Response(
                {"error": "No tracking numbers provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get max iteration count
        try:
            max_iterations = int(request.data.get("iteration_count", 3))
        except (ValueError, TypeError):
            max_iterations = 3

        # Generator for data streaming
        def stream_processor():
            loader = EvidenceLoader()
            claim_states = {}

            # Initialize state for all claims
            for t_id in tracking_ids:
                claim_states[t_id] = {
                    "previous_reasoning": "N/A (First Pass)",
                    "current_estimate": 0.0,
                    "history": [],  # Keep track of iterations for this claim
                }

            for i in range(1, max_iterations + 1):
                for t_id in tracking_ids:
                    try:
                        # Fetch Data
                        claim = Claim.objects.get(id=t_id)
                        evidence = loader.load_for_claim(t_id)
                        state = claim_states[t_id]

                        # Context Variables
                        user_claimed_val = (
                            f"${claim.amount_of_claim}" if claim.amount_of_claim else "Unknown"
                        )
                        policy_limit_val = (
                            f"${claim.max_benefit}" if claim.max_benefit else "Unknown"
                        )

                        try:
                            hard_cap = (
                                float(claim.max_benefit) if claim.max_benefit else float("inf")
                            )
                        except:
                            hard_cap = float("inf")

                        system_prompt = """
                        ROLE: Forensic Document Analyst & Claims Adjuster.
                        GOAL: Digitize the "Move-Out Form" or "Ledger" and audit line items against the policy.

                        ### 1. EXTRACTION & DICTIONARY (OCR Phase)
                        - Read the "Deductions" or "Charges" list verbatim.
                        - **Abbreviations Dictionary (CRITICAL):**
                        * "MCF" = Maintenance Coordination Fee (ADMIN FEE -> REJECT)
                        * "RBP" = Resident Benefit Package (SUBSCRIPTION -> REJECT)
                        * "SDRP" = Security Deposit Replacement Program (PREMIUM -> REJECT)
                        * "NSF" = Non-Sufficient Funds (FEE -> APPROVE if on ledger)

                        ### 2. COVERAGE RULES (Audit Phase)
                        - **APPROVE (Covered):**
                        1. Unpaid Rent / Base Rent / Lease Break Fee (if valid).
                        2. Late Fees & NSF Fees.
                        3. Physical Repairs (e.g., "Wall repair", "Carpet cleaning", "Painting").
                        4. Utilities (Water, Trash, Electric).
                        
                        - **REJECT (Not Covered):**
                        1. ADMINISTRATIVE FEES: MCF, Admin Fee, Leasing Fee, Setup Fee.
                        2. SUBSCRIPTIONS: RBP, SDRP, Insurance premiums.
                        3. **DOUBLE DIPPING (CRITICAL):** - REJECT "Trash Removal" if "General Cleaning" or "Full Clean" is also charged.
                        4. MINOR CONSUMABLES: REJECT "Lightbulbs", "Batteries", "Filters" unless > $50.

                        ### 3. OUTPUT INSTRUCTION
                        - Set 'approved_amount' to the positive value for charges, negative for credits.
                        - If REJECTED, set 'approved_amount' to 0.00 and provide the 'rejection_reason'.
                        - **DO NOT calculate the final total.** Just list the items.
                        """

                        # --- UPDATED USER PROMPT WITH PREVIOUS REASONING ---
                        user_prompt = f"""
                        ### 1. CLAIM CONTEXT
                        * **Claim ID:** {t_id}
                        * **Description:** {claim.description}
                        * **User Claimed:** {user_claimed_val} (Reference Only)
                        * **Policy Limit:** {policy_limit_val}
                        
                        ### 2. PREVIOUS ITERATION STATE
                        * **Current Estimate:** ${state['current_estimate']}
                        * **Previous Logic/Notes:** {state['previous_reasoning']}
                        {f"* **CRITIQUE:** Review your previous logic above. Did you incorrectly reject a valid fee, or approve a duplicate charge? Adjust accordingly." if i > 1 else ""}

                        ### 3. RAW EVIDENCE TEXT (OCR)
                        (Below is the raw text extracted from the attached files.)
                        ---
                        {evidence['text_context']}
                        ---
                        """

                        # Query Claim Assessment
                        assessment = query_claim_assessment(
                            user_prompt=user_prompt,
                            system_prompt=system_prompt,
                            image_paths=evidence.get("image_paths"),
                        )

                        # Sum the approved amount and cap
                        calculated_sum = sum(item.approved_amount for item in assessment.line_items)

                        if calculated_sum > hard_cap:
                            estimation = hard_cap
                            reasoning_text = f"{assessment.policy_check_notes} [CAPPED: ${calculated_sum:.2f} > Limit ${hard_cap:.2f}]"
                        else:
                            estimation = calculated_sum
                            reasoning_text = assessment.policy_check_notes

                        if estimation < 0:
                            estimation = 0.0
                            reasoning_text += " [NOTE: Net balance is negative. Claim set to $0.00]"

                        # Create iteration data
                        iteration_data = {
                            "iteration": i,
                            "estimate": estimation,
                            "reasoning": reasoning_text,
                            "line_items": [item.model_dump() for item in assessment.line_items],
                            "summary": assessment.summary_of_evidence,
                        }

                        # Update the state
                        state["previous_reasoning"] = assessment.policy_check_notes
                        state["current_estimate"] = estimation
                        state["history"].append(iteration_data)

                        # Update DB
                        claim.estimated_amount = estimation
                        claim.ai_reasoning = state["history"]

                        # Update Explanation (similar to PM Explnation) only on last step or generally
                        if i == max_iterations:
                            summary_lines = [f"Summary: {assessment.summary_of_evidence}"]
                            for item in iteration_data["line_items"]:
                                summary_lines.append(
                                    f"- {item['item_name']}: ${item['claimed_amount']} -> ${item['approved_amount']}"
                                )
                            claim.ai_explanation = "\n".join(summary_lines)
                            claim.status = "SUCCESS"

                        claim.save()

                        # Create a payload to stream
                        payload = {
                            "tracking_number": t_id,
                            "ground_truth": float(claim.ground_truth_amount or 0),
                            "estimated_amount": estimation,
                            "iterations": state["history"],
                        }

                        # Yield the payload
                        yield json.dumps(payload) + "\n"

                    except Claim.DoesNotExist:
                        yield json.dumps({"tracking_number": t_id, "error": "ID not found"}) + "\n"
                    except Exception as e:
                        yield json.dumps({"tracking_number": t_id, "error": str(e)}) + "\n"

        # Return streaming response
        return StreamingHttpResponse(stream_processor(), content_type="application/x-ndjson")
