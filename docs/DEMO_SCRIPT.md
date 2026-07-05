# The $340,000 Wire You Did Not Send

"AI agents are starting to read invoices and initiate payments. That makes the agent itself an attack surface.

This is TOSCO: a clearance layer between AI agents and financial execution.

In the clean case, the AP agent proposes a $340,000 payment. Vultr Serverless Inference extracts structured fields. TOSCO seals the extraction, runs six deterministic gates, creates a Proof Packet, appends it to a SHA-256 ledger, issues a clearance token, and the Mock Bank accepts.

Now watch the attack. This invoice contains prompt injection and routes payment to an attacker account ending 0009. The naive agent proposes it. TOSCO blocks it because the typed bank suffix does not match the verified vendor master. No token is issued. The Mock Bank rejects execution.

The third case is harder: the forged bank-change chain is internally consistent. But TOSCO's Reality Gate checks outside the document chain. Bank ownership fails, the domain is too new, and logistics confirmation is missing. TOSCO freezes the payment.

The model extracts. Deterministic gates decide. Every decision becomes a verifiable Proof Packet.

Agents propose. TOSCO clears. Execution obeys. Audit proves."
