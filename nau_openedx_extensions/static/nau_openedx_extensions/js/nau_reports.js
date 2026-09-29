/**
 * NAU Reports tab of the Instructor Dashboard.
 *
 * Everything is wrapped in a function and looked up inside the tab root element (`.nau-reports`),
 * so this script can run on the same page as the Certificate Export tab script without sharing
 * global names or binding to that tab's buttons.
 */
(function () {
    const root = document.querySelector(".nau-reports");
    if (!root) return;

    // Same interval as the list of reports of the Data Download tab.
    const REPORT_DOWNLOADS_POLL_INTERVAL = 20000;

    // Set when the list could not be loaded (e.g. no permission), so the periodic
    // reload stops until the tab is opened again.
    let reportDownloadsLoadFailed = false;

    /**
     * Retrieves the value of a cookie by name.
     *
     * @param {string} name - The name of the cookie to retrieve.
     * @returns {string|null} The cookie value, or null if not found.
     */
    function getCookie(name) {
        const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
        return match ? decodeURIComponent(match[1]) : null;
    }

    /**
     * Sets up a button to send a POST request to a specified endpoint when clicked.
     * It uses the CSRF token from the cookies and provides user feedback based on the response.
     * The success and failure messages are read from the button's dataset attributes.
     *
     * @param {string} buttonSelector - The CSS selector of the button (e.g., '#export-button').
     */
    function setupExportButton(buttonSelector) {
        const button = root.querySelector(buttonSelector);
        if (!button) return;

        button.addEventListener("click", async function () {
            const endpoint = this.dataset.endpoint;
            const successMessage = this.dataset.success;
            const failureMessage = this.dataset.failure;

            if (!endpoint) {
                console.warn("No endpoint specified for this button.");
                return;
            }

            const csrftoken = getCookie("csrftoken");

            try {
                const response = await fetch(endpoint, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrftoken,
                    },
                });

                // NAU endpoints reply {"success": true} and Open edX instructor endpoints
                // reply {"status": "..."}; both report failures with an HTTP error status.
                if (response.ok) {
                    alert(successMessage);
                    loadReportDownloads();
                } else {
                    alert(failureMessage);
                }
            } catch (error) {
                console.error("Error:", error);
                alert(root.dataset.errorMsg);
            }
        });
    }

    /**
     * Lists the reports available for download that were generated from this tab.
     * The endpoint returns every report of the course, so only the files whose name starts
     * with one of the prefixes in the list's `data-prefixes` attribute are shown.
     */
    async function loadReportDownloads() {
        const list = root.querySelector(".report-downloads-list");
        if (!list) return;

        const prefixes = JSON.parse(list.dataset.prefixes);
        const showMessage = (message) => {
            const item = document.createElement("li");
            item.textContent = message;
            list.replaceChildren(item);
        };

        try {
            const response = await fetch(list.dataset.endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
            });
            if (!response.ok) {
                reportDownloadsLoadFailed = true;
                showMessage(list.dataset.failure);
                return;
            }

            reportDownloadsLoadFailed = false;
            const data = await response.json();
            const downloads = data.downloads.filter(
                (download) => prefixes.some((prefix) => download.name.startsWith(prefix))
            );
            if (!downloads.length) {
                showMessage(list.dataset.empty);
                return;
            }

            list.replaceChildren(...downloads.map((download) => {
                const item = document.createElement("li");
                const link = document.createElement("a");
                link.href = download.url;
                link.textContent = download.name;
                item.appendChild(link);
                return item;
            }));
        } catch (error) {
            console.error("Error:", error);
            reportDownloadsLoadFailed = true;
            showMessage(list.dataset.failure);
        }
    }

    /**
     * Keeps the list of reports up to date, like the Data Download tab: it is reloaded when this
     * tab is opened, and every 20 seconds while this is the open tab and the browser tab is visible.
     * The Instructor Dashboard marks the open tab with the `active-section` CSS class.
     */
    function setupReportDownloadsPolling() {
        const list = root.querySelector(".report-downloads-list");
        if (!list) return;

        const section = list.closest(".idash-section");
        if (section) {
            document.querySelector(`[data-section="${section.id}"]`)?.addEventListener("click", loadReportDownloads);
        }

        setInterval(() => {
            const tabIsOpen = !section || section.classList.contains("active-section");
            if (tabIsOpen && !document.hidden && !reportDownloadsLoadFailed) {
                loadReportDownloads();
            }
        }, REPORT_DOWNLOADS_POLL_INTERVAL);
    }

    const exportButtons = [
        "#nau-reports-export-csv-certificates",
        "#nau-reports-export-zip-certificates",
        "#generate-grade-report",
        "#generate-profile-report",
        "#generate-survey-report"
    ];

    // Initialize export buttons
    exportButtons.forEach(selector => setupExportButton(selector));

    // Initialize the list of reports available for download
    loadReportDownloads();
    setupReportDownloadsPolling();
}());
