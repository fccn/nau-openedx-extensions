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

        // Construye la URL según la definición en urls.py
        const endpoint = `/courses/${courseId}/certificate_export/csv`;

        fetch(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
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