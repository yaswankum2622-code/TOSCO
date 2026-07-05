import { useState } from "react";

import { ApiError, apiClient } from "../../api/client";
import type { RunStoreState } from "../../run/store";

interface ReviewerCardProps {
  state: RunStoreState;
  loading: boolean;
  onReviewerIdChange: (reviewerId: string) => void;
  onReviewSubmitted: () => void;
  onError: (message: string) => void;
}

function ReviewerCard({
  state,
  loading,
  onReviewerIdChange,
  onReviewSubmitted,
  onError
}: ReviewerCardProps) {
  const [submitting, setSubmitting] = useState(false);
  const review = state.review;

  if (review?.required !== true || review.resolved) {
    return null;
  }

  async function submit(action: "APPROVED" | "REJECTED") {
    if (state.runId === null) {
      return;
    }

    const reviewerId = review?.reviewerId.trim() ?? "";
    if (!reviewerId) {
      onError("Enter a reviewer name or ID before submitting review.");
      return;
    }

    setSubmitting(true);
    onError("");

    try {
      await apiClient.submitReview(state.runId, {
        reviewer_id: reviewerId,
        action
      });
      onReviewSubmitted();
    } catch (submitError) {
      onError(submitError instanceof ApiError ? submitError.message : "Review submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel right-card reviewer-card" aria-labelledby="reviewer-card-heading" data-testid="reviewer-card">
      <div className="panel__header">
        <h2 id="reviewer-card-heading">Human Review</h2>
        <span className="status-pill status-pill--warning">PAUSED</span>
      </div>
      <p className="reviewer-card__reason">{review.reason}</p>
      <label className="reviewer-card__field">
        <span>Reviewer name / ID</span>
        <input
          className="mono-value"
          value={review.reviewerId}
          onChange={(event) => onReviewerIdChange(event.target.value)}
          disabled={loading || submitting}
          data-testid="reviewer-id-input"
        />
      </label>
      <div className="reviewer-card__actions">
        <button
          type="button"
          className="primary-button reviewer-card__approve"
          disabled={loading || submitting}
          onClick={() => void submit("APPROVED")}
          data-testid="review-approve-button"
        >
          Approve
        </button>
        <button
          type="button"
          className="ghost-button reviewer-card__reject"
          disabled={loading || submitting}
          onClick={() => void submit("REJECTED")}
          data-testid="review-reject-button"
        >
          Reject
        </button>
      </div>
    </section>
  );
}

export default ReviewerCard;
