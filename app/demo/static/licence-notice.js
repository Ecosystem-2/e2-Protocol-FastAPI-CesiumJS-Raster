// SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
// SPDX-FileCopyrightText: 2025-2026 Yang Zhang
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * AGPL sections 0 and 13: an interactive network UI has to show the copyright, the
 * absence of warranty, how to read the licence, and how to get the source. The values
 * come from /source rather than being hardcoded, so an operator who modifies this
 * service and sets SOURCE_URL offers their users their own source, not ours.
 */

(function () {
  const STYLE = `
    #agpl-notice {
      position: fixed; bottom: 0; right: 0; z-index: 9999;
      font: 11px/1.6 system-ui, sans-serif;
      background: rgba(20, 20, 20, 0.82); color: #ddd;
      padding: 4px 10px; border-radius: 4px 0 0 0;
      max-width: 100%; box-sizing: border-box;
    }
    #agpl-notice a { color: #7fb3ff; text-decoration: underline; }
    #agpl-notice .agpl-sep { opacity: 0.5; margin: 0 6px; }
  `;

  function render(offer) {
    const notice = document.createElement("div");
    notice.id = "agpl-notice";

    const revision = offer.revision ? ` (${offer.revision.slice(0, 7)})` : "";

    // Saying the operator hasn't told us is a truthful answer to "where is the source";
    // a link to whatever we happened to build from is not.
    const source = offer.source
      ? `<a href="${encodeURI(offer.source)}" target="_blank" rel="noopener">Source${escapeHtml(revision)}</a>`
      : `Source not offered by this deployment`;

    notice.innerHTML =
      `${escapeHtml(offer.copyright)}` +
      `<span class="agpl-sep">|</span>` +
      `<a href="${encodeURI(offer.licence_text)}" target="_blank" rel="noopener">` +
      `${escapeHtml(offer.licence)}</a>` +
      `<span class="agpl-sep">|</span>` +
      source +
      `<span class="agpl-sep">|</span>` +
      `${escapeHtml(offer.warranty)}`;

    const style = document.createElement("style");
    style.textContent = STYLE;
    document.head.appendChild(style);
    document.body.appendChild(notice);
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function mount() {
    fetch("/source")
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then(render)
      .catch(() => {
        // The offer must survive the endpoint being unreachable, otherwise the one
        // situation where a user most needs the link is the one where it vanishes.
        render({
          copyright: "Copyright (c) 2025-2026 Ecosystem2 Ltd and Yang Zhang",
          licence: "AGPL-3.0-or-later",
          licence_text: "/licence",
          source: null,
          warranty: "This program comes with ABSOLUTELY NO WARRANTY.",
          revision: null,
        });
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
