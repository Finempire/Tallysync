import logging

logger = logging.getLogger(__name__)

class TenantDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'tenant'):
            print(f"DEBUG: Host={request.get_host()}, Tenant={request.tenant.schema_name}, Domain={request.tenant.domains.first().domain if request.tenant.domains.exists() else 'None'}", flush=True)
        else:
            print(f"DEBUG: Host={request.get_host()}, Tenant=NOT SET", flush=True)
        
        response = self.get_response(request)
        return response
