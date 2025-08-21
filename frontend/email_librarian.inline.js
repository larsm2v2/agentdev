function emailLibrarianApp() {
  return {
    apiBaseUrl: "/api",
    showTab: "workflows",
    isLoading: false,
    connectionStatus: "connected",
    notifications: [],
    functions: {
      shelving: {
        enabled: false,
        processedToday: 127,
        avgSpeed: 15,
        config: {
          interval: 2,
          batchSize: 25,
          autoArchive: true,
          smartThrottling: true,
          priorityMode: true,
        },
        recentActivity: [
          {
            id: 1,
            action: "Processed 15 new emails",
            timestamp: "2 minutes ago",
          },
        ],
      },
      workflows: {
        name: "Workflows",
        endpoint: "/workflows",
        status: "active",
        activeWorkflows: [
          {
            id: "wf_1",
            name: "Daily Email Summary",
            description: "Creates a daily digest of important emails",
            active: true,
            executions: 24,
            lastRun: "2 hours ago",
            schedule: "Daily at 8:00 AM",
          },
        ],
        executionHistory: [
          {
            id: "ex_1",
            workflowName: "Daily Email Summary",
            status: "success",
            timestamp: "2 hours ago",
            details: "Processed 124 emails, created summary report",
            showDetails: false,
          },
        ],
      },
    },

    init() {
      console.log("Email Librarian App initialized");
    },

    toggleExecutionDetails(executionId) {
      const execution = this.functions.workflows.executionHistory.find(
        (e) => e.id === executionId
      );
      if (execution) {
        execution.showDetails = !execution.showDetails;
      }
    },
  };
}

function enhancedEmailLibrarianApp() {
  return {
    ...emailLibrarianApp(),
    init() {
      console.log("Enhanced Email Librarian App initialized");
    },
  };
}
