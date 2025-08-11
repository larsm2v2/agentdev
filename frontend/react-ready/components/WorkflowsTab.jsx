import React from "react";

const WorkflowsTab = ({
  showTab,
  functions,
  openN8nDashboard,
  refreshWorkflows,
  toggleWorkflow,
  executeWorkflow,
}) => {
  if (showTab !== "workflows") return null;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <i className="fas fa-project-diagram text-2xl text-orange-500 mr-3"></i>
          <h2 className="text-2xl font-bold text-gray-800">
            Workflows - n8n Integration & Automation
          </h2>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={openN8nDashboard}
            className="btn bg-orange-600 text-white px-4 py-2 rounded-md hover:bg-orange-700"
          >
            <i className="fas fa-external-link-alt mr-2"></i>Open n8n
          </button>
          <button
            onClick={refreshWorkflows}
            className="btn bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700"
          >
            <i className="fas fa-refresh mr-2"></i>Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className="text-lg font-semibold mb-4">Active Workflows</h3>
          <div className="space-y-3 max-h-64 overflow-y-auto custom-scrollbar">
            {functions.workflows.activeWorkflows.map((workflow) => (
              <div
                key={workflow.id}
                className="workflow-item border border-gray-200 rounded-lg p-4 hover:bg-gray-50"
              >
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-medium text-gray-900">{workflow.name}</h4>
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      workflow.active
                        ? "bg-green-100 text-green-800"
                        : "bg-red-100 text-red-800"
                    }`}
                  >
                    {workflow.active ? "Active" : "Inactive"}
                  </span>
                </div>
                <p className="text-sm text-gray-600 mb-2">
                  {workflow.description}
                </p>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>Last run: {workflow.lastRun}</span>
                  <span>Executions: {workflow.executions}</span>
                </div>
                <div className="flex space-x-2 mt-3">
                  <button
                    onClick={() => toggleWorkflow(workflow.id)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      workflow.active
                        ? "bg-red-100 text-red-700 hover:bg-red-200"
                        : "bg-green-100 text-green-700 hover:bg-green-200"
                    }`}
                  >
                    <i
                      className={`${
                        workflow.active ? "fas fa-pause" : "fas fa-play"
                      } mr-1`}
                    ></i>
                    {workflow.active ? "Pause" : "Start"}
                  </button>
                  <button
                    onClick={() => executeWorkflow(workflow.id)}
                    className="px-3 py-1 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded text-xs font-medium transition-colors"
                  >
                    <i className="fas fa-play-circle mr-1"></i>Execute
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-4">
            Workflow Execution History
          </h3>
          <div className="space-y-3 max-h-64 overflow-y-auto custom-scrollbar">
            {functions.workflows.executionHistory.map((execution) => (
              <div
                key={execution.id}
                className={`execution-item border-l-4 pl-4 py-2 ${
                  execution.status === "success"
                    ? "border-green-500"
                    : execution.status === "error"
                    ? "border-red-500"
                    : "border-yellow-500"
                }`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-sm font-medium">
                      {execution.workflowName}
                    </p>
                    <p className="text-xs text-gray-500">
                      {execution.timestamp}
                    </p>
                  </div>
                  <span
                    className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                      execution.status === "success"
                        ? "bg-green-100 text-green-800"
                        : execution.status === "error"
                        ? "bg-red-100 text-red-800"
                        : "bg-yellow-100 text-yellow-800"
                    }`}
                  >
                    {execution.status}
                  </span>
                </div>
                <p className="text-xs text-gray-600 mt-1">
                  {execution.details}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center">
            <i className="fas fa-play-circle text-2xl text-green-500 mr-3"></i>
            <div>
              <p className="text-sm text-gray-600">Total Executions</p>
              <p className="text-xl font-bold">
                {functions.workflows.totalExecutions}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center">
            <i className="fas fa-check-circle text-2xl text-blue-500 mr-3"></i>
            <div>
              <p className="text-sm text-gray-600">Success Rate</p>
              <p className="text-xl font-bold">
                {functions.workflows.successRate}%
              </p>
            </div>
          </div>
        </div>
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center">
            <i className="fas fa-clock text-2xl text-purple-500 mr-3"></i>
            <div>
              <p className="text-sm text-gray-600">Avg. Duration</p>
              <p className="text-xl font-bold">
                {functions.workflows.avgDuration}s
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkflowsTab;
