const button = document.querySelector("#export-csv-certificates");
if (button) {
    button.addEventListener("click", function () {
        const endpoint = this.dataset.endpoint; // The endpoint URL is stored in a data attribute

        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== "") {
                const cookies = document.cookie.split(";");
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.startsWith(name + "=")) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        const csrftoken = getCookie("csrftoken");

        fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrftoken, // add CSRF token for security
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("CSV export task started successfully!");
            } else {
                alert("Failed to start CSV export task.");
            }
        })
        .catch(error => {
            console.error("Error starting CSV export task:", error);
        });
    });
}