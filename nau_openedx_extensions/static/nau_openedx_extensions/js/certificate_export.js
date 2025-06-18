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
 *
 * @param {string} buttonSelector - The CSS selector of the button (e.g., '#export-button').
 * @param {string} successMessage - Message to display when the request succeeds.
 * @param {string} failureMessage - Message to display when the request fails or the response is not successful.
 */
function setupExportButton(buttonSelector, successMessage, failureMessage) {
    const button = document.querySelector(buttonSelector);
    if (!button) return;

    button.addEventListener("click", async function () {
        const endpoint = this.dataset.endpoint;
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

            const data = await response.json();
            if (data && data.success) {
                alert(successMessage);
            } else {
                alert(failureMessage);
            }
        } catch (error) {
            console.error("Error:", error);
            alert(gettext("An unexpected error occurred. Please try again later."));
        }
    });
}

const exportButtons = [
    {
        selector: "#export-csv-certificates",
        success: "CSV export task started successfully!",
        failure: "Failed to start CSV export task."
    },
    {
        selector: "#export-zip-certificates",
        success: "ZIP export task started successfully!",
        failure: "Failed to start ZIP export task."
    }
];

// Initialize export buttons
exportButtons.forEach(cfg =>
    setupExportButton(cfg.selector, cfg.success, cfg.failure)
);
