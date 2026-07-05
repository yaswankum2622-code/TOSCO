import type { WorkflowMetadata } from "../api/types";

interface WorkflowStripProps {
  workflows: WorkflowMetadata[];
  activeScenario: string | null;
}

function WorkflowStrip({ workflows, activeScenario }: WorkflowStripProps) {
  return (
    <section className="panel" aria-labelledby="workflow-strip-heading">
      <div className="panel__header">
        <h2 id="workflow-strip-heading">Workflow Strip</h2>
        <span className="mono-label">{activeScenario ? `Live run: ${activeScenario}` : "Ready"}</span>
      </div>
      {workflows.length === 0 ? (
        <p className="empty-state">Workflow metadata will appear when the backend registry is available.</p>
      ) : (
        <div className="workflow-strip-list">
          {workflows.map((workflow) => (
            <article key={workflow.workflow_id} className="workflow-strip__card">
              <div className="workflow-strip__topline">
                <h3>{workflow.workflow_name}</h3>
                <span className="mono-label">{workflow.workflow_id}</span>
              </div>
              <div className="workflow-strip__metrics">
                <div>
                  <span className="kv-label">Gates</span>
                  <span className="kv-value">{workflow.gates_to_run.length}</span>
                </div>
                <div>
                  <span className="kv-label">Tools</span>
                  <span className="kv-value">{workflow.tools_to_call.length}</span>
                </div>
                <div>
                  <span className="kv-label">Adapter</span>
                  <span className="kv-value">{workflow.execution_adapter}</span>
                </div>
              </div>
              <div className="workflow-strip__badges">
                <span className="badge badge--seal">Deterministic Gates</span>
                <span className="badge">Sandbox Rail</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default WorkflowStrip;
