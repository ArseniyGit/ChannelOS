from fastapi import APIRouter

from .admin.advertisements import router as advertisements_router
from .admin.advertisement_tariffs import router as advertisement_tariffs_router
from .admin.channels import router as channels_router
from .admin.companies import router as companies_router
from .admin.payments import router as payments_router
from .admin.ranks import router as ranks_router
from .admin.stats import router as stats_router
from .admin.tariffs import router as tariffs_router
from .admin.users import router as users_router

router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(stats_router)
router.include_router(users_router)
router.include_router(tariffs_router)
router.include_router(advertisement_tariffs_router)
router.include_router(channels_router)
router.include_router(companies_router)
router.include_router(payments_router)
router.include_router(ranks_router)
router.include_router(advertisements_router)
