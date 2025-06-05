const button = document.querySelector("#export-csv-certificates");
if (button) {
    button.addEventListener("click", function () {
        // Extraer el course_id desde la URL actual
        const pathParts = window.location.pathname.split("/");
        const courseId = pathParts.find(part => part.startsWith("course-v1"));

        if (!courseId) {
            console.error("No se pudo encontrar el course_id en la URL.");
            return;
        }

        // Construye la URL correctamente con el prefijo nau-openedx-extensions
        const endpoint = `/nau-openedx-extensions/certificate_export/courses/${courseId}/certificate_export/csv`;

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
                "X-CSRFToken": csrftoken, // Agrega el token CSRF
            },
            body: JSON.stringify({
                course_id: courseId, // Pasa el course_id en el cuerpo de la solicitud
            }),
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
} else {
    console.error("El botón export-csv-certificates no existe en el DOM.");
}