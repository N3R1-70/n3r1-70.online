(function () {
  function formatDate(raw) {
    return raw || "";
  }

  function renderItems(container, items) {
    if (!items || !items.length) {
      container.innerHTML = '<p class="feed-status">Nessun aggiornamento disponibile al momento. Visita <a href="https://iwillnotlookaway.org" target="_blank" rel="noopener">iwillnotlookaway.org</a>.</p>';
      return;
    }
    var html = items
      .map(function (item) {
        return (
          '<a class="feed-item" href="' + item.url + '" target="_blank" rel="noopener">' +
            '<span class="feed-date">' + formatDate(item.date) + "</span>" +
            "<span>" +
              '<span class="feed-category">' + (item.category || "Analisi") + "</span>" +
              '<span class="feed-title" style="display:block;">' + item.title + "</span>" +
            "</span>" +
          "</a>"
        );
      })
      .join("");
    container.innerHTML = html;
  }

  function renderStats(data) {
    var stats = data && data.stats;
    if (!stats) return;
    Object.keys(stats).forEach(function (key) {
      var el = document.querySelector('[data-stat="' + key + '"]');
      if (el) el.textContent = stats[key];
    });
  }

  function loadFeed() {
    var teaser = document.getElementById("feed-teaser");
    var full = document.getElementById("feed-full");
    if (!teaser && !full && !document.querySelector("[data-stat]")) return;

    fetch("data/iwnla-feed.json", { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("feed non disponibile");
        return res.json();
      })
      .then(function (data) {
        var items = (data && data.items) || [];
        if (teaser) {
          var limit = parseInt(teaser.getAttribute("data-limit"), 10) || items.length;
          renderItems(teaser, items.slice(0, limit));
        }
        if (full) {
          renderItems(full, items);
        }
        renderStats(data);
      })
      .catch(function () {
        var msg = '<p class="feed-status">Aggiornamenti non disponibili al momento. Visita <a href="https://iwillnotlookaway.org" target="_blank" rel="noopener">iwillnotlookaway.org</a> direttamente.</p>';
        if (teaser) teaser.innerHTML = msg;
        if (full) full.innerHTML = msg;
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadFeed);
  } else {
    loadFeed();
  }
})();
