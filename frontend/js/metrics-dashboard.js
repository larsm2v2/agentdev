/**
 * Integrated Metrics Dashboard for Email Librarian
 * This integrates with the main FastAPI server and uses existing API endpoints
 */

class IntegratedMetricsDashboard {
  constructor() {
    this.connected = false;
    this.charts = {};
    this.performanceData = [];
    this.apiData = [];
    this.maxDataPoints = 20;
    this.refreshInterval = 5000; // 5 seconds
    this.apiBaseUrl = this.detectApiBaseUrl();

    this.initializeCharts();
    this.startMetricsPolling();
    this.setupEventListeners();
  }

  detectApiBaseUrl() {
    // Detect if we're in development or production
    const isDev = window.location.port === "8001";
    return isDev ? "http://localhost:8000" : "";
  }

  initializeCharts() {
    // Performance Chart
    const performanceCtx = document
      .getElementById("performance-chart")
      .getContext("2d");
    this.charts.performance = new Chart(performanceCtx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Processing Time (seconds)",
            data: [],
            borderColor: "rgb(59, 130, 246)",
            backgroundColor: "rgba(59, 130, 246, 0.1)",
            tension: 0.4,
            fill: true,
          },
          {
            label: "Emails/Hour",
            data: [],
            borderColor: "rgb(34, 197, 94)",
            backgroundColor: "rgba(34, 197, 94, 0.1)",
            tension: 0.4,
            yAxisID: "y1",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top",
          },
          title: {
            display: false,
          },
        },
        scales: {
          y: {
            type: "linear",
            display: true,
            position: "left",
          },
          y1: {
            type: "linear",
            display: true,
            position: "right",
            grid: {
              drawOnChartArea: false,
            },
          },
        },
      },
    });

    // API Efficiency Chart
    const apiCtx = document.getElementById("api-chart").getContext("2d");
    this.charts.api = new Chart(apiCtx, {
      type: "doughnut",
      data: {
        labels: ["Calls Made", "Calls Saved"],
        datasets: [
          {
            data: [0, 0],
            backgroundColor: [
              "rgba(239, 68, 68, 0.8)",
              "rgba(34, 197, 94, 0.8)",
            ],
            borderColor: ["rgb(239, 68, 68)", "rgb(34, 197, 94)"],
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
          },
        },
      },
    });
  }

  async fetchMetrics() {
    try {
      this.updateConnectionStatus("connected");

      // Fetch metrics from existing API endpoints
      const [healthResponse, analyticsResponse, cacheResponse] =
        await Promise.all([
          fetch(`${this.apiBaseUrl}/health`),
          fetch(`${this.apiBaseUrl}/api/analytics/overview`).catch(() => null),
          fetch(`${this.apiBaseUrl}/api/cache/health`).catch(() => null),
        ]);

      const health = await healthResponse.json();
      const analytics = analyticsResponse
        ? await analyticsResponse.json()
        : null;
      const cache = cacheResponse ? await cacheResponse.json() : null;

      // Combine data from different sources
      const metrics = this.combineMetrics(health, analytics, cache);

      this.updateDashboard(metrics);
    } catch (error) {
      console.error("Error fetching metrics:", error);
      this.updateConnectionStatus("disconnected");
      this.updateDashboard(this.getFallbackMetrics());
    }
  }

  combineMetrics(health, analytics, cache) {
    const now = new Date();

    return {
      timestamp: now.toISOString(),
      health: {
        status: health?.status || "unknown",
        uptime_hours: this.calculateUptime(),
        redis_status: cache ? "connected" : "disconnected",
        active_websocket_connections: 0,
      },
      performance: {
        avg_processing_time_seconds: analytics?.avg_processing_time || 0,
        emails_processed_last_hour: analytics?.recent_activity?.length || 0,
        total_emails_processed_today: analytics?.total_processed || 0,
        processing_speed_trend: "stable",
        peak_performance_today: analytics?.peak_performance || 0,
      },
      api_efficiency: {
        api_calls_made: analytics?.api_calls_made || 0,
        api_calls_saved: analytics?.api_calls_saved || 0,
        efficiency_percentage: analytics?.efficiency_percentage || 0,
        batch_operations_today: analytics?.batch_operations || 0,
        rate_limit_hits: 0,
        average_batch_size: analytics?.avg_batch_size || 0,
      },
      processing: {
        total_emails_processed: analytics?.total_processed || 0,
        success_rate_percentage: analytics?.success_rate || 100,
        successful_categorizations: analytics?.successful || 0,
        failed_categorizations: analytics?.failed || 0,
        category_distribution: analytics?.categories || {},
        average_categories_per_email: 1.5,
      },
      cache_status: {
        status: cache?.status || "unknown",
        label_cache_size: cache?.label_cache_size || 0,
        cache_hit_rate_percentage: cache?.hit_rate || 0,
        memory_usage_mb: cache?.memory_usage || 0,
      },
      recent_jobs: analytics?.recent_jobs || [],
    };
  }

  calculateUptime() {
    // Simple uptime calculation - in production this would come from the server
    const startTime = localStorage.getItem("app_start_time");
    if (!startTime) {
      localStorage.setItem("app_start_time", Date.now().toString());
      return 0;
    }

    const uptimeMs = Date.now() - parseInt(startTime);
    return Math.round((uptimeMs / (1000 * 60 * 60)) * 100) / 100; // Hours with 2 decimal places
  }

  startMetricsPolling() {
    // Initial fetch
    this.fetchMetrics();

    // Set up polling
    this.pollingInterval = setInterval(() => {
      this.fetchMetrics();
    }, this.refreshInterval);
  }

  updateConnectionStatus(status) {
    const statusEl = document.getElementById("connection-status");

    statusEl.className = `connection-status ${status}`;

    switch (status) {
      case "connected":
        statusEl.innerHTML = '<i class="fas fa-circle"></i> Connected';
        this.connected = true;
        break;
      case "connecting":
        statusEl.innerHTML =
          '<i class="fas fa-circle animate-pulse"></i> Connecting...';
        this.connected = false;
        break;
      case "disconnected":
        statusEl.innerHTML = '<i class="fas fa-circle"></i> Disconnected';
        this.connected = false;
        break;
    }
  }

  updateDashboard(metrics) {
    // Update timestamp
    const timestamp = new Date(metrics.timestamp);
    document.getElementById("last-update").textContent =
      timestamp.toLocaleTimeString();

    // Update system health overview
    this.updateSystemHealth(metrics.health);

    // Update performance metrics
    this.updatePerformanceMetrics(metrics.performance);

    // Update API metrics
    this.updateApiMetrics(metrics.api_efficiency);

    // Update cache status
    this.updateCacheStatus(metrics.cache_status);

    // Update processing statistics
    this.updateProcessingStats(metrics.processing);

    // Update recent jobs
    this.updateRecentJobs(metrics.recent_jobs);

    // Update charts
    this.updateCharts(metrics);
  }

  updateSystemHealth(health) {
    const statusEl = document.getElementById("system-status");

    // Update status
    statusEl.innerHTML = `<span class="status-indicator"></span>${health.status}`;
    const newIndicator = statusEl.querySelector(".status-indicator");

    switch (health.status) {
      case "healthy":
        newIndicator.className = "status-indicator status-healthy";
        break;
      case "degraded":
        newIndicator.className = "status-indicator status-warning";
        break;
      default:
        newIndicator.className = "status-indicator status-error";
    }

    // Update uptime
    document.getElementById(
      "system-uptime"
    ).textContent = `${health.uptime_hours}h`;
  }

  updatePerformanceMetrics(performance) {
    document.getElementById("emails-today").textContent =
      performance.total_emails_processed_today || 0;
    document.getElementById(
      "avg-processing"
    ).textContent = `${performance.avg_processing_time_seconds}s`;
    document.getElementById("emails-per-hour").textContent =
      performance.emails_processed_last_hour || 0;
    document.getElementById(
      "peak-performance"
    ).textContent = `${performance.peak_performance_today}s`;
    document.getElementById("processing-trend").textContent =
      performance.processing_speed_trend || "unknown";
  }

  updateApiMetrics(apiMetrics) {
    document.getElementById("api-calls-made").textContent =
      apiMetrics.api_calls_made || 0;
    document.getElementById("api-calls-saved").textContent =
      apiMetrics.api_calls_saved || 0;
    document.getElementById("batch-operations").textContent =
      apiMetrics.batch_operations_today || 0;
    document.getElementById("avg-batch-size").textContent =
      apiMetrics.average_batch_size || 0;
  }

  updateCacheStatus(cacheStatus) {
    document.getElementById("cache-status").textContent =
      cacheStatus.status || "unknown";
    document.getElementById("label-cache-size").textContent =
      cacheStatus.label_cache_size || 0;
    document.getElementById("cache-hit-rate").textContent = `${
      cacheStatus.cache_hit_rate_percentage || 0
    }%`;
    document.getElementById("cache-memory").textContent = `${
      cacheStatus.memory_usage_mb || 0
    } MB`;
  }

  updateProcessingStats(processing) {
    document.getElementById("success-rate").textContent = `${
      processing.success_rate_percentage || 100
    }%`;
  }

  updateRecentJobs(jobs) {
    const tbody = document.getElementById("recent-jobs");
    tbody.innerHTML = "";

    if (!jobs || jobs.length === 0) {
      const row = document.createElement("tr");
      row.innerHTML = `
                <td colspan="6" class="px-6 py-4 text-center text-gray-500">
                    No recent job activity
                </td>
            `;
      tbody.appendChild(row);
      return;
    }

    jobs.forEach((job) => {
      const row = document.createElement("tr");
      row.className = "hover:bg-gray-50";

      const statusBadge = this.getStatusBadge(job.status || "completed");
      const timestamp = new Date(
        job.timestamp || Date.now()
      ).toLocaleTimeString();

      row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${
                  job.job_id || "N/A"
                }</td>
                <td class="px-6 py-4 whitespace-nowrap">${statusBadge}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${
                  job.emails_processed || 0
                }</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${
                  job.duration_seconds || 0
                }s</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${
                  job.success_rate || 100
                }%</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${timestamp}</td>
            `;

      tbody.appendChild(row);
    });
  }

  getStatusBadge(status) {
    const badgeClass =
      status === "completed"
        ? "bg-green-100 text-green-800"
        : status === "failed"
        ? "bg-red-100 text-red-800"
        : "bg-yellow-100 text-yellow-800";

    return `<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${badgeClass}">${status}</span>`;
  }

  updateCharts(metrics) {
    const now = new Date().toLocaleTimeString();

    // Update performance chart
    this.performanceData.push({
      time: now,
      processingTime: metrics.performance.avg_processing_time_seconds,
      emailsPerHour: metrics.performance.emails_processed_last_hour,
    });

    if (this.performanceData.length > this.maxDataPoints) {
      this.performanceData.shift();
    }

    this.charts.performance.data.labels = this.performanceData.map(
      (d) => d.time
    );
    this.charts.performance.data.datasets[0].data = this.performanceData.map(
      (d) => d.processingTime
    );
    this.charts.performance.data.datasets[1].data = this.performanceData.map(
      (d) => d.emailsPerHour
    );
    this.charts.performance.update("none");

    // Update API efficiency chart
    this.charts.api.data.datasets[0].data = [
      metrics.api_efficiency.api_calls_made,
      metrics.api_efficiency.api_calls_saved,
    ];
    this.charts.api.update("none");
  }

  setupEventListeners() {
    // Refresh button
    document.getElementById("refresh-btn").addEventListener("click", () => {
      this.fetchMetrics();
    });

    // Handle page visibility change to pause/resume polling
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        clearInterval(this.pollingInterval);
      } else {
        this.startMetricsPolling();
      }
    });
  }

  getFallbackMetrics() {
    return {
      timestamp: new Date().toISOString(),
      health: {
        status: "unknown",
        uptime_hours: 0,
        redis_status: "disconnected",
      },
      performance: {
        avg_processing_time_seconds: 0,
        emails_processed_last_hour: 0,
        total_emails_processed_today: 0,
      },
      api_efficiency: {
        api_calls_made: 0,
        api_calls_saved: 0,
        efficiency_percentage: 0,
      },
      processing: { total_emails_processed: 0, success_rate_percentage: 100 },
      cache_status: {
        status: "unknown",
        label_cache_size: 0,
        cache_hit_rate_percentage: 0,
      },
      recent_jobs: [],
    };
  }

  destroy() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
    }
  }
}

// Initialize dashboard when page loads
document.addEventListener("DOMContentLoaded", () => {
  window.metricsdashboard = new IntegratedMetricsDashboard();
});

// Cleanup on page unload
window.addEventListener("beforeunload", () => {
  if (window.metricsDashboard) {
    window.metricsDashboard.destroy();
  }
});
