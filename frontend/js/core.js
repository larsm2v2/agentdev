function emailLibrarianApp() {
  // Detect environment and set API base URL
  const isDev = window.location.port === "8001";
  const apiBaseUrl = isDev ? "http://localhost:8000" : "";

  return {
    apiBaseUrl: apiBaseUrl,
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
          interval: 2, // More frequent processing (2 minutes)
          batchSize: 25, // Larger batches for efficiency
          autoArchive: true,
          smartThrottling: true, // Only process when new emails exist
          priorityMode: true, // Process high-priority emails first
        },
        recentActivity: [
          {
            id: 1,
            action: "Processed 15 new emails",
            timestamp: "2 minutes ago",
          },
          {
            id: 2,
            action: "Applied 12 categories",
            timestamp: "5 minutes ago",
          },
          {
            id: 3,
            action: "Auto-archived 8 emails",
            timestamp: "8 minutes ago",
          },
        ],
      },
      cataloging: {
        enabled: false,
        historicalCount: 2847,
        processingRate: 120,
        config: {
          startDate: "",
          endDate: "",
          batchSize: 50,
        },
        progress: 0,
        processed: 0,
        remaining: 2847,
      },
      reclassification: {
        enabled: false,
        labelsCount: 23,
        reclassifiedCount: 89,
        config: {
          sourceLabel: "",
          sourceLabels: [], // Array of selected labels
          selectedLabel: "", // Currently selected label to add
          operation: "combine", // "split" or "combine"
          newClassification: "", // New label name
          targetCategories: [],
        },
        results: [
          {
            id: 1,
            summary: "Reclassified 'work' emails",
            timestamp: "1 hour ago",
            processed: 45,
            changed: 12,
          },
          {
            id: 2,
            summary: "Updated 'personal' categories",
            timestamp: "3 hours ago",
            processed: 32,
            changed: 8,
          },
        ],
      },
      workflows: {
        enabled: true,
        activeCount: 2, // Only Priority Alerts + Weekly Digest
        executionsToday: 45,
        totalExecutions: 1247,
        successRate: 94,
        avgDuration: 2.3,
        activeWorkflows: [
          {
            id: "wf_001",
            name: "Email Auto-Classifier",
            description:
              "Automatically classify incoming emails using AI (DISABLED - Using Shelving Instead)",
            active: false, // Disabled in favor of shelving
            lastRun: "5 mins ago",
            executions: 234,
          },
          {
            id: "wf_002",
            name: "Priority Email Alerts",
            description: "Send notifications for high-priority emails",
            active: true,
            lastRun: "15 mins ago",
            executions: 89,
          },
          {
            id: "wf_003",
            name: "Weekly Email Digest",
            description: "Generate and send weekly email summaries",
            active: true, // Re-enabled for periodic reporting
            lastRun: "2 days ago",
            executions: 12,
          },
        ],
        executionHistory: [
          {
            id: "ex_001",
            workflowName: "Email Auto-Classifier",
            status: "success",
            timestamp: "2 mins ago",
            details: "Processed 15 emails, classified into 8 categories",
          },
          {
            id: "ex_002",
            workflowName: "Priority Email Alerts",
            status: "success",
            timestamp: "8 mins ago",
            details: "Sent 3 priority notifications",
          },
          {
            id: "ex_003",
            workflowName: "Email Auto-Classifier",
            status: "error",
            timestamp: "1 hour ago",
            details: "API rate limit exceeded, retrying in 5 minutes",
          },
        ],
      },
    },
    stats: {
      totalProcessed: 3240,
      categoriesCount: 43,
      avgSpeed: 25,
      accuracyRate: 94,
    },
    availableLabels: [
      { name: "work", count: 234 },
      { name: "personal", count: 156 },
      { name: "promotions", count: 89 },
      { name: "newsletters", count: 201 },
    ],
    availableCategories: [
      "work",
      "personal",
      "family & friends",
      "job alerts",
      "banking",
      "travel",
      "shopping",
      "social media",
      "newsletters",
      "promotions",
    ],

    init() {
      // Initialize dates
      const today = new Date();
      const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
      this.functions.cataloging.config.endDate = today
        .toISOString()
        .split("T")[0];
      this.functions.cataloging.config.startDate = lastWeek
        .toISOString()
        .split("T")[0];

      // Load persisted states
      this.loadStates();

      // Fetch current labels for reclassification
      this.fetchCurrentLabels();

      // Start monitoring active functions
      this.startMonitoring();
    },

    toggleFunction(functionName) {
      console.log(
        `Toggling ${functionName}:`,
        this.functions[functionName].enabled
      );
      this.saveStates();

      if (this.functions[functionName].enabled) {
        this.startFunction(functionName);
      } else {
        this.stopFunction(functionName);
      }
    },

    startFunction(functionName) {
      console.log(`Starting ${functionName} function`);
      // Here you would make API calls to start the specific function
    },

    stopFunction(functionName) {
      console.log(`Stopping ${functionName} function`);
      // Here you would make API calls to stop the specific function
    },

    getActiveFunctionsCount() {
      return Object.values(this.functions).filter((f) => f.enabled).length;
    },

    startCataloging() {
      if (!this.functions.cataloging.enabled) {
        this.functions.cataloging.enabled = true;
        this.toggleFunction("cataloging");
      }
      console.log("Starting cataloging process...");
      // Here you would start the cataloging process with the configured parameters
    },

    startReclassification() {
      if (!this.functions.reclassification.enabled) {
        this.functions.reclassification.enabled = true;
        this.toggleFunction("reclassification");
      }
      console.log("Starting reclassification process...");
      // Here you would start the reclassification process
    },

    openN8nDashboard() {
      window.open("http://localhost:5678", "_blank");
    },

    refreshWorkflows() {
      console.log("Refreshing workflows...");
      // Here you would make API calls to refresh workflow data
    },

    // Reclassification Methods
    async fetchCurrentLabels() {
      console.log("🏷️ Fetching current Gmail labels...");

      try {
        const response = await fetch(`${this.apiBaseUrl}/api/gmail/labels`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        this.availableLabels = data.labels || [];

        console.log(`✅ Fetched ${this.availableLabels.length} Gmail labels`);

        // Store in localStorage for caching
        localStorage.setItem(
          "gmailLabels",
          JSON.stringify(this.availableLabels)
        );
        localStorage.setItem("gmailLabelsTimestamp", Date.now().toString());

        return this.availableLabels;
      } catch (error) {
        console.error("❌ Failed to fetch Gmail labels:", error);

        // Fallback to cached data if available
        const cachedLabels = localStorage.getItem("gmailLabels");
        const cachedTimestamp = localStorage.getItem("gmailLabelsTimestamp");

        if (cachedLabels && cachedTimestamp) {
          const cacheAge = Date.now() - parseInt(cachedTimestamp);
          // Use cache if less than 1 hour old
          if (cacheAge < 3600000) {
            this.availableLabels = JSON.parse(cachedLabels);
            console.log(
              `📋 Using cached Gmail labels (${this.availableLabels.length} labels)`
            );
            return this.availableLabels;
          }
        }

        // Ultimate fallback to mock data
        console.log("📋 Using fallback mock data");
        const mockLabels = [
          { name: "work", count: 234, color: "#4285f4" },
          { name: "personal", count: 156, color: "#ea4335" },
          { name: "promotions", count: 89, color: "#fbbc04" },
          { name: "newsletters", count: 201, color: "#34a853" },
          { name: "banking", count: 67, color: "#9aa0a6" },
          { name: "travel", count: 34, color: "#ff6d01" },
          { name: "shopping", count: 123, color: "#ab47bc" },
          { name: "social", count: 45, color: "#00acc1" },
          { name: "family", count: 78, color: "#7cb342" },
          { name: "receipts", count: 92, color: "#f57c00" },
        ];

        this.availableLabels = mockLabels;
        return mockLabels;
      }
    },

    addLabelToReclassification(labelName) {
      const config = this.functions.reclassification.config;
      if (!config.sourceLabels) {
        config.sourceLabels = [];
      }

      if (!config.sourceLabels.includes(labelName) && labelName) {
        config.sourceLabels.push(labelName);
        console.log(`Added label: ${labelName}`);
      }
    },

    removeLabelFromReclassification(labelName) {
      const config = this.functions.reclassification.config;
      if (config.sourceLabels) {
        config.sourceLabels = config.sourceLabels.filter(
          (label) => label !== labelName
        );
        console.log(`Removed label: ${labelName}`);
      }
    },

    executeReclassification() {
      const config = this.functions.reclassification.config;

      if (!config.sourceLabels || config.sourceLabels.length === 0) {
        alert("Please select at least one source label");
        return;
      }

      if (!config.newClassification || config.newClassification.trim() === "") {
        alert("Please enter a new classification name");
        return;
      }

      console.log("Executing reclassification:", {
        sourceLabels: config.sourceLabels,
        operation: config.operation,
        newClassification: config.newClassification,
      });

      // Simulate reclassification process
      const totalEmails = config.sourceLabels.reduce((sum, labelName) => {
        const label = this.availableLabels.find((l) => l.name === labelName);
        return sum + (label ? label.count : 0);
      }, 0);

      // Add to results
      const newResult = {
        id: Date.now(),
        summary: `${
          config.operation === "split" ? "Split" : "Combined"
        } ${config.sourceLabels.join(", ")} → ${config.newClassification}`,
        timestamp: "just now",
        processed: totalEmails,
        changed: Math.floor(totalEmails * 0.8), // Simulate 80% success rate
        operation: config.operation,
        sourceLabels: [...config.sourceLabels],
        newLabel: config.newClassification,
      };

      this.functions.reclassification.results.unshift(newResult);

      // Keep only last 10 results
      if (this.functions.reclassification.results.length > 10) {
        this.functions.reclassification.results =
          this.functions.reclassification.results.slice(0, 10);
      }

      // Update stats
      this.functions.reclassification.reclassifiedCount += newResult.changed;

      // Reset form
      config.sourceLabels = [];
      config.newClassification = "";
      config.selectedLabel = "";
    },

    toggleWorkflow(workflowId) {
      console.log(`Toggling workflow ${workflowId}`);
      const workflow = this.functions.workflows.activeWorkflows.find(
        (w) => w.id === workflowId
      );
      if (workflow) {
        workflow.active = !workflow.active;
        // Here you would make API call to n8n to start/stop the workflow
      }
    },

    executeWorkflow(workflowId) {
      console.log(`Executing workflow ${workflowId}`);
      // Here you would make API call to n8n to execute the workflow
      const workflow = this.functions.workflows.activeWorkflows.find(
        (w) => w.id === workflowId
      );
      if (workflow) {
        workflow.lastRun = "just now";
        workflow.executions += 1;

        // Add to execution history
        this.functions.workflows.executionHistory.unshift({
          id: `ex_${Date.now()}`,
          workflowName: workflow.name,
          status: "success",
          timestamp: "just now",
          details: "Manual execution completed successfully",
        });

        // Keep only last 10 executions
        if (this.functions.workflows.executionHistory.length > 10) {
          this.functions.workflows.executionHistory =
            this.functions.workflows.executionHistory.slice(0, 10);
        }
      }
    },

    exportData() {
      console.log("Exporting data...");
      // Here you would implement data export functionality
    },

    dismissNotification(notificationId) {
      this.notifications = this.notifications.filter(
        (n) => n.id !== notificationId
      );
    },

    saveStates() {
      const states = {
        functions: this.functions,
        showTab: this.showTab,
      };
      localStorage.setItem("emailLibrarianStates", JSON.stringify(states));
    },

    loadStates() {
      const saved = localStorage.getItem("emailLibrarianStates");
      if (saved) {
        const states = JSON.parse(saved);
        this.functions = { ...this.functions, ...states.functions };
        this.showTab = states.showTab || "workflows";
      }
    },

    startMonitoring() {
      // Simulate real-time updates
      setInterval(() => {
        if (this.functions.shelving.enabled) {
          this.functions.shelving.processedToday += Math.floor(
            Math.random() * 3
          );
        }
        if (
          this.functions.cataloging.enabled &&
          this.functions.cataloging.progress < 100
        ) {
          this.functions.cataloging.progress += Math.floor(Math.random() * 2);
          this.functions.cataloging.processed += Math.floor(Math.random() * 5);
          this.functions.cataloging.remaining = Math.max(
            0,
            this.functions.cataloging.remaining - Math.floor(Math.random() * 5)
          );
        }
      }, 5000);
    },
  };
}
