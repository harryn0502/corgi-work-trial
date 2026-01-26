import json
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from api.models import Claim
from api.utils.file_loader import EvidenceLoader
from api.ai_service import query_ai


def health_check(request):
    return JsonResponse({"status": "ok", "message": "Django is talking to React!"})


class BatchAnalyzeView(APIView):
    def post(self, request):
        # Get tracking numbers and split them into each number
        raw_ids = request.data.get("tracking_numbers", "")
        tracking_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]

        if not tracking_ids:
            return Response(
                {
                    "error": "No tracking numbers provided. Please send a comma-separated list (e.g., '1, 2, 3')."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get iteration count (default: 3)
        try:
            max_iterations = int(request.data.get("iteration_count", 3))
        except (ValueError, TypeError):
            max_iterations = 3

        # Prepare the anaylzed result
        loader = EvidenceLoader()
        results = []

        for t_id in tracking_ids:
            try:
                # Fetch Data
                claim = Claim.objects.get(id=t_id)
                evidence = loader.load_for_claim(t_id)

                # Prepare Loop
                iterations = []
                current_estimate = 0

                # Context formatting
                max_benefit = f"${claim.max_benefit}" if claim.max_benefit else "Unknown"
                amount_of_claim = (
                    f"${claim.amount_of_claim}" if claim.amount_of_claim else "Unknown"
                )

                # Iteration Loop
                for i in range(1, max_iterations + 1):
                    prompt = f"""
                    Iteration {i} of {max_iterations}.
                    ROLE: Senior Insurance Adjuster.
                    GOAL: Determine the 'Approved Benefit Amount' (Ground Truth).
                    
                    CLAIM CONTEXT:
                    - ID: {t_id}
                    - PM Description: {claim.description}
                    - Amount User Claimed: {max_benefit} (You likely cannot exceed this)
                    - Max Benefit Policy: {amount_of_claim} (You ABSOLUTELY cannot exceed this)
                    
                    EVIDENCE FILES:
                    {evidence['text_context']}
                    
                    PREVIOUS ESTIMATE: ${current_estimate}
                    {f'Critique the previous guess. If it is 0, start fresh.' if i > 1 else ''}
                    
                    OUTPUT JSON ONLY: {{ "amount": 100.00, "reasoning": "Brief explanation" }}
                    """

                    # Query AI
                    response_text = query_ai(prompt, image_paths=evidence["image_paths"])

                    try:
                        data = json.loads(response_text)
                        estimation = float(data.get("amount", 0))
                        reasoning = data.get("reasoning", "")
                    except:
                        estimation = 0
                        reasoning = "Failed to parse JSON"

                    # Calculate Stats
                    ground_truth = float(claim.ground_truth_amount or 0)
                    diff = abs(estimation - ground_truth)
                    error_rate = (diff / ground_truth * 100) if ground_truth > 0 else 0

                    iterations.append(
                        {
                            "step": i,
                            "estimate": estimation,
                            "ground_truth": ground_truth,
                            "difference": diff,
                            "error_rate": error_rate,
                            "reasoning": reasoning,
                        }
                    )
                    current_estimate = estimation

                # Add to results
                claim.estimated_amount = current_estimate
                claim.ai_reasoning = iterations
                if iterations:
                    claim.ai_explanation = iterations[-1].get("reasoning", "")
                claim.status = "SUCCESS"
                claim.save()

                results.append(
                    {
                        "tracking_number": t_id,
                        "ground_truth": claim.ground_truth_amount,
                        "final_estimate": current_estimate,
                        "iterations": iterations,
                    }
                )

            except Claim.DoesNotExist:
                results.append({"tracking_number": t_id, "error": "ID not found in DB"})
            except Exception as e:
                results.append({"tracking_number": t_id, "error": str(e)})

        return Response(results)
