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
 * @param {Object} [options] - Optional configuration.
 * @param {string} [options.inputSelector] - CSS selector for an input field whose value
 *   should be included in the POST body as a specific key.
 * @param {string} [options.inputKey] - The key name to use in the POST body for the input value.
 */
function setupExportButton(buttonSelector, options) {
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

        // Build request body if an input selector is configured
        let body = undefined;
        if (options && options.inputSelector && options.inputKey) {
            const input = document.querySelector(options.inputSelector);
            if (input) {
                const value = input.value.trim();
                if (!value) {
                    alert("Please enter a value in the input field.");
                    return;
                }
                body = JSON.stringify({ [options.inputKey]: value });
            }
        }

        const csrftoken = getCookie("csrftoken");

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                },
                body: body,
            });

            const data = await response.json();
            if (data && data.success) {
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

// Certificate export buttons (no input needed)
setupExportButton("#export-csv-certificates");
setupExportButton("#export-zip-certificates");

// Student answers values report button (requires block_id from input)
setupExportButton("#generate-student-answers-report", {
    inputSelector: "#problem-location",
    inputKey: "block_id",
});
