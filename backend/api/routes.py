from fastapi import APIRouter

from .public.advertisements import router as advertisements_router
from .public.advertisement_tariffs import router as advertisement_tariffs_router
from .public.auth import router as auth_router
from .public.channels import router as channels_router
from .public.companies import router as companies_router
from .public.payments import router as payments_router
from .public.tariffs import router as tariffs_router
from .public.users import router as users_router
from .public.upload import router as upload_router

router = APIRouter()


router.include_router(auth_router)
router.include_router(users_router)
router.include_router(tariffs_router)
router.include_router(companies_router)
router.include_router(channels_router)
router.include_router(payments_router)
router.include_router(advertisements_router)
router.include_router(advertisement_tariffs_router)
router.include_router(upload_router)
