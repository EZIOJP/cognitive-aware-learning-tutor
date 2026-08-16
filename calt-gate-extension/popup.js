(function () {
  var status = document.getElementById("status");
  var api = typeof chrome !== "undefined" && chrome.runtime ? chrome : browser;

  function paint(res) {
    var g = (res && res.gateCache) || {};
    var b = g.browser || {};
    var mode = (b.mode_label || b.mode || "—").toUpperCase();
    var bits = ["Mode: " + mode];
    if (g.reward_day) bits.push("reward day");
    else if (g.day_unlimited) bits.push("goal met");
    if (g.stale || g.degraded) bits.push("stale");
    if (res && res.redirectsEnabled === false) bits.push("redirects OFF");
    status.textContent = bits.join(" · ");
  }

  function refresh() {
    api.runtime.sendMessage({ type: "GET_GATE" }, function (res) {
      paint(res || {});
    });
  }

  document.getElementById("refresh").onclick = function () {
    status.textContent = "Refreshing…";
    api.runtime.sendMessage({ type: "REFRESH_GATE" }, function (res) {
      paint(res || {});
    });
  };

  document.getElementById("toggle").onclick = function () {
    api.runtime.sendMessage({ type: "GET_GATE" }, function (cur) {
      var next = !(cur && cur.redirectsEnabled !== false);
      api.runtime.sendMessage({ type: "SET_REDIRECTS", enabled: next }, function () {
        refresh();
      });
    });
  };

  refresh();
})();
