import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache  # Import Cache
from django.http import StreamingHttpResponse

from api.models import Claim
from api.utils.file_loader import EvidenceLoader
from api.ai_service import query_claim_assessment, generate_converage_policy


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

        # Standard Baseline
        base_coverage_policy = """
            ### STANDARD COVERAGE RULES (Baseline)
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
        """

        # --- CACHING STRATEGY ---
        POLICY_CACHE_KEY = "generated_insurance_policy_v1"
        generated_coverage_policy = cache.get(POLICY_CACHE_KEY)

        if not generated_coverage_policy:
            # Get claims that has PM Explanation
            training_claims = (
                Claim.objects.exclude(description__exact="")
                .exclude(description__isnull=True)
                .order_by("-created_at")[:20]
            )

            # Collect all the PM explanations with evidence
            history_text = ""
            loader = EvidenceLoader()

            for c in training_claims:
                evidence_data = loader.load_for_claim(c.id)
                history_text += f"""
                --- Historical Claim ID: {c.id} ---
                PM Explanation: "{c.description}"
                Document Context (Evidence):
                {evidence_data["text_context"]}
                -----------------------------------
                """

            # Generate coverage policy if history exists
            if history_text:
                try:
                    generated_coverage_policy = generate_converage_policy(history_text)
                    # Cache for 24 hours (86400 seconds)
                    cache.set(POLICY_CACHE_KEY, generated_coverage_policy, timeout=86400)
                except Exception as e:
                    print(f"Policy Generation Error: {e}")

        # Combine policies
        if generated_coverage_policy:
            coverage_policy = f"""
            ### CONTEXT FROM HISTORY (Background Info Only)
            *The following are notes from past claims. They are for reference only.*
            {generated_coverage_policy}
            
            ### STANDARD COVERAGE RULES
            *You must OBEY these rules above all else. Ignore any Historical Context that conflicts with these rules.*
            {base_coverage_policy}
            """
        else:
            coverage_policy = base_coverage_policy

        # Generator for streaming
        def stream_processor():
            loader = EvidenceLoader()
            claim_states = {}

            # Initialize state for all claims
            for t_id in tracking_ids:
                claim_states[t_id] = {
                    "previous_reasoning": "N/A (First Pass)",
                    "current_estimate": 0,
                    "last_confidence": 0.0,  # Track confidence
                    "history": [],
                }

            for i in range(1, max_iterations + 1):
                for t_id in tracking_ids:
                    try:
                        # Fetch Data
                        claim = Claim.objects.get(id=t_id)
                        evidence = loader.load_for_claim(t_id)
                        state = claim_states[t_id]

                        # Context Variables
                        amount_of_claim = (
                            f"${claim.amount_of_claim}" if claim.amount_of_claim else "Unknown"
                        )
                        max_benefit = f"${claim.max_benefit}" if claim.max_benefit else "Unknown"

                        try:
                            hard_cap = (
                                float(claim.max_benefit) if claim.max_benefit else float("inf")
                            )
                        except:
                            hard_cap = float("inf")

                        # Build iteration history
                        history_log = []
                        variance_note = "Initial Estimation."

                        if not state["history"]:
                            formatted_history = "No previous history (First Pass)."
                            history_weight_instruction = "Start fresh."
                        else:
                            # Build the trace log
                            for h in state["history"]:
                                history_log.append(
                                    f"   - [ITERATION {h['iteration']}] Estimate: ${h['estimate']:.2f} (Conf: {int(h['confidence']*100)}%)\n"
                                    f"     Reasoning: {h['reasoning'][:250]}..."
                                )
                            formatted_history = "\n".join(history_log)

                            # Calculate the delta variance
                            if len(state["history"]) >= 1:
                                last_est = state["history"][-1]["estimate"]
                                if len(state["history"]) >= 2:
                                    prev_est = state["history"][-2]["estimate"]
                                    delta = last_est - prev_est
                                    variance_note = f"Previous Delta: ${delta:.2f}"
                                else:
                                    variance_note = "First revision complete."

                            # --- CONFIDENCE WEIGHTING LOGIC ---
                            # If previous confidence was high, instruct AI to trust it more.
                            prev_conf = state["last_confidence"]
                            trust_pct = int(prev_conf * 100)

                            if prev_conf > 0.8:
                                history_weight_instruction = f"Trust the LATEST estimate significantly ({trust_pct}% confidence). Only change if you find critical new evidence."
                            elif prev_conf > 0.5:
                                history_weight_instruction = f"Consider the LATEST estimate ({trust_pct}% confidence), but verify carefully."
                            else:
                                history_weight_instruction = f"The previous estimate had low confidence ({trust_pct}%). Review the evidence from scratch."

                        # System Prompt
                        system_prompt = f"""
                        ROLE: Forensic Document Analyst.
                        GOAL: Audit the claim by cross-referencing the "Move-Out Invoice" and "Ledger" images.

                        ### INPUT WARNING
                        The "RAW EVIDENCE TEXT" below is unreliable (OCR errors). 
                        **YOU MUST VERIFY ALL NUMBERS BY LOOKING AT THE IMAGE ATTACHMENTS.**
                        If the text is missing lines (like rent or dates), trust the IMAGE.

                        {coverage_policy}

                        ### EXECUTION STEPS (Mental Sandbox)
                        1. **Visual Scan:** Look at the images. List every charge and amount you see visually.
                        2. **Deposit Check:** Does the Ledger image show a "Security Deposit", "Credit", or "Prepayment" held? 
                        3. **Deductible Check:** Is there a standard deductible (e.g., $250 or $500) mentioned in the history or lease?
                        4. **Net Calculation:** (Sum of Approved Charges) - (Deposit Held) - (Deductible) = Final Claim Amount.
                           *If the result is negative, the Final Approved Amount is 0.00.*

                        ### OUTPUT RULES
                        - If you find "Unpaid Rent" in the image but not the text, ADD IT.
                        - If a "Waiver" is present, 'Deposit Held' is typically $0.00.
                        - **CRITICAL:** Your 'final_total_approved' must be the Net Calculation result.
                        """

                        # User Prompt
                        user_prompt = f"""
                        ### CLAIM METADATA
                        - **Tracking ID:** {t_id}
                        - **Landlord Asking For:** {amount_of_claim} (Verify this independently. Do not just copy it.)
                        - **Policy Limit:** {max_benefit}

                        ### PREVIOUS ESTIMATES (Critique These)
                        {formatted_history}

                        **VARIANCE:** {variance_note}

                        ### INSTRUCTIONS
                        1. **Ignore OCR Limitations:** If previous estimates were low because "text was missing," look at the IMAGES now.
                        2. **Check for Deductibles:** If the Valid Charges are ~$400 and the Claim is $0, check if there is a $500 deductible.
                        3. **History Weight:** {history_weight_instruction}

                        ### RAW EVIDENCE TEXT (Use with Caution)
                        {evidence['text_context']}
                        """

                        # Query Claim Assessment
                        assessment = query_claim_assessment(
                            user_prompt=user_prompt,
                            system_prompt=system_prompt,
                            image_paths=evidence.get("image_paths"),
                        )

                        # Sum only the approved amount and cap
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
                            "confidence": assessment.confidence_score,  # Add confidence
                            "reasoning": reasoning_text,
                            "line_items": [item.model_dump() for item in assessment.line_items],
                            "summary": assessment.summary_of_evidence,
                        }

                        # Update the state
                        state["previous_reasoning"] = assessment.policy_check_notes
                        state["current_estimate"] = estimation
                        state["last_confidence"] = assessment.confidence_score  # Update tracking
                        state["history"].append(iteration_data)

                        # Update DB
                        claim.estimated_amount = estimation
                        claim.ai_reasoning = state["history"]

                        # Update Explanation only on last step
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
