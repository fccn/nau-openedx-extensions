from rest_framework.views import APIView
from rest_framework.response import Response
from nau_openedx_extensions.certificate_export.tasks import export_course_certificates_task

class CertificateExportAPIView(APIView):
    """
    API endpoint to start the certificate export task.
    """
    def post(self, request, course_id):
        # Lógica para iniciar la tarea de exportación
        export_course_certificates_task.delay(course_id)
        return Response({"success": True, "message": "CSV export task started successfully."})