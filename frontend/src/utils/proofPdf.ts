import { jsPDF } from "jspdf";

import type { RunStoreState } from "../run/store";

function line(doc: jsPDF, label: string, value: string, y: number): number {
  doc.setFont("helvetica", "bold");
  doc.text(label, 14, y);
  doc.setFont("helvetica", "normal");
  const wrapped = doc.splitTextToSize(value, 182);
  doc.text(wrapped, 14, y + 5);
  return y + 5 + wrapped.length * 5 + 4;
}

export function buildProofPacketPdf(state: RunStoreState): jsPDF {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const action = state.proposal?.request.action;
  const generatedAt = new Date().toISOString();

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text("TOSCO Proof Packet", 14, 18);

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.text("SANDBOX — demonstration export only", 14, 26);

  let y = 34;
  y = line(doc, "Run ID", state.runId ?? "-", y);
  y = line(doc, "Scenario", state.scenario ?? "-", y);
  y = line(doc, "Workflow", state.workflow ?? "-", y);
  y = line(
    doc,
    "Proposer",
    state.proposal?.request.agent_id ?? "reference-ap-agent",
    y
  );

  if (action) {
    y = line(
      doc,
      "Proposed action",
      `${action.vendor_id} | ${action.amount} ${action.currency} | bank ••••${action.bank_account_last4}`,
      y
    );
  }

  y = line(
    doc,
    "Evidence refs",
    (state.proposal?.request.evidence_refs ?? []).join(", ") || "-",
    y
  );

  doc.setFont("helvetica", "bold");
  doc.text("Gate outcomes", 14, y);
  y += 6;
  doc.setFont("helvetica", "normal");

  for (const gate of state.gates) {
    if (gate.status === "idle") {
      continue;
    }
    const gateLine = `${gate.id}: ${gate.status}${gate.reasonCode ? ` (${gate.reasonCode})` : ""}`;
    const wrapped = doc.splitTextToSize(gateLine, 182);
    doc.text(wrapped, 14, y);
    y += wrapped.length * 5 + 2;
    if (y > 270) {
      break;
    }
  }

  y += 2;
  y = line(doc, "Decision", state.decision?.value ?? "Pending", y);
  y = line(doc, "Decision reason", state.decision?.humanReason ?? "-", y);
  y = line(doc, "Chain hash", state.proof?.chainHash ?? "-", y);
  y = line(
    doc,
    "Verification",
    state.verification
      ? state.verification.verified
        ? "VERIFIED"
        : "FAILED"
      : "Not verified in this session",
    y
  );
  y = line(doc, "Generated at", generatedAt, y);
  const reviewerLine =
    state.review?.resolved && state.review.reviewerId
      ? `${state.review.reviewerId} | ${state.review.action ?? "REVIEWED"}`
      : "Not assigned (sandbox demo)";
  y = line(doc, "Reviewer", reviewerLine, y);

  return doc;
}

export function downloadProofPacketPdf(state: RunStoreState): void {
  const doc = buildProofPacketPdf(state);
  const runId = state.runId ?? "run";
  doc.save(`tosco-proof-${runId}.pdf`);
}
