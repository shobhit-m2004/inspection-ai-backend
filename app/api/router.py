from fastapi import APIRouter

from app.api.routes import analysis, documents, parameters, review

api_router = APIRouter()
api_router.include_router(documents.router, prefix='/documents', tags=['documents'])
api_router.include_router(review.router, prefix='/review', tags=['review'])
api_router.include_router(analysis.router, prefix='/analysis', tags=['analysis'])
api_router.include_router(parameters.router, prefix='/parameters', tags=['parameters'])
