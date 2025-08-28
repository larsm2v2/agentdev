// Admin Dashboard UI
// Renders a simple admin panel into #function-cards-container
(function () {
  function el(id) {
    return document.getElementById(id);
  }

  async function fetchFunctions() {
    try {
      const res = await fetch("/api/functions");
      if (!res.ok) throw new Error("Failed to fetch functions");
      return await res.json();
    } catch (err) {
      console.warn(
        "AdminDashboard: API /api/functions unavailable, using mock",
        err
      );
      return {
        shelving: { enabled: false, processedToday: 0 },
        cataloging: { enabled: false, historicalCount: 0 },
        reclassification: { enabled: false },
        workflows: { enabled: true },
      };
    }
  }

  function renderFunctionCard(name, info) {
    const wrapper = document.createElement("div");
    wrapper.className = "bg-white rounded-lg shadow p-4";
    wrapper.style.minHeight = "120px";

    const title = document.createElement("div");
    title.className = "flex items-center justify-between mb-3";

    const h = document.createElement("h4");
    h.textContent = name;
    h.className = "text-lg font-semibold";

    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.checked = !!info.enabled;
    toggle.addEventListener("change", async () => {
      toggle.disabled = true;
      try {
        const res = await fetch(`/api/${name}/toggle`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: toggle.checked }),
        });
        if (!res.ok) {
          console.warn("Toggle API failed", res.status);
          // revert
          toggle.checked = !toggle.checked;
        }
      } catch (e) {
        console.warn("Toggle network error", e);
        toggle.checked = !toggle.checked;
      } finally {
        toggle.disabled = false;
      }
    });

    title.appendChild(h);
    title.appendChild(toggle);

    wrapper.appendChild(title);

    const body = document.createElement("div");
    body.className = "text-sm text-gray-600";

    if (name === "cataloging") {
      const startBtn = document.createElement("button");
      startBtn.className = "bg-green-600 text-white px-3 py-1 rounded mr-2";
      startBtn.textContent = "Start Cataloging";

      const jobIdSpan = document.createElement("div");
      jobIdSpan.className = "text-sm text-gray-700 mt-2";

      const progressBar = document.createElement("div");
      progressBar.className = "w-full bg-gray-200 rounded mt-2";
      progressBar.style.display = "none";
      const progressInner = document.createElement("div");
      progressInner.className = "bg-green-500 text-xs text-white rounded";
      progressInner.style.width = "0%";
      progressInner.style.padding = "4px 0";
      progressBar.appendChild(progressInner);

      const countsLine = document.createElement("div");
      countsLine.className = "text-sm text-gray-600 mt-2";
      countsLine.textContent = "";

      const errorLine = document.createElement("div");
      errorLine.className = "text-sm text-red-600 mt-2";
      errorLine.textContent = "";

      let ws = null;

      function connectWebSocket(job_id) {
        // Attempt to connect to the job-specific websocket
        const scheme = window.location.protocol === "https:" ? "wss" : "ws";
        const url = `${scheme}://${window.location.host}/api/ws/jobs/${job_id}`;
        try {
          ws = new WebSocket(url);
        } catch (e) {
          console.warn("WebSocket creation failed", e);
          return;
        }

        ws.addEventListener("open", () => {
          progressBar.style.display = "";
          jobIdSpan.textContent = "Job ID: " + job_id;
          // enable cancel button when connected
          try {
            cancelBtn.disabled = false;
          } catch (e) {}
        });

        ws.addEventListener("message", (evt) => {
          try {
            const data = JSON.parse(evt.data);
            // Data may include processed_count, total_count, status, error
            const processed = data.processed_count || data.processed || 0;
            const total = data.total_count || data.total || 1;
            const percent =
              total > 0 ? Math.round((processed / total) * 100) : 0;
            progressInner.style.width = Math.min(100, percent) + "%";
            progressInner.textContent = percent + "%";
            countsLine.textContent = `Processed: ${processed} / ${total}`;
            if (
              data.error ||
              data.error_message ||
              (data.results && data.results.error)
            ) {
              errorLine.textContent =
                data.error ||
                data.error_message ||
                (data.results && data.results.error) ||
                "";
            } else {
              errorLine.textContent = "";
            }
            if (
              data.status === "completed" ||
              data.status === "cancelled" ||
              percent >= 100
            ) {
              startBtn.disabled = false;
              if (ws) ws.close();
              try {
                cancelBtn.disabled = true;
              } catch (e) {}
              jobIdSpan.textContent = `Job ${
                data.status || "completed"
              }: ${job_id}`;
            }
          } catch (e) {
            console.warn("Invalid WS message", e);
          }
        });

        ws.addEventListener("close", () => {
          // closed
        });

        ws.addEventListener("error", (e) => {
          console.warn("WebSocket error", e);
        });
      }

      startBtn.addEventListener("click", async () => {
        startBtn.disabled = true;
        // Basic prompt for date range
        const startDate = prompt("Start date (YYYY-MM-DD)", "2020-01-01");
        const endDate = prompt(
          "End date (YYYY-MM-DD)",
          new Date().toISOString().slice(0, 10)
        );
        if (!startDate || !endDate) {
          alert("Start and end dates are required");
          startBtn.disabled = false;
          return;
        }
        try {
          const res = await fetch("/api/functions/cataloging/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              start_date: startDate,
              end_date: endDate,
              batch_size: 50,
            }),
          });
          if (!res.ok) {
            const txt = await res.text();
            alert("Failed to start cataloging: " + txt);
            startBtn.disabled = false;
          } else {
            const json = await res.json();
            const job_id =
              (json.job && json.job.job_id) ||
              json.job_id ||
              json.jobId ||
              null;
            if (job_id) {
              jobIdSpan.textContent = "Job ID: " + job_id;
              // start websocket for realtime updates
              connectWebSocket(job_id);
            } else {
              // fallback: show returned object
              jobIdSpan.textContent = "Started: " + JSON.stringify(json);
            }
          }
        } catch (err) {
          alert("Network error starting cataloging");
          console.error(err);
          startBtn.disabled = false;
        }
      });

      const cancelBtn = document.createElement("button");
      cancelBtn.className = "bg-red-600 text-white px-3 py-1 rounded ml-2";
      cancelBtn.textContent = "Cancel Job";
      cancelBtn.disabled = true;

      cancelBtn.addEventListener("click", async () => {
        const current = jobIdSpan.textContent.replace("Job ID: ", "").trim();
        if (!current) return;
        cancelBtn.disabled = true;
        try {
          const res = await fetch(`/api/jobs/${current}/cancel`, {
            method: "POST",
          });
          if (!res.ok) {
            const txt = await res.text();
            errorLine.textContent = "Cancel failed: " + txt;
            cancelBtn.disabled = false;
          } else {
            const j = await res.json();
            errorLine.textContent = j.message || "Cancellation requested";
          }
        } catch (e) {
          errorLine.textContent = "Network error cancelling job";
          cancelBtn.disabled = false;
        }
      });

      body.appendChild(startBtn);
      body.appendChild(cancelBtn);
      body.appendChild(jobIdSpan);
      body.appendChild(progressBar);
      body.appendChild(countsLine);
      body.appendChild(errorLine);
    }

    // Add some detail lines
    const details = document.createElement("div");
    details.innerHTML = `<div>Enabled: ${info.enabled ? "Yes" : "No"}</div>`;
    body.appendChild(details);

    wrapper.appendChild(body);

    return wrapper;
  }

  async function render() {
    const container = el("function-cards-container");
    if (!container) return;
    container.innerHTML = "";

    const functions = await fetchFunctions();

    const grid = document.createElement("div");
    grid.className =
      "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8";

    for (const [name, info] of Object.entries(functions)) {
      const card = renderFunctionCard(name, info);
      grid.appendChild(card);
    }

    container.appendChild(grid);
  }

  // Expose a global loader for manual refresh
  window.AdminDashboard = {
    render,
    refresh: render,
  };

  // Auto-render after DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
