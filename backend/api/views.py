from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from api.models import Claim
from api.utils.file_loader import EvidenceLoader
from api.ai_service import query_claim_assessment, ClaimAssessment


class HealthView(APIView):
    def get(self, request):
        return Response({"message": "Django is talking to React!"}, status=status.HTTP_200_OK)


class AnalyzeView(APIView):
    def post(self, request):
        # 1. Get tracking numbers
        raw_ids = request.data.get("tracking_numbers", "")
        tracking_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]

        if not tracking_ids:
            return Response(
                {"error": "No tracking numbers provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Get iteration count
        try:
            max_iterations = int(request.data.get("iteration_count", 3))
        except (ValueError, TypeError):
            max_iterations = 3

        loader = EvidenceLoader()
        results = []

        for t_id in tracking_ids:
            try:
                # Fetch Data
                claim = Claim.objects.get(id=t_id)
                evidence = loader.load_for_claim(t_id)

                iterations_log = []
                current_estimate = 0.0
                previous_reasoning = "N/A (First Pass)"

                # --- Context Preparation ---
                user_claimed_val = (
                    f"${claim.amount_of_claim}" if claim.amount_of_claim else "Unknown"
                )
                policy_limit_val = f"${claim.max_benefit}" if claim.max_benefit else "Unknown"

                try:
                    hard_cap = float(claim.max_benefit) if claim.max_benefit else float("inf")
                except:
                    hard_cap = float("inf")

                # Iteration Loop
                for i in range(1, max_iterations + 1):

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
                    * **Current Estimate:** ${current_estimate}
                    * **Previous Logic/Notes:** {previous_reasoning}
                    {f"* **CRITIQUE:** Review your previous logic above. Did you incorrectly reject a valid fee, or approve a duplicate charge? Adjust accordingly." if i > 1 else ""}

                    ### 3. RAW EVIDENCE TEXT (OCR)
                    (Below is the raw text extracted from the attached files.)
                    ---
                    {evidence['text_context']}
                    ---
                    """

                    try:
                        # Query Claim Assessment
                        assessment: ClaimAssessment = query_claim_assessment(
                            user_prompt=user_prompt,
                            system_prompt=system_prompt,
                            image_paths=evidence.get("image_paths"),
                        )

                        # Sum the Line Items
                        calculated_sum = sum(item.approved_amount for item in assessment.line_items)

                        # Apply the Hard Cap
                        if calculated_sum > hard_cap:
                            estimation = hard_cap
                            reasoning_text = f"{assessment.policy_check_notes} [CAPPED: ${calculated_sum:.2f} > Limit ${hard_cap:.2f}]"
                        else:
                            estimation = calculated_sum
                            reasoning_text = assessment.policy_check_notes

                        if estimation < 0:
                            estimation = 0.0
                            reasoning_text += " [NOTE: Net balance is negative. Claim set to $0.00]"

                        iteration_data = {
                            "iteration": i,
                            "estimate": estimation,
                            "reasoning": reasoning_text,
                            "line_items": [item.model_dump() for item in assessment.line_items],
                            "summary": assessment.summary_of_evidence,
                        }

                        # Update the reasoning state for the next loop
                        previous_reasoning = assessment.policy_check_notes

                    except Exception as e:
                        estimation = 0.0
                        reasoning_text = f"AI Service Error: {str(e)}"
                        iteration_data = {
                            "iteration": i,
                            "estimate": 0.0,
                            "reasoning": reasoning_text,
                            "error": str(e),
                        }
                        previous_reasoning = f"Error in previous step: {str(e)}"

                    iterations_log.append(iteration_data)
                    current_estimate = estimation

                # Save to Database
                claim.estimated_amount = current_estimate
                claim.ai_reasoning = iterations_log

                if iterations_log:
                    last_iter = iterations_log[-1]
                    summary_lines = [f"Summary: {last_iter.get('summary', 'No summary')}"]
                    if "line_items" in last_iter:
                        for item in last_iter["line_items"]:
                            summary_lines.append(
                                f"- {item['item_name']}: ${item['claimed_amount']} -> ${item['approved_amount']}"
                            )
                    claim.ai_explanation = "\n".join(summary_lines)

                claim.status = "SUCCESS"
                claim.save()

                results.append(
                    {
                        "tracking_number": t_id,
                        "ground_truth": claim.ground_truth_amount,
                        "estimated_amount": current_estimate,
                        "iterations": iterations_log,
                    }
                )

            except Claim.DoesNotExist:
                results.append({"tracking_number": t_id, "error": "ID not found in DB"})
            except Exception as e:
                results.append({"tracking_number": t_id, "error": str(e)})

        return Response(results)
