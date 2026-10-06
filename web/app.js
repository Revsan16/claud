(function () {
  "use strict";

  var jobsEl = document.getElementById("jobs");
  var emptyEl = document.getElementById("empty");
  var form = document.getElementById("job-form");
  var errEl = document.getElementById("form-error");
  var goBtn = document.getElementById("go");
  var viewer = document.getElementById("viewer");

  var current = { id: null, file: null, text: "" };
  var pollTimer = null;

  document.getElementById("year").textContent = new Date().getFullYear();

  var modeSel = document.getElementById("tamil_mode");
  var engWrap = document.getElementById("english-wrap");
  function syncMode() { engWrap.hidden = modeSel.value !== "verbatim"; }
  modeSel.addEventListener("change", syncMode);
  syncMode();

  var LABELS = {
    "tamil.txt": "Tamil",
    "english.txt": "English",
    "summary.md": "Summary",
    "tamil.srt": "Tamil .srt",
    "english.srt": "English .srt"
  };
  var ORDER = ["summary.md", "tamil.txt", "english.txt", "tamil.srt", "english.srt"];

  function hhmm(seconds) {
    if (!seconds) return "";
    var m = Math.floor(seconds / 60);
    var s = seconds % 60;
    if (m >= 60) return Math.floor(m / 60) + "h " + (m % 60) + "m";
    return m + "m " + (s < 10 ? "0" : "") + s + "s";
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  // ---- submitting -----------------------------------------------------

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    errEl.hidden = true;
    goBtn.disabled = true;
    goBtn.textContent = "Starting...";

    fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: document.getElementById("url").value,
        model: document.getElementById("model").value,
        tamil_mode: document.getElementById("tamil_mode").value,
        english: document.getElementById("english").checked,
        summary: document.getElementById("summary").checked
      })
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) {
          errEl.textContent = res.d.error || "Something went wrong.";
          errEl.hidden = false;
        } else {
          document.getElementById("url").value = "";
          refresh();
        }
      })
      .catch(function () {
        errEl.textContent = "Could not reach the server. Is the window still open?";
        errEl.hidden = false;
      })
      .finally(function () {
        goBtn.disabled = false;
        goBtn.textContent = "Transcribe";
      });
  });

  // ---- rendering ------------------------------------------------------

  function renderJob(j) {
    var card = el("div", "job " + j.status);

    var head = el("div", "job-head");
    var left = el("div");
    left.appendChild(el("p", "job-title", j.title || "Fetching video details..."));
    var bits = [];
    if (j.channel) bits.push(j.channel);
    if (j.duration) bits.push(hhmm(j.duration));
    bits.push(j.model);
    left.appendChild(el("p", "job-meta", bits.join("  ·  ")));
    head.appendChild(left);
    card.appendChild(head);

    if (j.status === "running" || j.status === "queued") {
      var bar = el("div", "bar");
      var fill = el("i");
      fill.style.width = Math.round((j.progress || 0) * 100) + "%";
      bar.appendChild(fill);
      card.appendChild(bar);
      card.appendChild(el("p", "stage", j.stage));
    }

    if (j.status === "error") {
      card.appendChild(el("p", "job-error", j.error || "Stopped."));
    }

    // A finished job can still carry a note, e.g. the summary was skipped.
    if (j.status === "done" && j.error) {
      card.appendChild(el("p", "job-note", j.error));
    }

    // Finished and failed jobs both need actions - a failed one still has to
    // be removable, and is usually worth retrying.
    if (j.status === "done" || j.status === "error") {
      var actions = el("div", "job-actions");

      if (j.status === "done") {
        ORDER.forEach(function (name) {
          if (j.files.indexOf(name) === -1) return;
          var b = el("button", null, LABELS[name] || name);
          b.addEventListener("click", function () { openViewer(j, name); });
          actions.appendChild(b);
        });
      } else {
        var again = el("button", null, "Try again");
        again.addEventListener("click", function () {
          again.disabled = true;
          fetch("/api/jobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              url: j.url,
              model: j.model,
              tamil_mode: j.tamil_mode || "fluent",
              english: true,
              summary: true
            })
          }).then(refresh);
        });
        actions.appendChild(again);
      }

      var del = el("button", "del", "Delete");
      del.addEventListener("click", function () {
        if (!confirm("Delete this for good?")) return;
        fetch("/api/jobs/" + j.id, { method: "DELETE" }).then(refresh);
      });
      actions.appendChild(del);
      card.appendChild(actions);
    }

    return card;
  }

  function render(list) {
    jobsEl.textContent = "";
    emptyEl.hidden = list.length > 0;
    list.forEach(function (j) { jobsEl.appendChild(renderJob(j)); });
  }

  function refresh() {
    return fetch("/api/jobs")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var list = d.jobs || [];
        render(list);
        var busy = list.some(function (j) {
          return j.status === "running" || j.status === "queued";
        });
        schedule(busy ? 1500 : 8000);
      })
      .catch(function () { schedule(5000); });
  }

  function schedule(ms) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(refresh, ms);
  }

  // ---- viewer ---------------------------------------------------------

  function openViewer(job, file) {
    current.id = job.id;
    document.getElementById("v-title").textContent = job.title || "Transcript";
    document.getElementById("v-channel").textContent = job.channel || "";

    var tabs = document.getElementById("v-tabs");
    tabs.textContent = "";
    ORDER.forEach(function (name) {
      if (job.files.indexOf(name) === -1) return;
      var b = el("button", name === file ? "on" : null, LABELS[name] || name);
      b.addEventListener("click", function () { openViewer(job, name); });
      tabs.appendChild(b);
    });

    var body = document.getElementById("v-body");
    body.className = "tab-body" + (file.slice(-4) === ".srt" ? " srt" : "");
    body.textContent = "Loading...";
    viewer.hidden = false;

    fetch("/api/jobs/" + job.id + "/text/" + file)
      .then(function (r) { return r.text(); })
      .then(function (text) {
        current.file = file;
        current.text = text;
        body.textContent = "";
        if (file === "summary.md") {
          // Light touch: turn "## heading" lines into real headings, leave
          // everything else as plain text.
          text.split("\n").forEach(function (line) {
            if (line.indexOf("## ") === 0) {
              body.appendChild(el("h2", null, line.slice(3)));
            } else {
              body.appendChild(document.createTextNode(line + "\n"));
            }
          });
        } else {
          body.textContent = text;
        }
        document.getElementById("v-download").href =
          "/api/jobs/" + job.id + "/download/" + file;
      });
  }

  function closeViewer() { viewer.hidden = true; }

  document.getElementById("viewer-close").addEventListener("click", closeViewer);
  viewer.addEventListener("click", function (e) {
    if (e.target === viewer) closeViewer();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !viewer.hidden) closeViewer();
  });

  document.getElementById("v-copy").addEventListener("click", function () {
    var btn = this;
    navigator.clipboard.writeText(current.text).then(function () {
      btn.textContent = "Copied";
      setTimeout(function () { btn.textContent = "Copy text"; }, 1600);
    });
  });

  refresh();
})();
