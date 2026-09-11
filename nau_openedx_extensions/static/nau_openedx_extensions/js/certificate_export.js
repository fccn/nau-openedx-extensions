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
    const button = document.querySelector(buttonSelector);
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
            } else {
                alert(failureMessage);
            }
        } catch (error) {
            console.error("Error:", error);
            const container = document.querySelector('.certificate-export-section');
            const errorMessage = container.dataset.errorMsg;
            alert(errorMessage);
        }
    });
}

const exportButtons = [
    "#export-csv-certificates",
    "#export-zip-certificates",
    "#generate-grade-report"
];

// Initialize export buttons
exportButtons.forEach(selector => setupExportButton(selector));
