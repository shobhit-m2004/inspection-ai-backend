from fastapi import APIRouter

from app.schemas.parameter import ParameterSuggestionResponse
from app.services.normalization_service import normalization_service

router = APIRouter()


@router.get('/suggestions', response_model=ParameterSuggestionResponse)
def parameter_suggestions():
    return ParameterSuggestionResponse(
        predefined_parameters=normalization_service.predefined_parameters(),
        aliases=normalization_service.aliases(),
    )
