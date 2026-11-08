from pathlib import Path
from fastapi.templating import Jinja2Templates

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

class SafeJinja2Templates(Jinja2Templates):
    def TemplateResponse(self, *args, **kwargs):
        # Support both old Starlette: TemplateResponse("file.html", context)
        # and new Starlette: TemplateResponse(request=req, name="file.html", context=context)
        if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], dict):
            name = args[0]
            context = args[1]
            req = context.get("request")
            status_code = args[2] if len(args) > 2 else kwargs.get("status_code", 200)
            return super().TemplateResponse(
                request=req,
                name=name,
                context=context,
                status_code=status_code,
                **{k: v for k, v in kwargs.items() if k != "status_code"}
            )
        return super().TemplateResponse(*args, **kwargs)

templates = SafeJinja2Templates(directory=str(TEMPLATE_DIR))
